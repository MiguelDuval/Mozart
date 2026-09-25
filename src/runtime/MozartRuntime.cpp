#include "MozartRuntime.h"

#include "core/MidiTypes.h"

#include <chrono>

namespace mozart::runtime {

MozartRuntime::MozartRuntime(midi::MidiOutputTransport& midiOutput)
    : sendQueue_(midiOutput),
      scheduler_(linkClock_, sendQueue_) {}

MozartRuntime::~MozartRuntime() {
    stop();
}

void MozartRuntime::start() {
    if (started_) {
        return;
    }

    sendQueue_.start();
    scheduler_.start();
    started_ = true;
}

void MozartRuntime::stop() {
    if (!started_) {
        return;
    }

    scheduler_.setArmed(false);
    scheduler_.stop();
    sendQueue_.stop();
    started_ = false;
}

void MozartRuntime::setLinkEnabled(const bool enabled) noexcept {
    linkClock_.setEnabled(enabled);

    if (!enabled) {
        setAccompanimentEnabled(false);
    }
}

void MozartRuntime::setAccompanimentEnabled(const bool enabled) noexcept {
    if (enabled) {
        if (started_) {
            scheduler_.start();
        }
        scheduler_.setArmed(true);
        return;
    }

    scheduler_.setArmed(false);
    scheduler_.stop();
    sendQueue_.clearPending();
}

void MozartRuntime::setKeyScale(const musical::KeyScale& keyScale) {
    scheduler_.setKeyScale(keyScale);
}

bool MozartRuntime::sendDiagnosticNote() {
    start();

    using namespace std::chrono;
    const auto now = duration_cast<nanoseconds>(
            steady_clock::now().time_since_epoch()).count();
    const auto noteOnTimestamp =
            static_cast<std::uint64_t>(now + 50'000'000LL);
    const auto noteOffTimestamp =
            static_cast<std::uint64_t>(now + 300'000'000LL);

    const auto noteOn = midi::noteOn(0, 36, 100, noteOnTimestamp);
    const auto noteOff = midi::noteOff(0, 36, 0, noteOffTimestamp);

    if (!noteOn.has_value() || !noteOff.has_value()) {
        return false;
    }

    const bool onQueued = sendQueue_.enqueue(*noteOn);
    const bool offQueued = sendQueue_.enqueue(*noteOff);
    return onQueued && offQueued;
}

bool MozartRuntime::linkEnabled() const noexcept {
    return linkClock_.isEnabled();
}

bool MozartRuntime::accompanimentEnabled() const noexcept {
    return scheduler_.isArmed();
}

} // namespace mozart::runtime
