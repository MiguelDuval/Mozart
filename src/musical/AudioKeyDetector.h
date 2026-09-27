#pragma once

#include "KeyScale.h"

#include <array>
#include <cstddef>

namespace mozart::musical {

struct AudioKeyDetectionResult final {
    bool valid = false;
    KeyScale keyScale{};
    double score = 0.0;
    double runnerUpScore = 0.0;
    double confidence = 0.0;
};

class AudioKeyDetector final {
public:
    using Chroma = std::array<double, 12>;

    // Estimates Major or Natural Minor from a normalized 12-bin chroma vector.
    // The detector is intentionally stateless: audio capture, temporal
    // smoothing, and hysteresis belong to higher layers.
    [[nodiscard]] static AudioKeyDetectionResult estimate(
            const Chroma& chroma) noexcept;

private:
    [[nodiscard]] static double correlation(
            const Chroma& chroma,
            const std::array<double, 12>& profile) noexcept;

    [[nodiscard]] static double normalizedConfidence(
            double bestScore,
            double runnerUpScore,
            std::size_t candidateCount) noexcept;
};

} // namespace mozart::musical
