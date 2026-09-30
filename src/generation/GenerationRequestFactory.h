#pragma once

#include "generation/GenerationRequest.h"
#include "generation/PatternDensity.h"
#include "generation/PatternSwing.h"
#include "generation/StyleVocabulary.h"

namespace mozart::generation {

class GenerationRequestFactory final {
public:
    [[nodiscard]] static GenerationRequest fromPerformanceContext(
            const musical::KeyScale& keyScale,
            const double tempoBpm,
            const GenerationRole role,
            const PatternDensity density,
            const PatternSwing swing,
            const std::uint8_t energyControl,
            const std::uint32_t seed = 0x4D4F5A41u) noexcept {
        GenerationRequest request;
        request.style = GenerationStyle::Techno;
        StyleVocabulary::applyDefaults(request);

        request.keyScale = keyScale;
        request.tempoBpm = tempoBpm;
        request.role = role;
        request.density =
                static_cast<double>(densityPercent(density)) / 100.0;
        request.swing =
                swing == PatternSwing::Full
                        ? 1.0
                        : swing == PatternSwing::Light
                                ? 0.5
                                : 0.0;
        request.energy =
                static_cast<double>(energyControl) / 127.0;
        request.bars = 4;
        request.polyphony = 1;
        request.seed = seed;

        return request;
    }
};

} // namespace mozart::generation
