#pragma once

#include "AudioKeyDetector.h"

#include <cstddef>

namespace mozart::musical {

struct AudioKeyStabilitySnapshot final {
    bool hasStableKey = false;
    KeyScale keyScale{};
    double confidence = 0.0;
    std::size_t consecutiveObservations = 0;
};

class AudioKeyStabilityFilter final {
public:
    explicit AudioKeyStabilityFilter(
            double minimumConfidence = 0.10,
            std::size_t requiredObservations = 3) noexcept;

    void reset() noexcept;

    // Accepts one detector estimate. A key becomes stable only after the same
    // valid candidate has been observed repeatedly with sufficient confidence.
    void update(const AudioKeyDetectionResult& result) noexcept;

    [[nodiscard]] AudioKeyStabilitySnapshot snapshot() const noexcept;

private:
    static bool sameKey(
            const KeyScale& first,
            const KeyScale& second) noexcept;

    double minimumConfidence_;
    std::size_t requiredObservations_;
    bool hasCandidate_ = false;
    KeyScale candidateKey_{12, Scale::Major};
    double candidateConfidence_ = 0.0;
    std::size_t consecutiveObservations_ = 0;
    bool hasStableKey_ = false;
    KeyScale stableKey_{12, Scale::Major};
    double stableConfidence_ = 0.0;
};

} // namespace mozart::musical
