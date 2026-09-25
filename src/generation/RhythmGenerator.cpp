#include "RhythmGenerator.h"

#include <algorithm>

namespace mozart::generation {

std::vector<bool> RhythmGenerator::euclidean(
        std::size_t steps,
        std::size_t pulses,
        std::size_t rotation) {
    if (steps == 0) {
        return {};
    }

    pulses = std::min(pulses, steps);
    rotation %= steps;

    std::vector<bool> pattern(steps, false);

    if (pulses > 0) {
        for (std::size_t i = 0; i < steps; ++i) {
            pattern[i] = ((i * pulses) % steps) < pulses;
        }
    }

    if (rotation != 0) {
        std::rotate(pattern.begin(), pattern.begin() + rotation, pattern.end());
    }

    return pattern;
}

std::vector<std::uint8_t> RhythmGenerator::seededVelocityPattern(
        std::size_t steps,
        std::uint32_t seed) {
    std::vector<std::uint8_t> result;
    result.reserve(steps);

    auto state = seed == 0 ? 0x6D2B79F5u : seed;

    for (std::size_t i = 0; i < steps; ++i) {
        const auto value = static_cast<std::uint8_t>(80u + (next(state) % 48u));
        result.push_back(value);
    }

    return result;
}

std::uint32_t RhythmGenerator::next(std::uint32_t& state) noexcept {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    return state;
}

} // namespace mozart::generation
