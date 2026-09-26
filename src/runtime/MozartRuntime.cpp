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

    // Reuse the normal accompaniment shutdown path while the MIDI send queue
    // is still alive, so an in-flight Note On cannot leave a stuck note.
    setAccompanimentEnabled(false);
    setLinkEnabled(false);

    sendQueue_.stop();
    started_ = false;
}

void MozartRuntime::setLinkEnabled(const bool enabled) noexcept {
    linkClock_.setEnabled(enabled);

    // Disabling Link should stop an armed accompanist, but must not invoke the
    // shutdown path twice when callers already stopped accompaniment first.
    if (!enabled && accompanimentEnabled()) {
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

    // STOP must not leave a Note On sounding after its queued Note Off was
    // discarded. Send a transport-level panic after clearing future events.
    const auto now = std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
    const auto timestamp =
            static_cast<std::uint64_t>(now + 10'000'000LL);

    const auto allNotesOff = midi::controlChange(0, 123, 0, timestamp);
    const auto allSoundOff = midi::controlChange(0, 120, 0, timestamp);

    if (allNotesOff.has_value()) {
        (void) sendQueue_.enqueue(*allNotesOff);
    }
    if (allSoundOff.has_value()) {
        (void) sendQueue_.enqueue(*allSoundOff);
    }
}

void MozartRuntime::setKeyScale(const musical::KeyScale& keyScale) {
    scheduler_.setKeyScale(keyScale);
}

void MozartRuntime::setAccompanimentRole(
        const scheduler::AccompanimentRole role) noexcept {
    scheduler_.setRole(role);
}

scheduler::AccompanimentRole MozartRuntime::accompanimentRole() const noexcept {
    return scheduler_.role();
}

void MozartRuntime::setPatternDensity(
        const generation::PatternDensity density) noexcept {
    scheduler_.setDensity(density);
}

generation::PatternDensity MozartRuntime::patternDensity() const noexcept {
    return scheduler_.density();
}

void MozartRuntime::setPatternAccent(
        const generation::PatternAccent accent) noexcept {
    scheduler_.setAccent(accent);
}

generation::PatternAccent MozartRuntime::patternAccent() const noexcept {
    return scheduler_.accent();
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

clock::LinkClockSnapshot MozartRuntime::captureLinkSnapshot() const {
    return linkClock_.captureAppSnapshot();
}

} // namespace mozart::runtime
