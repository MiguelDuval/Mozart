#include "AudioKeyStabilityFilter.h"

#include <algorithm>

namespace mozart::musical {

AudioKeyStabilityFilter::AudioKeyStabilityFilter(
        const double minimumConfidence,
        const std::size_t requiredObservations) noexcept
    : minimumConfidence_(std::clamp(minimumConfidence, 0.0, 1.0)),
      requiredObservations_(std::max<std::size_t>(1, requiredObservations)) {}

void AudioKeyStabilityFilter::reset() noexcept {
    hasCandidate_ = false;
    candidateKey_ = KeyScale{12, Scale::Major};
    candidateConfidence_ = 0.0;
    consecutiveObservations_ = 0;
    hasStableKey_ = false;
    stableKey_ = KeyScale{12, Scale::Major};
    stableConfidence_ = 0.0;
}

void AudioKeyStabilityFilter::update(
        const AudioKeyDetectionResult& result) noexcept {
    if (!result.valid ||
        !result.keyScale.isValid() ||
        result.confidence < minimumConfidence_) {
        hasCandidate_ = false;
        candidateKey_ = KeyScale{};
        candidateConfidence_ = 0.0;
        consecutiveObservations_ = 0;
        return;
    }

    if (hasCandidate_ && sameKey(candidateKey_, result.keyScale)) {
        ++consecutiveObservations_;
        candidateConfidence_ = std::max(
                candidateConfidence_,
                result.confidence);
    } else {
        hasCandidate_ = true;
        candidateKey_ = result.keyScale;
        candidateConfidence_ = result.confidence;
        consecutiveObservations_ = 1;
    }

    if (consecutiveObservations_ >= requiredObservations_) {
        hasStableKey_ = true;
        stableKey_ = candidateKey_;
        stableConfidence_ = candidateConfidence_;
    }
}

AudioKeyStabilitySnapshot AudioKeyStabilityFilter::snapshot() const noexcept {
    return AudioKeyStabilitySnapshot{
        hasStableKey_,
        stableKey_,
        stableConfidence_,
        consecutiveObservations_
    };
}

bool AudioKeyStabilityFilter::sameKey(
        const KeyScale& first,
        const KeyScale& second) noexcept {
    return first.isValid() &&
           second.isValid() &&
           first.rootPitchClass() == second.rootPitchClass() &&
           first.scale() == second.scale();
}

} // namespace mozart::musical
