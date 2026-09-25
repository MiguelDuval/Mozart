#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace mozart::generation {

class RhythmGenerator final {
public:
    [[nodiscard]] static std::vector<bool> euclidean(
            std::size_t steps,
            std::size_t pulses,
            std::size_t rotation = 0);

    [[nodiscard]] static std::vector<std::uint8_t> seededVelocityPattern(
            std::size_t steps,
            std::uint32_t seed);

private:
    static std::uint32_t next(std::uint32_t& state) noexcept;
};

} // namespace mozart::generation
