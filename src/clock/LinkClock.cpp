#include "LinkClock.h"

#include <stdexcept>

namespace mozart::clock {

LinkClock::LinkClock(const double initialTempoBpm, const double quantum)
    : link_(initialTempoBpm),
      quantum_(quantum) {
    if (!(quantum_ > 0.0)) {
        throw std::invalid_argument("Link quantum must be positive");
    }
}

void LinkClock::setEnabled(const bool enabled) noexcept {
    link_.enable(enabled);
}

bool LinkClock::isEnabled() const noexcept {
    return link_.isEnabled();
}

void LinkClock::enableStartStopSync(const bool enabled) noexcept {
    link_.enableStartStopSync(enabled);
}

bool LinkClock::isStartStopSyncEnabled() const noexcept {
    return link_.isStartStopSyncEnabled();
}

LinkClockSnapshot LinkClock::captureAppSnapshot() const {
    const auto state = link_.captureAppSessionState();
    const auto hostTime = link_.clock().micros();
    const auto peers = link_.numPeers();

    return {
        link_.isEnabled(),
        state.isPlaying(),
        peers > 0,
        peers,
        state.tempo(),
        state.beatAtTime(hostTime, quantum_),
        state.phaseAtTime(hostTime, quantum_),
        quantum_,
        hostTime
    };
}

std::chrono::microseconds LinkClock::hostTimeAtBeat(const double beat) const {
    const auto state = link_.captureAppSessionState();
    return state.timeAtBeat(beat, quantum_);
}

double LinkClock::beatAtHostTime(
        const std::chrono::microseconds hostTime) const {
    const auto state = link_.captureAppSessionState();
    return state.beatAtTime(hostTime, quantum_);
}

} // namespace mozart::clock
