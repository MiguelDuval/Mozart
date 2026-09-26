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

}
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
    launchBarStart_ = -1.0;
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
            launchBarStart_ = -1.0;
        } else {
            const auto snapshot = clock_.captureAppSnapshot();

            // START/STOP Sync is intentionally not part of this stage. The
            // local START button arms accompaniment; Link supplies the shared
            // beat/tempo/phase timeline whether or not a remote peer is
            // publishing a start/stop state.
            if (!(snapshot.tempoBpm > 0.0)) {
                scheduledBarStart_ = -1.0;
                launchBarStart_ = -1.0;
            } else {
                // START is quantized to the next Link quantum boundary.
                // This prevents a mid-bar START from entering the current bar.
                if (launchBarStart_ < 0.0) {
                    launchBarStart_ =
                            timing::nextQuantizedBeat(snapshot.beat, snapshot.quantum);
                }

                const auto barStart =
                        scheduledBarStart_ < 0.0
                                ? launchBarStart_
                                : timing::quantizeBeat(
                                        snapshot.beat,
                                        snapshot.quantum);

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

        // Never enqueue a Note On whose musical start has already passed.
        if (startBeat < snapshot.beat) {
            continue;
        }

        const auto noteOnTimestamp =
                beatToTimestampNanos(clock_.hostTimeAtBeat(startBeat));
        const auto noteOffTimestamp =
                beatToTimestampNanos(clock_.hostTimeAtBeat(endBeat));

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
