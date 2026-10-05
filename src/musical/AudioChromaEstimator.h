#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace mozart::musical {

class AudioChromaEstimator final {
public:
    using Chroma = std::array<double, 12>;

    // Estimates pitch-class energy from a short mono PCM16 frame. The
    // estimator is offline/worker-side and never touches transport timing.
    [[nodiscard]] static Chroma estimate(
            const std::int16_t* samples,
            std::size_t sampleCount,
            std::uint32_t sampleRate) noexcept;
};

} // namespace mozart::musical
