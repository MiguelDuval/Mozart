#pragma once

#include "generation/GenerationRequest.h"

#include <string_view>

namespace mozart::generation {

struct StyleProfile final {
    GenerationStyle style = GenerationStyle::Techno;
    std::string_view slug = "techno";
    std::string_view displayName = "Techno";

    GenerationSubstyle defaultSubstyle = GenerationSubstyle::Techno;
    GenerationMood defaultMood = GenerationMood::Driving;
    GenerationRhythm defaultRhythm = GenerationRhythm::Straight;

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
                        GenerationSubstyle::Generic,
                        GenerationMood::Atmospheric,
                        GenerationRhythm::Straight,
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
                        GenerationSubstyle::Techno,
                        GenerationMood::Driving,
                        GenerationRhythm::Straight,
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
                        GenerationSubstyle::DarkTechno,
                        GenerationMood::Dark,
                        GenerationRhythm::Straight,
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
                        GenerationSubstyle::HardTechno,
                        GenerationMood::Aggressive,
                        GenerationRhythm::Straight,
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
                        GenerationSubstyle::Trap,
                        GenerationMood::Hypnotic,
                        GenerationRhythm::HalfTime,
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
                        GenerationSubstyle::Custom,
                        GenerationMood::Custom,
                        GenerationRhythm::Custom,
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

    [[nodiscard]] static constexpr std::string_view substyleSlug(
            const GenerationSubstyle substyle) noexcept {
        switch (substyle) {
            case GenerationSubstyle::Generic: return "generic";
            case GenerationSubstyle::Techno: return "techno";
            case GenerationSubstyle::DarkTechno: return "dark_techno";
            case GenerationSubstyle::HardTechno: return "hard_techno";
            case GenerationSubstyle::Trap: return "trap";
            case GenerationSubstyle::DarkTrap: return "dark_trap";
            case GenerationSubstyle::Custom: return "custom";
        }
        return "custom";
    }

    [[nodiscard]] static constexpr GenerationSubstyle substyleFromSlug(
            const std::string_view value) noexcept {
        if (value == "generic") return GenerationSubstyle::Generic;
        if (value == "techno") return GenerationSubstyle::Techno;
        if (value == "dark_techno") return GenerationSubstyle::DarkTechno;
        if (value == "hard_techno") return GenerationSubstyle::HardTechno;
        if (value == "trap") return GenerationSubstyle::Trap;
        if (value == "dark_trap") return GenerationSubstyle::DarkTrap;
        return GenerationSubstyle::Custom;
    }

    [[nodiscard]] static constexpr bool isValidSubstyleSlug(
            const std::string_view value) noexcept {
        return substyleFromSlug(value) != GenerationSubstyle::Custom ||
                value == "custom";
    }

    [[nodiscard]] static constexpr std::string_view moodSlug(
            const GenerationMood mood) noexcept {
        switch (mood) {
            case GenerationMood::Neutral: return "neutral";
            case GenerationMood::Driving: return "driving";
            case GenerationMood::Dark: return "dark";
            case GenerationMood::Aggressive: return "aggressive";
            case GenerationMood::Hypnotic: return "hypnotic";
            case GenerationMood::Tense: return "tense";
            case GenerationMood::Atmospheric: return "atmospheric";
            case GenerationMood::Custom: return "custom";
        }
        return "custom";
    }

    [[nodiscard]] static constexpr GenerationMood moodFromSlug(
            const std::string_view value) noexcept {
        if (value == "neutral") return GenerationMood::Neutral;
        if (value == "driving") return GenerationMood::Driving;
        if (value == "dark") return GenerationMood::Dark;
        if (value == "aggressive") return GenerationMood::Aggressive;
        if (value == "hypnotic") return GenerationMood::Hypnotic;
        if (value == "tense") return GenerationMood::Tense;
        if (value == "atmospheric") return GenerationMood::Atmospheric;
        return GenerationMood::Custom;
    }

    [[nodiscard]] static constexpr bool isValidMoodSlug(
            const std::string_view value) noexcept {
        return moodFromSlug(value) != GenerationMood::Custom || value == "custom";
    }

    [[nodiscard]] static constexpr std::string_view rhythmSlug(
            const GenerationRhythm rhythm) noexcept {
        switch (rhythm) {
            case GenerationRhythm::Straight: return "straight";
            case GenerationRhythm::Syncopated: return "syncopated";
            case GenerationRhythm::Swing: return "swing";
            case GenerationRhythm::HalfTime: return "half_time";
            case GenerationRhythm::DoubleTime: return "double_time";
            case GenerationRhythm::Broken: return "broken";
            case GenerationRhythm::Custom: return "custom";
        }
        return "custom";
    }

    [[nodiscard]] static constexpr GenerationRhythm rhythmFromSlug(
            const std::string_view value) noexcept {
        if (value == "straight") return GenerationRhythm::Straight;
        if (value == "syncopated") return GenerationRhythm::Syncopated;
        if (value == "swing") return GenerationRhythm::Swing;
        if (value == "half_time") return GenerationRhythm::HalfTime;
        if (value == "double_time") return GenerationRhythm::DoubleTime;
        if (value == "broken") return GenerationRhythm::Broken;
        return GenerationRhythm::Custom;
    }

    [[nodiscard]] static constexpr bool isValidRhythmSlug(
            const std::string_view value) noexcept {
        return rhythmFromSlug(value) != GenerationRhythm::Custom ||
                value == "custom";
    }

    [[nodiscard]] static constexpr std::string_view roleSlug(
            const GenerationRole role) noexcept {
        switch (role) {
            case GenerationRole::Bass: return "bass";
            case GenerationRole::Arpeggio: return "arpeggio";
            case GenerationRole::Chords: return "chords";
            case GenerationRole::Lead: return "lead";
            case GenerationRole::Drums: return "drums";
            case GenerationRole::Percussion: return "percussion";
            case GenerationRole::Texture: return "texture";
            case GenerationRole::Custom: return "custom";
        }
        return "custom";
    }

    [[nodiscard]] static constexpr GenerationRole roleFromSlug(
            const std::string_view value) noexcept {
        if (value == "bass") return GenerationRole::Bass;
        if (value == "arpeggio") return GenerationRole::Arpeggio;
        if (value == "chords") return GenerationRole::Chords;
        if (value == "lead") return GenerationRole::Lead;
        if (value == "drums") return GenerationRole::Drums;
        if (value == "percussion") return GenerationRole::Percussion;
        if (value == "texture") return GenerationRole::Texture;
        return GenerationRole::Custom;
    }

    [[nodiscard]] static constexpr bool isValidRoleSlug(
            const std::string_view value) noexcept {
        return roleFromSlug(value) != GenerationRole::Custom || value == "custom";
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
        request.substyle = p.defaultSubstyle;
        request.mood = p.defaultMood;
        request.rhythm = p.defaultRhythm;
        request.energy = p.defaultEnergy;
        request.density = p.defaultDensity;
        request.syncopation = p.defaultSyncopation;
        request.swing = p.defaultSwing;
        request.variation = p.defaultVariation;
    }
};

} // namespace mozart::generation
