#pragma once

#include "clock/LinkClock.h"
#include "midi/MidiTransport.h"
#include "scheduler/AccompanimentScheduler.h"
#include "scheduler/MidiSendQueue.h"

namespace mozart::runtime {

class MozartRuntime final {
public:
    explicit MozartRuntime(midi::MidiOutputTransport& midiOutput);
    ~MozartRuntime();

    MozartRuntime(const MozartRuntime&) = delete;
    MozartRuntime& operator=(const MozartRuntime&) = delete;

    void start();
    void stop();

    void setLinkEnabled(bool enabled) noexcept;
    void setAccompanimentEnabled(bool enabled) noexcept;
    void setKeyScale(const musical::KeyScale& keyScale);

    [[nodiscard]] bool linkEnabled() const noexcept;
    [[nodiscard]] bool accompanimentEnabled() const noexcept;

private:
    clock::LinkClock linkClock_{120.0, 4.0};
    scheduler::MidiSendQueue sendQueue_;
    scheduler::AccompanimentScheduler scheduler_;
    bool started_ = false;
};

} // namespace mozart::runtime
