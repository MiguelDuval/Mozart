#pragma once

#include "clock/LinkClock.h"
#include "generation/BassGenerator.h"
#include "musical/KeyScale.h"
#include "scheduler/MidiSendQueue.h"

#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <mutex>
#include <thread>

namespace mozart::scheduler {

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

private:
    void run();
    void scheduleBar(
            const clock::LinkClockSnapshot& snapshot,
            const musical::KeyScale& keyScale,
            double barStartBeat);

    clock::LinkClock& clock_;
    MidiSendQueue& sendQueue_;

    mutable std::mutex stateMutex_;
    musical::KeyScale keyScale_{6, musical::Scale::NaturalMinor};

    std::atomic_bool running_{false};
    std::atomic_bool armed_{false};

    std::mutex wakeMutex_;
    std::condition_variable wakeCondition_;
    std::thread worker_;

    double scheduledBarStart_ = -1.0;
    std::uint32_t seed_ = 0x4D4F5A41u;
};

} // namespace mozart::scheduler
