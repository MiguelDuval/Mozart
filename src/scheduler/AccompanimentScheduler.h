#pragma once

#include "clock/LinkClock.h"
#include "generation/ArpeggioGenerator.h"
#include "generation/PatternAccent.h"
#include "generation/BassGenerator.h"
#include "generation/PatternDensity.h"
#include "generation/NoteRepeat.h"
#include "generation/PatternSwing.h"
#include "generation/PatternProposal.h"
#include "musical/KeyScale.h"
#include "scheduler/MidiSendQueue.h"
#include "scheduler/AccompanimentRole.h"
#include "scheduler/PerformanceScene.h"
#include "scheduler/MacroControl.h"
#include "scheduler/TimingTelemetry.h"

#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <mutex>
#include <optional>
#include <thread>

namespace mozart::scheduler {

class AccompanimentScheduler final {
public:
    AccompanimentScheduler(
            clock::LinkClock& clock,
            MidiSendQueue& sendQueue,
            TimingTelemetry* telemetry = nullptr);

    ~AccompanimentScheduler();

    AccompanimentScheduler(const AccompanimentScheduler&) = delete;
    AccompanimentScheduler& operator=(const AccompanimentScheduler&) = delete;

    void start();
    void stop();

    void setArmed(bool armed) noexcept;
    [[nodiscard]] bool isArmed() const noexcept;

    void setKeyScale(const musical::KeyScale& keyScale);
    [[nodiscard]] musical::KeyScale keyScale() const;

    void setRole(AccompanimentRole role) noexcept;
    [[nodiscard]] AccompanimentRole role() const noexcept;

    void setDensity(generation::PatternDensity density) noexcept;
    [[nodiscard]] generation::PatternDensity density() const noexcept;

    void setAccent(generation::PatternAccent accent) noexcept;
    [[nodiscard]] generation::PatternAccent accent() const noexcept;

    void setSwing(generation::PatternSwing swing) noexcept;
    [[nodiscard]] generation::PatternSwing swing() const noexcept;

    void setScene(std::uint8_t sceneIndex) noexcept;
    [[nodiscard]] std::uint8_t scene() const noexcept;

    void requestMutation() noexcept;

    void setNoteRepeat(generation::NoteRepeatRate rate) noexcept;
    [[nodiscard]] generation::NoteRepeatRate noteRepeat() const noexcept;
    void setMacro(MacroControl control, std::uint8_t value) noexcept;
    [[nodiscard]] std::uint8_t macroEnergy() const noexcept;

    // A validated AI proposal is consumed only at a musical boundary. The
    // scheduler owns the active copy after the handoff and then returns to its
    // deterministic generator when the proposal cycle is complete.
    [[nodiscard]] bool queueGeneratedPattern(
            generation::PatternProposal proposal);
    [[nodiscard]] std::uint8_t macroMotion() const noexcept;

private:
    void run();
    void applyRequestedScene() noexcept;
    void scheduleEvent(
            const clock::LinkClockSnapshot& snapshot,
            const musical::MusicalNoteEvent& event,
            double startBeat);

    void activatePendingGeneratedPattern(double startBeat);

    clock::LinkClock& clock_;
    MidiSendQueue& sendQueue_;
    TimingTelemetry* telemetry_ = nullptr;

    // Serialize lifecycle transitions so stop() cannot race the worker
    // publication performed by start().
    mutable std::mutex lifecycleMutex_;
    mutable std::mutex stateMutex_;
    musical::KeyScale requestedKeyScale_{6, musical::Scale::NaturalMinor};
    musical::KeyScale activeKeyScale_{6, musical::Scale::NaturalMinor};

    std::atomic_bool running_{false};
    std::atomic_bool armed_{false};
    std::atomic<AccompanimentRole> requestedRole_{AccompanimentRole::Bass};
    std::atomic<generation::PatternDensity> requestedDensity_{
            generation::PatternDensity::Full};
    std::atomic<generation::PatternAccent> requestedAccent_{
            generation::PatternAccent::Off};
    std::atomic<generation::PatternSwing> requestedSwing_{
            generation::PatternSwing::Off};
    std::atomic<std::uint8_t> requestedScene_{0};
    std::atomic<std::uint8_t> activeScene_{0};
    std::atomic_bool mutationRequested_{false};
    std::atomic<generation::NoteRepeatRate> requestedNoteRepeat_{
            generation::NoteRepeatRate::Off};
    std::atomic<std::uint8_t> macroEnergy_{0};
    std::atomic<std::uint8_t> macroMotion_{0};

    std::mutex wakeMutex_;
    std::condition_variable wakeCondition_;
    std::thread worker_;

    double launchBarStart_ = -1.0;
    std::int64_t nextBarIndex_ = 0;
    std::size_t nextEventIndex_ = 0;
    AccompanimentRole activeRole_ = AccompanimentRole::Bass;
    generation::PatternDensity activeDensity_ = generation::PatternDensity::Full;
    generation::PatternAccent activeAccent_ = generation::PatternAccent::Off;
    generation::PatternSwing activeSwing_ = generation::PatternSwing::Off;
    generation::NoteRepeatRate activeNoteRepeat_ = generation::NoteRepeatRate::Off;
    std::uint32_t seed_ = 0x4D4F5A41u;

    std::mutex generatedPatternMutex_;
    std::optional<generation::PatternProposal> pendingGeneratedPattern_{};
    std::optional<generation::PatternProposal> activeGeneratedPattern_{};
    double activeGeneratedPatternStartBeat_ = -1.0;
};

} // namespace mozart::scheduler
