#include "Track.h"

#include <algorithm>

namespace mozart {

Track::Track(std::uint32_t id, std::string name)
    : id_(id), name_(std::move(name)) {}

void Track::setLevel(float level) noexcept {
    level_.store(std::clamp(level, 0.0f, 1.0f), std::memory_order_relaxed);
}

float Track::level() const noexcept {
    return level_.load(std::memory_order_relaxed);
}

void Track::setPan(float pan) noexcept {
    pan_.store(std::clamp(pan, -1.0f, 1.0f), std::memory_order_relaxed);
}

float Track::pan() const noexcept {
    return pan_.load(std::memory_order_relaxed);
}

void Track::setMuted(bool muted) noexcept {
    muted_.store(muted, std::memory_order_relaxed);
}

} // namespace mozart
