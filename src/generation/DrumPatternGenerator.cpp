#include "generation/DrumPatternGenerator.h"

#include "generation/RhythmGenerator.h"

#include <algorithm>
#include <cstddef>

namespace mozart::generation {

namespace {

[[nodiscard]] double stepBeat(const std::size_t step) noexcept {
    return static_cast<double>(step) * 0.25;
}

void appendHit(
        std::vector<musical::MusicalNoteEvent>& events,
        const std::size_t step,
        const std::uint8_t note,
        const std::uint8_t velocity,
        const double durationBeats) {
    events.push_back({
            stepBeat(step),
            durationBeats,
            note,
            velocity,
            DrumPatternGenerator::kMidiChannel
    });
}

} // namespace

std::vector<musical::MusicalNoteEvent> DrumPatternGenerator::generateBar(
        const std::uint32_t seed,
        const PatternDensity density) {
    const auto densityValue = densityPercent(density);
    const std::size_t kickCount =
            densityValue >= 100 ? 4 :
            densityValue >= 75 ? 3 : 2;
    const std::size_t hatStride =
            densityValue >= 100 ? 2 : 4;

    std::vector<musical::MusicalNoteEvent> events;
    events.reserve(14);

    const auto velocities = RhythmGenerator::seededVelocityPattern(16, seed);

    constexpr std::size_t kickSteps[4] = {0, 4, 8, 12};
    for (std::size_t i = 0; i < kickCount; ++i) {
        const auto step = kickSteps[i];
        appendHit(events, step, kKick, velocities[step], 0.20);
    }

    constexpr std::size_t snareSteps[2] = {4, 12};
    const std::size_t snareCount = densityValue >= 50 ? 2 : 1;
    for (std::size_t i = 0; i < snareCount; ++i) {
        const auto step = snareSteps[i];
        appendHit(events, step, kSnare, velocities[step], 0.20);
    }

    for (std::size_t step = 0; step < 16; step += hatStride) {
        const auto hatVelocity =
                static_cast<std::uint8_t>(
                        std::max(1u, static_cast<unsigned>(velocities[step]) - 20u));
        appendHit(events, step, kClosedHiHat, hatVelocity, 0.12);
    }

    return events;
}

} // namespace mozart::generation
