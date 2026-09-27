#pragma once

#include <cstdint>

namespace mozart::generation {

enum class PatternSwing : std::uint8_t {
    Off = 0,
    Light = 1,
    Full = 2
};

[[nodiscard]] constexpr double swingOffsetBeats(
        PatternSwing swing) noexcept {
    switch (swing) {
        case PatternSwing::Full:
            return 1.0 / 6.0;
        case PatternSwing::Light:
            return 1.0 / 12.0;
        case PatternSwing::Off:
        default:
            return 0.0;
    }
}

} // namespace mozart::generation
