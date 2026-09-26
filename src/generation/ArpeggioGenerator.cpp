#include "ArpeggioGenerator.h"

#include <algorithm>
#include <array>

namespace mozart::generation {

std::vector<musical::MusicalNoteEvent> ArpeggioGenerator::generateBar(
        const musical::KeyScale& keyScale,
        const std::uint8_t baseOctave,
        const std::uint32_t seed,
        const std::uint8_t channel) {
    if (!keyScale.isValid() || channel > 15) {
        return {};
    }

    // One eighth-note arpeggio cell repeated over a four-beat bar.
    static constexpr std::array<double, 8> beats{
        0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5
    };

    static constexpr std::array<std::size_t, 8> degrees{
        0, 2, 4, 6, 4, 2, 1, 2
    };

    std::vector<musical::MusicalNoteEvent> result;
    result.reserve(beats.size());

    auto state = seed == 0 ? 0xA341316Cu : seed;

    for (std::size_t i = 0; i < beats.size(); ++i) {
        const auto randomValue = next(state);
        if (i != 0 &&
            (randomValue % 100u) >= densityPercent(density)) {
            continue;
        }

        const auto baseVelocity =
                static_cast<std::uint8_t>(76u + (randomValue % 40u));
        const auto accent =
                (i % 4 == 0)
                        ? accentBoost(accent)
                        : static_cast<std::uint8_t>(0);
        const auto velocity =
                static_cast<std::uint8_t>(
                        std::min(127u,
                                 static_cast<unsigned int>(baseVelocity) + accent));

        const double shiftedBeat =
                beats[i] +
                ((i % 2 == 1) ? swingOffsetBeats(swing) : 0.0);

        result.push_back(musical::MusicalNoteEvent{
            shiftedBeat,
            0.34,
            keyScale.degreeToMidiNote(degrees[i], baseOctave),
            velocity,
            channel
        });
    }

    for (std::size_t i = 0; i < result.size(); ++i) {
        const double nextBeat =
                i + 1 < result.size()
                        ? result[i + 1].startBeat
                        : 4.0;
        const double availableDuration = nextBeat - result[i].startBeat;
        result[i].durationBeats =
                std::min(
                        result[i].durationBeats,
                        std::max(0.05, availableDuration - 0.02));
    }

    return result;
}

std::uint32_t ArpeggioGenerator::next(std::uint32_t& state) noexcept {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    return state;
}

} // namespace mozart::generation
