#pragma once

#include "musical/MusicalNote.h"

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace mozart::generation {

class PatternVariation final {
public:
    [[nodiscard]] static std::vector<musical::MusicalNoteEvent> apply(
            const std::vector<musical::MusicalNoteEvent>& input,
            const double probability,
            const std::uint8_t ratchet,
            const std::uint32_t seed) {
        if (!std::isfinite(probability) ||
            probability < 0.0 ||
            probability > 1.0 ||
            ratchet < 1 ||
            ratchet > 4) {
            return {};
        }

        std::vector<musical::MusicalNoteEvent> output;
        output.reserve(input.size() * ratchet);

        for (std::size_t index = 0; index < input.size(); ++index) {
            if (!keep(input[index], probability, seed, index)) {
                continue;
            }

            const auto& event = input[index];
            const auto count = static_cast<std::uint8_t>(ratchet);
            const double duration =
                    event.durationBeats / static_cast<double>(count);

            for (std::uint8_t step = 0; step < count; ++step) {
                auto repeated = event;
                repeated.startBeat +=
                        duration * static_cast<double>(step);
                repeated.durationBeats = duration;
                output.push_back(repeated);
            }
        }

        return output;
    }

private:
    [[nodiscard]] static bool keep(
            const musical::MusicalNoteEvent&,
            const double probability,
            const std::uint32_t seed,
            const std::size_t index) noexcept {
        if (probability <= 0.0) {
            return false;
        }
        if (probability >= 1.0) {
            return true;
        }

        std::uint32_t state =
                seed ^
                (0x9E3779B9u *
                 static_cast<std::uint32_t>(index + 1U));
        state ^= state >> 16U;
        state *= 0x85EBCA6Bu;
        state ^= state >> 13U;
        state *= 0xC2B2AE35u;
        state ^= state >> 16U;

        const double unit =
                static_cast<double>(state) /
                static_cast<double>(UINT32_MAX);
        return unit < probability;
    }
};

} // namespace mozart::generation
