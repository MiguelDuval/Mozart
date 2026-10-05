#include "ChordProgressionGenerator.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace mozart::generation {
namespace {

constexpr std::array<std::array<std::size_t, 4>, 3> kMajorFamilies{{
    {{0, 5, 3, 4}}, // I vi IV V
    {{1, 4, 0, 5}}, // ii V I vi
    {{0, 4, 5, 3}}  // I V vi IV
}};

constexpr std::array<std::array<std::size_t, 4>, 3> kMinorFamilies{{
    {{0, 5, 2, 6}}, // i VI III VII
    {{0, 3, 5, 6}}, // i iv VI VII
    {{0, 5, 3, 4}}  // i VI iv v
}};

constexpr std::array<std::array<std::size_t, 4>, 3> kDorianFamilies{{
    {{0, 3, 6, 2}}, // i IV VII III
    {{0, 4, 3, 6}}, // i v IV VII
    {{0, 3, 4, 6}}  // i IV v VII
}};

constexpr std::array<musical::ChordQuality, 7> kMajorQualities{
    musical::ChordQuality::Major,
    musical::ChordQuality::Minor,
    musical::ChordQuality::Minor,
    musical::ChordQuality::Major,
    musical::ChordQuality::Major,
    musical::ChordQuality::Minor,
    musical::ChordQuality::Diminished
};

constexpr std::array<musical::ChordQuality, 7> kMinorQualities{
    musical::ChordQuality::Minor,
    musical::ChordQuality::Diminished,
    musical::ChordQuality::Major,
    musical::ChordQuality::Minor,
    musical::ChordQuality::Minor,
    musical::ChordQuality::Major,
    musical::ChordQuality::Major
};

constexpr std::array<musical::ChordQuality, 7> kDorianQualities{
    musical::ChordQuality::Minor,
    musical::ChordQuality::Minor,
    musical::ChordQuality::Major,
    musical::ChordQuality::Major,
    musical::ChordQuality::Minor,
    musical::ChordQuality::Diminished,
    musical::ChordQuality::Major
};

[[nodiscard]] const auto& familiesFor(
        const musical::Scale scale) noexcept {
    switch (scale) {
        case musical::Scale::NaturalMinor:
            return kMinorFamilies;
        case musical::Scale::Dorian:
            return kDorianFamilies;
        case musical::Scale::Major:
        default:
            return kMajorFamilies;
    }
}

[[nodiscard]] const auto& qualitiesFor(
        const musical::Scale scale) noexcept {
    switch (scale) {
        case musical::Scale::NaturalMinor:
            return kMinorQualities;
        case musical::Scale::Dorian:
            return kDorianQualities;
        case musical::Scale::Major:
        default:
            return kMajorQualities;
    }
}

} // namespace

std::vector<musical::Chord> ChordProgressionGenerator::generate(
        const musical::KeyScale& keyScale,
        const std::size_t bars,
        std::uint32_t seed) noexcept {
    std::vector<musical::Chord> progression;

    if (!keyScale.isValid() || bars == 0) {
        return progression;
    }

    const auto& families = familiesFor(keyScale.scale());
    const auto& qualities = qualitiesFor(keyScale.scale());

    seed = next(seed);
    const auto familyIndex =
            static_cast<std::size_t>(seed % families.size());
    const auto& family = families[familyIndex];

    progression.reserve(bars);
    for (std::size_t bar = 0; bar < bars; ++bar) {
        const auto degree = family[bar % family.size()];
        const auto root =
                keyScale.degreeToMidiNote(degree, 0) % 12;
        progression.emplace_back(
                root,
                qualities[degree]);
    }

    return progression;
}

std::uint32_t ChordProgressionGenerator::next(
        std::uint32_t& state) noexcept {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    return state;
}

} // namespace mozart::generation
