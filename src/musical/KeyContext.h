#pragma once

#include "AudioKeyStabilityFilter.h"

#include <cstddef>
#include <cstdint>
#include <mutex>

namespace mozart::musical {

enum class KeyContextSource : std::uint8_t {
    Manual = 0,
    Audio = 1
};

struct KeyContextSnapshot final {
    KeyContextSource source = KeyContextSource::Manual;
    KeyScale resolvedKeyScale{};
    KeyScale manualKeyScale{};
    AudioKeyStabilitySnapshot audio{};
};

class KeyContext final {
public:
    explicit KeyContext(
            const KeyScale& initialManualKeyScale =
                    KeyScale{6, Scale::NaturalMinor},
            double minimumAudioConfidence = 0.10,
            std::size_t requiredAudioObservations = 3) noexcept;

    void setManualKeyScale(const KeyScale& keyScale);
    void setSource(KeyContextSource source) noexcept;

    // Feed one local audio-key estimate. The resolved context changes only
    // when the stability filter has accepted a stable candidate.
    void updateAudioDetection(
            const AudioKeyDetectionResult& result) noexcept;

    // Reset the audio candidate and use the manual context as the deterministic
    // fallback while waiting for a new stable audio estimate.
    void resetAudio() noexcept;

    [[nodiscard]] KeyContextSource source() const noexcept;
    [[nodiscard]] KeyScale resolvedKeyScale() const noexcept;
    [[nodiscard]] KeyContextSnapshot snapshot() const noexcept;

private:
    mutable std::mutex mutex_;
    KeyContextSource source_ = KeyContextSource::Manual;
    KeyScale manualKeyScale_{6, Scale::NaturalMinor};
    KeyScale resolvedKeyScale_{6, Scale::NaturalMinor};
    AudioKeyStabilityFilter audioFilter_;
};

} // namespace mozart::musical
