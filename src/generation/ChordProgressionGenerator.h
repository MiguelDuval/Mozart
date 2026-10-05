#pragma once

#include "musical/Chord.h"
#include "musical/KeyScale.h"

#include <cstddef>
#include <cstdint>
#include <vector>

namespace mozart::generation {

class ChordProgressionGenerator final {
public:
    // Generates one diatonic triad per bar. The seed selects a deterministic
    // progression family; no realtime or transport state is consulted.
    [[nodiscard]] static std::vector<musical::Chord> generate(
            const musical::KeyScale& keyScale,
            std::size_t bars,
            std::uint32_t seed = 0x4D4F5A41u) noexcept;

private:
    static std::uint32_t next(std::uint32_t& state) noexcept;
};

} // namespace mozart::generation
