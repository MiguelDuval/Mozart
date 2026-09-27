#include "VoiceLeading.h"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdlib>
#include <limits>
#include <vector>

namespace mozart::musical {
namespace {

using Voicing = std::vector<std::uint8_t>;

constexpr int kOctaveTransposeMin = -2;
constexpr int kOctaveTransposeMax = 2;

[[nodiscard]] bool inRange(
        const Voicing& voicing,
        const VoiceLeadingOptions& options) noexcept {
    if (voicing.empty()) {
        return false;
    }

    return std::all_of(
            voicing.begin(),
            voicing.end(),
            [&options](const std::uint8_t note) {
                return note >= options.minNote && note <= options.maxNote;
            });
}

[[nodiscard]] Voicing makeVoicing(
        const Chord& chord,
        const std::size_t inversion,
        const int octaveTranspose,
        const VoiceLeadingOptions& options) {
    const auto count = chord.noteCount();
    Voicing voicing;
    voicing.reserve(count);

    for (std::size_t voice = 0; voice < count; ++voice) {
        const auto sourceIndex = (inversion + voice) % count;
        const auto pitchClass = chord.pitchClassAt(sourceIndex);

        int octave = static_cast<int>(options.baseOctave) + octaveTranspose;
        if (!voicing.empty() &&
                pitchClass <= static_cast<std::uint8_t>(voicing.back() % 12)) {
            ++octave;
        }

        const int note =
                12 * (octave + 1) + static_cast<int>(pitchClass);

        if (note < 0 || note > 127) {
            return {};
        }

        voicing.push_back(static_cast<std::uint8_t>(note));
    }

    return voicing;
}

[[nodiscard]] long long firstVoicingCost(
        const Voicing& voicing,
        const VoiceLeadingOptions& options,
        const std::size_t inversion) noexcept {
    const double center =
            (static_cast<double>(options.minNote) +
             static_cast<double>(options.maxNote)) * 0.5;

    long long cost = 0;
    for (const auto note : voicing) {
        cost += static_cast<long long>(
                std::llabs(static_cast<long long>(note) -
                           static_cast<long long>(center)));
    }

    // Prefer root position on exact ties, keeping the opening voicing stable.
    cost = cost * 16 + static_cast<long long>(inversion);
    return cost;
}

[[nodiscard]] long long transitionCost(
        const Voicing& previous,
        const Voicing& candidate) noexcept {
    const auto voices = std::min(previous.size(), candidate.size());

    long long cost = 0;
    for (std::size_t i = 0; i < voices; ++i) {
        cost += std::llabs(
                static_cast<long long>(previous[i]) -
                static_cast<long long>(candidate[i]));
    }

    if (previous.size() != candidate.size()) {
        const auto missing = previous.size() > candidate.size()
                ? previous.size() - candidate.size()
                : candidate.size() - previous.size();
        cost += static_cast<long long>(missing) * 36;
    }

    // Secondary penalty discourages octave-wide outer-voice jumps when
    // multiple candidates have the same aggregate movement.
    if (!candidate.empty()) {
        cost += static_cast<long long>(
                std::llabs(
                        static_cast<long long>(candidate.front()) -
                        static_cast<long long>(previous.front())) / 2);
        cost += static_cast<long long>(
                std::llabs(
                        static_cast<long long>(candidate.back()) -
                        static_cast<long long>(previous.back())) / 2);
    }

    return cost;
}

[[nodiscard]] bool lexicographicallyLess(
        const Voicing& lhs,
        const Voicing& rhs) noexcept {
    return std::lexicographical_compare(
            lhs.begin(),
            lhs.end(),
            rhs.begin(),
            rhs.end());
}

} // namespace

std::vector<std::vector<std::uint8_t>> VoiceLeading::generate(
        const std::vector<Chord>& progression,
        const VoiceLeadingOptions& options) noexcept {
    std::vector<Voicing> result;

    if (progression.empty() ||
            options.minNote > options.maxNote ||
            options.maxNote > 127) {
        return result;
    }

    for (const auto& chord : progression) {
        if (!chord.isValid() || chord.noteCount() == 0) {
            return {};
        }
    }

    result.reserve(progression.size());

    for (std::size_t chordIndex = 0; chordIndex < progression.size();
            ++chordIndex) {
        const auto& chord = progression[chordIndex];
        Voicing best;
        long long bestCost = std::numeric_limits<long long>::max();

        for (std::size_t inversion = 0;
                inversion < chord.noteCount();
                ++inversion) {
            for (int octaveTranspose = kOctaveTransposeMin;
                    octaveTranspose <= kOctaveTransposeMax;
                    ++octaveTranspose) {
                const auto candidate =
                        makeVoicing(
                                chord,
                                inversion,
                                octaveTranspose,
                                options);
                if (!inRange(candidate, options)) {
                    continue;
                }

                const long long cost =
                        chordIndex == 0
                        ? firstVoicingCost(
                                  candidate, options, inversion)
                        : transitionCost(result.back(), candidate);

                if (best.empty() ||
                        cost < bestCost ||
                        (cost == bestCost &&
                         lexicographicallyLess(candidate, best))) {
                    best = candidate;
                    bestCost = cost;
                }
            }
        }

        if (best.empty()) {
            return {};
        }

        result.push_back(std::move(best));
    }

    return result;
}

} // namespace mozart::musical
