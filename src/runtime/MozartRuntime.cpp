#include "MozartRuntime.h"

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
        scheduler_.setArmed(false);
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

bool MozartRuntime::linkEnabled() const noexcept {
    return linkClock_.isEnabled();
}

bool MozartRuntime::accompanimentEnabled() const noexcept {
    return scheduler_.isArmed();
}

} // namespace mozart::runtime
