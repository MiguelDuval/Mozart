#include "AudioChromaEstimator.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>

namespace mozart::musical {
namespace {

constexpr int kLowestMidiNote = 36;  // C2
constexpr int kHighestMidiNote = 84; // C6
constexpr double kPi = 3.141592653589793238462643383279502884;

[[nodiscard]] double goertzelPower(
        const std::int16_t* samples,
        const std::size_t sampleCount,
        const double frequency,
        const std::uint32_t sampleRate) noexcept {
    if (samples == nullptr ||
        sampleCount < 2 ||
        sampleRate == 0 ||
        frequency <= 0.0 ||
        frequency >= static_cast<double>(sampleRate) * 0.5) {
        return 0.0;
    }

    const auto bin = std::max(
            1.0,
            std::floor(
                    0.5 +
                    static_cast<double>(sampleCount) *
                            frequency /
                            static_cast<double>(sampleRate)));
    const auto omega =
            2.0 * kPi * bin / static_cast<double>(sampleCount);
    const auto coefficient = 2.0 * std::cos(omega);

    double previous = 0.0;
    double previousPrevious = 0.0;

    for (std::size_t i = 0; i < sampleCount; ++i) {
        const auto window =
                0.5 *
                (1.0 -
                 std::cos(
                         2.0 * kPi *
                         static_cast<double>(i) /
                         static_cast<double>(sampleCount - 1)));
        const auto sample =
                static_cast<double>(samples[i]) / 32768.0;
        const auto current =
                sample * window +
                coefficient * previous -
                previousPrevious;
        previousPrevious = previous;
        previous = current;
    }

    const auto power =
            previousPrevious * previousPrevious +
            previous * previous -
            coefficient * previous * previousPrevious;
    return std::max(0.0, power);
}

} // namespace

AudioChromaEstimator::Chroma AudioChromaEstimator::estimate(
        const std::int16_t* samples,
        const std::size_t sampleCount,
        const std::uint32_t sampleRate) noexcept {
    Chroma chroma{};

    if (samples == nullptr ||
        sampleCount < 32 ||
        sampleRate < 4000) {
        return chroma;
    }

    for (int midiNote = kLowestMidiNote;
         midiNote <= kHighestMidiNote;
         ++midiNote) {
        const auto frequency =
                440.0 *
                std::pow(
                        2.0,
                        (static_cast<double>(midiNote) - 69.0) / 12.0);
        const auto power =
                goertzelPower(
                        samples, sampleCount, frequency, sampleRate);

        chroma[static_cast<std::size_t>(midiNote % 12)] +=
                std::log1p(power);
    }

    const auto maxValue =
            *std::max_element(chroma.begin(), chroma.end());
    if (maxValue <= 1.0e-12) {
        return Chroma{};
    }

    for (auto& value : chroma) {
        value /= maxValue;
    }

    return chroma;
}

} // namespace mozart::musical
