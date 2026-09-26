#pragma once

#include <cstdint>

namespace mozart::generation {

enum class PatternAccent : std::uint8_t {
    Off = 0,
    Mild = 1,
    Strong = 2
};

[[nodiscard]] constexpr std::uint8_t accentBoost(
        PatternAccent accent) noexcept {
    switch (accent) {
        case PatternAccent::Strong:
            return 20;
        case PatternAccent::Mild:
            return 10;
        case PatternAccent::Off:
        default:
            return 0;
    }
}

} // namespace mozart::generation
