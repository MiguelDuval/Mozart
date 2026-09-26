#pragma once

#include <cstdint>

namespace mozart::generation {

enum class PatternDensity : std::uint8_t {
    Sparse = 50,
    Normal = 75,
    Full = 100
};

[[nodiscard]] constexpr std::uint8_t densityPercent(
        PatternDensity density) noexcept {
    return static_cast<std::uint8_t>(density);
}

} // namespace mozart::generation
