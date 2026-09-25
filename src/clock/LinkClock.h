#pragma once

#include <chrono>
#include <cstddef>

#include <ableton/Link.hpp>

namespace mozart::clock {

struct LinkClockSnapshot {
    bool enabled = false;
    bool playing = false;
    bool inSession = false;
    std::size_t peers = 0;
    double tempoBpm = 120.0;
    double beat = 0.0;
    double phase = 0.0;
    double quantum = 4.0;
    std::chrono::microseconds hostTime{};
};

class LinkClock final {
public:
    explicit LinkClock(double initialTempoBpm = 120.0, double quantum = 4.0);

    LinkClock(const LinkClock&) = delete;
    LinkClock& operator=(const LinkClock&) = delete;
    LinkClock(LinkClock&&) = delete;
    LinkClock& operator=(LinkClock&&) = delete;

    void setEnabled(bool enabled) noexcept;
    [[nodiscard]] bool isEnabled() const noexcept;

    void enableStartStopSync(bool enabled) noexcept;
    [[nodiscard]] bool isStartStopSyncEnabled() const noexcept;

    [[nodiscard]] LinkClockSnapshot captureAppSnapshot() const;

private:
    ableton::Link link_;
    double quantum_;
};

} // namespace mozart::clock
