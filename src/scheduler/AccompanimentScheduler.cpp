#include "AccompanimentScheduler.h"

#include "core/MidiTypes.h"
#include "core/TransportMath.h"

#include <chrono>
#include <cmath>
#include <cstdint>
#include <limits>

namespace mozart::scheduler {

namespace {

[[nodiscard]] std::uint64_t beatToTimestampNanos(
        const clock::LinkClockSnapshot& snapshot,
        const double beat) noexcept {
    const double deltaBeats = beat - snapshot.beat;
    const double deltaMicros =
            deltaBeats * (60.0 / snapshot.tempoBpm) * 1'000'000.0;

    const double timestampMicros =
            static_cast<double>(snapshot.hostTime.count()) + deltaMicros;

    if (!(timestampMicros > 0.0)) {
        return 0;
    }

    const double timestampNanos = timestampMicros * 1'000.0;
    const double maxNanos =
            static_cast<double>(std::numeric_limits<std::uint64_t>::max());

    if (timestampNanos >= maxNanos) {
        return std::numeric_limits<std::uint64_t>::max();
    }

    return static_cast<std::uint64_t>(timestampNanos);
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

    scheduledBarStart_ = -1.0;
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

void AccompanimentScheduler::run() {
    constexpr double kLookAheadBeats = 1.0;
    constexpr double kEpsilon = 1.0e-9;

    while (running_.load()) {
        if (!armed_.load() || !clock_.isEnabled()) {
            scheduledBarStart_ = -1.0;
        } else {
            const auto snapshot = clock_.captureAppSnapshot();

            if (!snapshot.playing || !(snapshot.tempoBpm > 0.0)) {
                scheduledBarStart_ = -1.0;
            } else {
                const auto barStart =
                        timing::quantizeBeat(snapshot.beat, snapshot.quantum);

                if (barStart + kEpsilon < scheduledBarStart_) {
                    scheduledBarStart_ = -1.0;
                }

                if (barStart <= snapshot.beat + kLookAheadBeats &&
                    barStart > scheduledBarStart_ + kEpsilon) {
                    scheduleBar(snapshot, keyScale(), barStart);
                    scheduledBarStart_ = barStart;
                }
            }
        }

        std::unique_lock<std::mutex> lock(wakeMutex_);
        wakeCondition_.wait_for(
                lock,
                std::chrono::milliseconds(10),
                [this] { return !running_.load(); });
    }
}

void AccompanimentScheduler::scheduleBar(
        const clock::LinkClockSnapshot& snapshot,
        const musical::KeyScale& keyScale,
        const double barStartBeat) {
    const auto events =
            generation::BassGenerator::generateBar(keyScale, 2, seed_, 0);

    for (const auto& event : events) {
        const double startBeat = barStartBeat + event.startBeat;
        const double endBeat = startBeat + event.durationBeats;

        // Never enqueue a note whose onset is already behind the current
        // Link position. A late scheduler iteration may still see the
        // beginning of the current bar inside its look-ahead window.
        if (startBeat < snapshot.beat) {
            continue;
        }

        const auto noteOnTimestamp = beatToTimestampNanos(snapshot, startBeat);
        const auto noteOffTimestamp = beatToTimestampNanos(snapshot, endBeat);

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
}

} // namespace mozart::scheduler
