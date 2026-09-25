#include "BassGenerator.h"

#include <array>

namespace mozart::generation {

std::vector<musical::MusicalNoteEvent> BassGenerator::generateBar(
        const musical::KeyScale& keyScale,
        const std::uint8_t baseOctave,
        const std::uint32_t seed,
        const std::uint8_t channel) {
    if (!keyScale.isValid() || channel > 15) {
        return {};
    }

    static constexpr std::array<double, 8> beats{
        0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5
    };

    static constexpr std::array<std::size_t, 8> degrees{
        0, 0, 4, 3, 0, 0, 2, 3
    };

    std::vector<musical::MusicalNoteEvent> result;
    result.reserve(beats.size());

    auto state = seed == 0 ? 0x9E3779B9u : seed;

    for (std::size_t i = 0; i < beats.size(); ++i) {
        const auto velocity =
                static_cast<std::uint8_t>(88u + (next(state) % 32u));

        result.push_back(musical::MusicalNoteEvent{
            beats[i],
            0.42,
            keyScale.degreeToMidiNote(degrees[i], baseOctave),
            velocity,
            channel
        });
    }

    return result;
}

std::uint32_t BassGenerator::next(std::uint32_t& state) noexcept {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    return state;
}

} // namespace mozart::generation
