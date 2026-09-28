#pragma once

#include "musical/Chord.h"
#include "musical/KeyScale.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace mozart::generation {

enum class GenerationStyle : std::uint8_t {
    Electronic = 0,
    Techno = 1,
    DarkTechno = 2,
    HardTechno = 3,
    Trap = 4,
    Custom = 5
};

enum class GenerationSubstyle : std::uint8_t {
    Generic = 0,
    Techno = 1,
    DarkTechno = 2,
    HardTechno = 3,
    Trap = 4,
    DarkTrap = 5,
    Custom = 6
};

enum class GenerationMood : std::uint8_t {
    Neutral = 0,
    Driving = 1,
    Dark = 2,
    Aggressive = 3,
    Hypnotic = 4,
    Tense = 5,
    Atmospheric = 6,
    Custom = 7
};

enum class GenerationRhythm : std::uint8_t {
    Straight = 0,
    Syncopated = 1,
    Swing = 2,
    HalfTime = 3,
    DoubleTime = 4,
    Broken = 5,
    Custom = 6
};

enum class GenerationRole : std::uint8_t {
    Bass = 0,
    Arpeggio = 1,
    Chords = 2,
    Lead = 3,
    Drums = 4,
    Percussion = 5,
    Texture = 6,
    Custom = 7
};

struct GenerationRequest final {
    static constexpr std::uint8_t kMinBars = 1;
    static constexpr std::uint8_t kMaxBars = 16;
    static constexpr std::uint8_t kMinPolyphony = 1;
    static constexpr std::uint8_t kMaxPolyphony = 16;

    GenerationStyle style = GenerationStyle::Techno;
    GenerationSubstyle substyle = GenerationSubstyle::Techno;
    GenerationMood mood = GenerationMood::Driving;
    GenerationRhythm rhythm = GenerationRhythm::Straight;
    GenerationRole role = GenerationRole::Bass;
    musical::KeyScale keyScale{6, musical::Scale::NaturalMinor};
    std::vector<musical::Chord> chordProgression{};

    double tempoBpm = 120.0;
    std::uint8_t bars = 4;
    std::uint8_t polyphony = 1;
    std::uint8_t minNote = 36;
    std::uint8_t maxNote = 96;

    double density = 1.0;
    double energy = 0.5;
    double syncopation = 0.25;
    double swing = 0.0;
    double variation = 0.5;

    std::uint32_t seed = 0x4D4F5A41u;

    [[nodiscard]] bool isValid() const noexcept {
        const auto unitRange = [](const double value) noexcept {
            return std::isfinite(value) && value >= 0.0 && value <= 1.0;
        };

        const auto styleValid =
                static_cast<std::uint8_t>(style) <=
                        static_cast<std::uint8_t>(GenerationStyle::Custom);
        const auto substyleValid =
                static_cast<std::uint8_t>(substyle) <=
                        static_cast<std::uint8_t>(GenerationSubstyle::Custom);
        const auto moodValid =
                static_cast<std::uint8_t>(mood) <=
                        static_cast<std::uint8_t>(GenerationMood::Custom);
        const auto rhythmValid =
                static_cast<std::uint8_t>(rhythm) <=
                        static_cast<std::uint8_t>(GenerationRhythm::Custom);
        const auto roleValid =
                static_cast<std::uint8_t>(role) <=
                        static_cast<std::uint8_t>(GenerationRole::Custom);

        return styleValid &&
                substyleValid &&
                moodValid &&
                rhythmValid &&
                roleValid &&
                keyScale.isValid() &&
                std::isfinite(tempoBpm) &&
                tempoBpm >= 20.0 &&
                tempoBpm <= 300.0 &&
                bars >= kMinBars &&
                bars <= kMaxBars &&
                polyphony >= kMinPolyphony &&
                polyphony <= kMaxPolyphony &&
                minNote <= maxNote &&
                maxNote <= 127 &&
                density >= 0.0 &&
                density <= 1.0 &&
                unitRange(energy) &&
                unitRange(syncopation) &&
                unitRange(swing) &&
                unitRange(variation) &&
                chordProgression.size() <= static_cast<std::size_t>(bars) * 4U &&
                std::all_of(
                        chordProgression.begin(),
                        chordProgression.end(),
                        [](const auto& chord) { return chord.isValid(); });
    }
};

} // namespace mozart::generation
