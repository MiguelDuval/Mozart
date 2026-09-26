#include "AccompanimentScheduler.h"

#include "core/MidiTypes.h"
#include "core/TransportMath.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <limits>

namespace mozart::scheduler {

namespace {

[[nodiscard]] std::uint64_t beatToTimestampNanos(
        const std::chrono::microseconds hostTime) noexcept {
    if (hostTime.count() <= 0) {
        return 0;
    }

    const auto micros = static_cast<std::uint64_t>(hostTime.count());
    constexpr std::uint64_t kNanosPerMicrosecond = 1'000ULL;

    if (micros > std::numeric_limits<std::uint64_t>::max() /
            kNanosPerMicrosecond) {
        return std::numeric_limits<std::uint64_t>::max();
    }

    return micros * kNanosPerMicrosecond;
}

} // namespace

AccompanimentScheduler::AccompanimentScheduler(
        clock::LinkClock& clock,
        MidiSendQueue& sendQueue)
    : clock_(clock),
      sendQueue_(sendQueue) {}

AccompanimentScheduler::~AccompanimentScheduler() {
    stop();
}

void AccompanimentScheduler::start() {
    if (running_.exchange(true)) {
        return;
    }

    worker_ = std::thread(&AccompanimentScheduler::run, this);
}

void AccompanimentScheduler::stop() {
    if (!running_.exchange(false)) {
        return;
    }

    wakeCondition_.notify_all();

    if (worker_.joinable()) {
        worker_.join();
    }

    launchBarStart_ = -1.0;
    nextBarIndex_ = 0;
    nextEventIndex_ = 0;
    activeRole_ = requestedRole_.load();
}

void AccompanimentScheduler::setArmed(const bool armed) noexcept {
    armed_.store(armed);
    wakeCondition_.notify_all();
}

bool AccompanimentScheduler::isArmed() const noexcept {
    return armed_.load();
}

void AccompanimentScheduler::setKeyScale(const musical::KeyScale& keyScale) {
    if (!keyScale.isValid()) {
        return;
    }

    std::lock_guard<std::mutex> lock(stateMutex_);
    keyScale_ = keyScale;
}

musical::KeyScale AccompanimentScheduler::keyScale() const {
    std::lock_guard<std::mutex> lock(stateMutex_);
    return keyScale_;
}

void AccompanimentScheduler::setRole(
        const AccompanimentRole role) noexcept {
    requestedRole_.store(role);
    wakeCondition_.notify_all();
}

AccompanimentRole AccompanimentScheduler::role() const noexcept {
    return requestedRole_.load();
}

void AccompanimentScheduler::run() {
    constexpr double kLookAheadSeconds = 0.032;
    constexpr double kEpsilon = 1.0e-9;
    constexpr std::chrono::milliseconds kPollPeriod{5};

    while (running_.load()) {
        if (!armed_.load() || !clock_.isEnabled()) {
            launchBarStart_ = -1.0;
            nextBarIndex_ = 0;
            nextEventIndex_ = 0;
        } else {
            const auto snapshot = clock_.captureAppSnapshot();

            // START/STOP Sync is intentionally not part of this stage. The
            // local START button arms accompaniment; Link supplies the shared
            // beat/tempo/phase timeline whether or not a remote peer is
            // publishing a start/stop state.
            if (!(snapshot.tempoBpm > 0.0) ||
                !std::isfinite(snapshot.tempoBpm)) {
                launchBarStart_ = -1.0;
                nextBarIndex_ = 0;
                nextEventIndex_ = 0;
            } else {
                // The musical cursor is deliberately independent of tempo.
                // A Link tempo change changes beat->host-time conversion, not
                // which note comes next. This prevents the sequence from
                // restarting or waiting for a new bar after a tempo change.
                if (launchBarStart_ < 0.0) {
                    // START is quantized once, at arming time. After launch,
                    // this reference beat is never recomputed from tempo.
                    launchBarStart_ =
                            timing::nextQuantizedBeat(
                                    snapshot.beat,
                                    snapshot.quantum);
                    nextBarIndex_ = 0;
                    nextEventIndex_ = 0;
                    activeRole_ = requestedRole_.load();
                }

                const auto events =
                        activeRole_ == AccompanimentRole::Arpeggio
                                ? generation::ArpeggioGenerator::generateBar(
                                        keyScale(), 4, seed_, 0)
                                : generation::BassGenerator::generateBar(
                                        keyScale(), 2, seed_, 0);

                if (events.empty()) {
                    nextBarIndex_ = 0;
                    nextEventIndex_ = 0;
                } else if (snapshot.beat + kEpsilon >= launchBarStart_) {
                    const double lookAheadBeats =
                            std::max(
                                    0.03125,
                                    snapshot.tempoBpm * kLookAheadSeconds / 60.0);

                    // Advance the persistent cursor through every event whose
                    // beat coordinate fits inside the short look-ahead window.
                    // Only the timestamp mapping is tempo-dependent.
                    while (nextEventIndex_ < events.size()) {
                        const double eventBeat =
                                launchBarStart_ +
                                static_cast<double>(nextBarIndex_) *
                                        snapshot.quantum +
                                events[nextEventIndex_].startBeat;

                        if (eventBeat > snapshot.beat + lookAheadBeats + kEpsilon) {
                            break;
                        }

                        scheduleEvent(
                                snapshot,
                                events[nextEventIndex_],
                                eventBeat);

                        ++nextEventIndex_;
                    }

                    if (nextEventIndex_ >= events.size()) {
                        nextEventIndex_ = 0;
                        ++nextBarIndex_;

                        // Role changes are quantized to the next bar so a
                        // performer can switch voices without truncating the
                        // currently running musical phrase.
                        activeRole_ = requestedRole_.load();
                    }
                }

            }
        }

        std::unique_lock<std::mutex> lock(wakeMutex_);
        wakeCondition_.wait_for(
                lock,
                kPollPeriod,
                [this] { return !running_.load(); });
    }
}

void AccompanimentScheduler::scheduleEvent(
        const clock::LinkClockSnapshot& snapshot,
        const musical::MusicalNoteEvent& event,
        const double startBeat) {
    const double endBeat = startBeat + event.durationBeats;

    // If the scheduler wakes up slightly late, sending the current note with
    // an immediate monotonic timestamp is preferable to dropping a musical
    // step. Normal operation keeps events inside the look-ahead horizon.
    const auto nowTimestamp = beatToTimestampNanos(snapshot.hostTime);
    const auto desiredStartTimestamp =
            beatToTimestampNanos(clock_.hostTimeAtBeat(startBeat));
    const auto noteOnTimestamp =
            desiredStartTimestamp < nowTimestamp
                    ? nowTimestamp
                    : desiredStartTimestamp;

    const auto desiredNoteOffTimestamp =
            beatToTimestampNanos(clock_.hostTimeAtBeat(endBeat));
    const auto minimumNoteOffTimestamp =
            noteOnTimestamp + 1'000'000ULL;
    const auto noteOffTimestamp =
            desiredNoteOffTimestamp < minimumNoteOffTimestamp
                    ? minimumNoteOffTimestamp
                    : desiredNoteOffTimestamp;

    const auto noteOn =
            midi::noteOn(
                    event.channel,
                    event.note,
                    event.velocity,
                    noteOnTimestamp);

    const auto noteOff =
            midi::noteOff(
                    event.channel,
                    event.note,
                    0,
                    noteOffTimestamp);

    if (noteOn.has_value()) {
        (void) sendQueue_.enqueue(*noteOn);
    }

    if (noteOff.has_value()) {
        (void) sendQueue_.enqueue(*noteOff);
    }
}

} // namespace mozart::scheduler
