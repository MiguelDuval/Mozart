#include "AudioKeyDetector.h"

#include <algorithm>
#include <array>
#include <cmath>

namespace mozart::musical {
namespace {

constexpr std::size_t kPitchClasses = 12;
constexpr std::size_t kCandidates = 24;

// Krumhansl key profiles, C-centered.
constexpr std::array<double, kPitchClasses> kKrumhanslMajor{
    6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
    2.52, 5.19, 2.39, 3.66, 2.29, 2.88
};

constexpr std::array<double, kPitchClasses> kKrumhanslMinor{
    6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
    2.54, 4.75, 3.98, 2.69, 3.34, 3.17
};

// Temperley's revised profiles, C-centered.
constexpr std::array<double, kPitchClasses> kTemperleyMajor{
    5.0, 2.0, 3.5, 2.0, 4.5, 4.0,
    2.0, 4.5, 2.0, 3.5, 1.5, 4.0
};

constexpr std::array<double, kPitchClasses> kTemperleyMinor{
    5.0, 2.0, 3.5, 4.5, 2.0, 4.0,
    2.0, 4.5, 3.5, 2.0, 1.5, 4.0
};

template <typename Profile>
std::array<double, kPitchClasses> rotateProfile(
        const Profile& profile,
        const std::size_t rootPitchClass) noexcept {
    std::array<double, kPitchClasses> rotated{};
    for (std::size_t pitchClass = 0; pitchClass < kPitchClasses; ++pitchClass) {
        const auto relativePitchClass =
                (pitchClass + kPitchClasses - rootPitchClass) % kPitchClasses;
        rotated[pitchClass] = profile[relativePitchClass];
    }
    return rotated;
}

} // namespace

AudioKeyDetectionResult AudioKeyDetector::estimate(
        const Chroma& chroma) noexcept {
    double energy = 0.0;
    for (const auto value : chroma) {
        if (!std::isfinite(value) || value < 0.0) {
            return {};
        }
        energy += value;
    }

    if (energy <= 1.0e-12) {
        return {};
    }

    double bestScore = -2.0;
    double runnerUpScore = -2.0;
    KeyScale bestKeyScale{};

    for (std::size_t root = 0; root < kPitchClasses; ++root) {
        const auto majorKrumhansl =
                rotateProfile(kKrumhanslMajor, root);
        const auto minorKrumhansl =
                rotateProfile(kKrumhanslMinor, root);
        const auto majorTemperley =
                rotateProfile(kTemperleyMajor, root);
        const auto minorTemperley =
                rotateProfile(kTemperleyMinor, root);

        const auto majorScore =
                0.5 * correlation(chroma, majorKrumhansl) +
                0.5 * correlation(chroma, majorTemperley);
        const auto minorScore =
                0.5 * correlation(chroma, minorKrumhansl) +
                0.5 * correlation(chroma, minorTemperley);

        const KeyScale majorKey(
                static_cast<std::uint8_t>(root),
                Scale::Major);
        const KeyScale minorKey(
                static_cast<std::uint8_t>(root),
                Scale::NaturalMinor);

        for (const auto& candidate : std::array{
                 std::pair<double, KeyScale>{majorScore, majorKey},
                 std::pair<double, KeyScale>{minorScore, minorKey}}) {
            if (candidate.first > bestScore) {
                runnerUpScore = bestScore;
                bestScore = candidate.first;
                bestKeyScale = candidate.second;
            } else if (candidate.first > runnerUpScore) {
                runnerUpScore = candidate.first;
            }
        }
    }

    if (!bestKeyScale.isValid()) {
        return {};
    }

    return AudioKeyDetectionResult{
        true,
        bestKeyScale,
        bestScore,
        runnerUpScore,
        normalizedConfidence(
                bestScore,
                runnerUpScore,
                kCandidates)
    };
}

double AudioKeyDetector::correlation(
        const Chroma& chroma,
        const std::array<double, 12>& profile) noexcept {
    double chromaMean = 0.0;
    double profileMean = 0.0;
    for (std::size_t i = 0; i < kPitchClasses; ++i) {
        chromaMean += chroma[i];
        profileMean += profile[i];
    }

    chromaMean /= static_cast<double>(kPitchClasses);
    profileMean /= static_cast<double>(kPitchClasses);

    double numerator = 0.0;
    double chromaEnergy = 0.0;
    double profileEnergy = 0.0;

    for (std::size_t i = 0; i < kPitchClasses; ++i) {
        const auto chromaCentered = chroma[i] - chromaMean;
        const auto profileCentered = profile[i] - profileMean;
        numerator += chromaCentered * profileCentered;
        chromaEnergy += chromaCentered * chromaCentered;
        profileEnergy += profileCentered * profileCentered;
    }

    const auto denominator =
            std::sqrt(chromaEnergy * profileEnergy);

    if (denominator <= 1.0e-12) {
        return 0.0;
    }

    return numerator / denominator;
}

double AudioKeyDetector::normalizedConfidence(
        const double bestScore,
        const double runnerUpScore,
        const std::size_t candidateCount) noexcept {
    if (candidateCount < 2) {
        return 0.0;
    }

    // This is a relative separation metric, not a calibrated probability.
    // A later temporal context layer will decide whether the estimate is
    // stable enough to change the active musical context.
    const auto margin = std::max(0.0, bestScore - runnerUpScore);
    const auto spread =
            std::max(1.0e-12, 1.0 - runnerUpScore);
    const auto raw =
            margin / spread;

    return std::clamp(raw, 0.0, 1.0);
}

} // namespace mozart::musical
