#pragma once

#include "generation/PatternDensity.h"
#include "musical/MusicalNote.h"

#include <cstdint>
#include <vector>

namespace mozart::generation {

class DrumPatternGenerator final {
public:
    static constexpr std::uint8_t kMidiChannel = 9;
    static constexpr std::uint8_t kKick = 36;
    static constexpr std::uint8_t kSnare = 38;
    static constexpr std::uint8_t kClosedHiHat = 42;

    [[nodiscard]] static std::vector<musical::MusicalNoteEvent> generateBar(
            std::uint32_t seed,
            PatternDensity density);
};

} // namespace mozart::generation
