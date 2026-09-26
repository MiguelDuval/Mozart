#pragma once

#include "PatternAccent.h"
#include "PatternDensity.h"
#include "PatternSwing.h"
#include "musical/KeyScale.h"
#include "musical/MusicalNote.h"

#include <cstdint>
#include <vector>

namespace mozart::generation {

class BassGenerator final {
public:
    [[nodiscard]] static std::vector<musical::MusicalNoteEvent> generateBar(
            const musical::KeyScale& keyScale,
            std::uint8_t baseOctave,
            std::uint32_t seed,
            std::uint8_t channel = 0,
            PatternDensity density = PatternDensity::Full,
            PatternAccent accent = PatternAccent::Off,
            PatternSwing swing = PatternSwing::Off);

private:
    static std::uint32_t next(std::uint32_t& state) noexcept;
};

} // namespace mozart::generation
