#pragma once

#include "clock/LinkClock.h"
#include "generation/PatternAccent.h"
#include "generation/PatternDensity.h"
#include "generation/PatternSwing.h"
#include "generation/NoteRepeat.h"
#include "midi/MidiTransport.h"
#include "midi/ControllerMapping.h"
#include "musical/KeyContext.h"
#include "scheduler/AccompanimentScheduler.h"
#include <cstdint>
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
    void setKeyContextSource(musical::KeyContextSource source) noexcept;
    void updateAudioKeyDetection(
            const musical::AudioKeyDetectionResult& result) noexcept;
    void resetAudioKeyContext() noexcept;
    [[nodiscard]] musical::KeyContextSnapshot captureKeyContextSnapshot() const;
    void setAccompanimentRole(scheduler::AccompanimentRole role) noexcept;
    [[nodiscard]] scheduler::AccompanimentRole accompanimentRole() const noexcept;

    void setPatternDensity(generation::PatternDensity density) noexcept;
    [[nodiscard]] generation::PatternDensity patternDensity() const noexcept;

    void setPatternAccent(generation::PatternAccent accent) noexcept;
    [[nodiscard]] generation::PatternAccent patternAccent() const noexcept;

    void setPatternSwing(generation::PatternSwing swing) noexcept;
    [[nodiscard]] generation::PatternSwing patternSwing() const noexcept;

    void setPerformanceScene(std::uint8_t sceneIndex) noexcept;
    [[nodiscard]] std::uint8_t performanceScene() const noexcept;
    void requestPatternMutation() noexcept;
    void setNoteRepeat(generation::NoteRepeatRate rate) noexcept;
    [[nodiscard]] generation::NoteRepeatRate noteRepeat() const noexcept;
    void handleMidiController(const midi::MidiShortMessage& message) noexcept;

    [[nodiscard]] bool sendDiagnosticNote();

    [[nodiscard]] bool linkEnabled() const noexcept;
    [[nodiscard]] bool accompanimentEnabled() const noexcept;
    [[nodiscard]] clock::LinkClockSnapshot captureLinkSnapshot() const;

private:
    clock::LinkClock linkClock_{120.0, 4.0};
    musical::KeyContext keyContext_{};
    scheduler::MidiSendQueue sendQueue_;
    scheduler::AccompanimentScheduler scheduler_;
    midi::ControllerMapping controllerMapping_{};
    bool started_ = false;
};

} // namespace mozart::runtime
