#pragma once

#include "clock/LinkClock.h"
#include "generation/ArpeggioGenerator.h"
#include "generation/BassGenerator.h"
#include "generation/PatternDensity.h"
#include "musical/KeyScale.h"
#include "scheduler/MidiSendQueue.h"

#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <mutex>
#include <thread>

namespace mozart::scheduler {

enum class AccompanimentRole : std::uint8_t {
    Bass = 0,
    Arpeggio = 1
};

class AccompanimentScheduler final {
public:
    AccompanimentScheduler(
            clock::LinkClock& clock,
            MidiSendQueue& sendQueue);

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

private:
    void run();
    void scheduleEvent(
            const clock::LinkClockSnapshot& snapshot,
            const musical::MusicalNoteEvent& event,
            double startBeat);

    clock::LinkClock& clock_;
    MidiSendQueue& sendQueue_;

    mutable std::mutex stateMutex_;
    musical::KeyScale keyScale_{6, musical::Scale::NaturalMinor};

    std::atomic_bool running_{false};
    std::atomic_bool armed_{false};
    std::atomic<AccompanimentRole> requestedRole_{AccompanimentRole::Bass};
    std::atomic<generation::PatternDensity> requestedDensity_{
            generation::PatternDensity::Full};

    std::mutex wakeMutex_;
    std::condition_variable wakeCondition_;
    std::thread worker_;

    double launchBarStart_ = -1.0;
    std::int64_t nextBarIndex_ = 0;
    std::size_t nextEventIndex_ = 0;
    AccompanimentRole activeRole_ = AccompanimentRole::Bass;
    generation::PatternDensity activeDensity_ = generation::PatternDensity::Full;
    std::uint32_t seed_ = 0x4D4F5A41u;
};

} // namespace mozart::scheduler
