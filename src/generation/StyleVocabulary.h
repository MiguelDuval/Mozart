#pragma once

#include "generation/GenerationRequest.h"

#include <string_view>

namespace mozart::generation {

struct StyleProfile final {
    GenerationStyle style = GenerationStyle::Techno;
    std::string_view slug = "techno";
    std::string_view displayName = "Techno";

    double defaultEnergy = 0.6;
    double defaultDensity = 0.75;
    double defaultSyncopation = 0.25;
    double defaultSwing = 0.0;
    double defaultVariation = 0.5;
};

class StyleVocabulary final {
public:
    [[nodiscard]] static constexpr StyleProfile profile(
            const GenerationStyle style) noexcept {
        switch (style) {
            case GenerationStyle::Electronic:
                return {
                        GenerationStyle::Electronic,
                        "electronic",
                        "Electronic",
                        0.50,
                        0.60,
                        0.25,
                        0.05,
                        0.50
                };
            case GenerationStyle::Techno:
                return {
                        GenerationStyle::Techno,
                        "techno",
                        "Techno",
                        0.65,
                        0.78,
                        0.28,
                        0.00,
                        0.50
                };
            case GenerationStyle::DarkTechno:
                return {
                        GenerationStyle::DarkTechno,
                        "dark_techno",
                        "Dark Techno",
                        0.78,
                        0.82,
                        0.34,
                        0.00,
                        0.62
                };
            case GenerationStyle::HardTechno:
                return {
                        GenerationStyle::HardTechno,
                        "hard_techno",
                        "Hard Techno",
                        0.92,
                        0.94,
                        0.42,
                        0.00,
                        0.72
                };
            case GenerationStyle::Trap:
                return {
                        GenerationStyle::Trap,
                        "trap",
                        "Trap",
                        0.72,
                        0.64,
                        0.58,
                        0.10,
                        0.66
                };
            case GenerationStyle::Custom:
            default:
                return {
                        GenerationStyle::Custom,
                        "custom",
                        "Custom",
                        0.50,
                        0.50,
                        0.25,
                        0.00,
                        0.50
                };
        }
    }

    [[nodiscard]] static constexpr std::string_view slug(
            const GenerationStyle style) noexcept {
        return profile(style).slug;
    }

    [[nodiscard]] static constexpr std::string_view displayName(
            const GenerationStyle style) noexcept {
        return profile(style).displayName;
    }

    [[nodiscard]] static constexpr bool isValidSlug(
            const std::string_view value) noexcept {
        return fromSlug(value) != GenerationStyle::Custom || value == "custom";
    }

    [[nodiscard]] static constexpr GenerationStyle fromSlug(
            const std::string_view value) noexcept {
        if (value == "electronic") {
            return GenerationStyle::Electronic;
        }
        if (value == "techno") {
            return GenerationStyle::Techno;
        }
        if (value == "dark_techno") {
            return GenerationStyle::DarkTechno;
        }
        if (value == "hard_techno") {
            return GenerationStyle::HardTechno;
        }
        if (value == "trap") {
            return GenerationStyle::Trap;
        }
        return GenerationStyle::Custom;
    }

    static void applyDefaults(GenerationRequest& request) noexcept {
        const auto p = profile(request.style);
        request.energy = p.defaultEnergy;
        request.density = p.defaultDensity;
        request.syncopation = p.defaultSyncopation;
        request.swing = p.defaultSwing;
        request.variation = p.defaultVariation;
    }
};

} // namespace mozart::generation
