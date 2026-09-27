#pragma once

#include "musical/MusicalNote.h"

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace mozart::generation {

struct PatternControlEvent final {
    double startBeat = 0.0;
    std::uint8_t channel = 0;
    std::uint8_t controller = 0;
    std::uint8_t value = 0;

    friend bool operator==(const PatternControlEvent&, const PatternControlEvent&) = default;
};

struct PatternProposalMetadata final {
    static constexpr std::uint16_t kSchemaVersion = 1;

    std::uint16_t schemaVersion = kSchemaVersion;
    std::uint32_t seed = 0;
    double confidence = 0.0;
    std::uint32_t generationTimeMs = 0;
    std::string generatorId = "unknown";

    friend bool operator==(const PatternProposalMetadata&, const PatternProposalMetadata&) = default;
};

struct PatternProposal final {
    static constexpr std::size_t kMaxNoteEvents = 4096;
    static constexpr std::size_t kMaxControlEvents = 1024;

    std::vector<musical::MusicalNoteEvent> noteEvents{};
    std::vector<PatternControlEvent> controlEvents{};
    PatternProposalMetadata metadata{};

    [[nodiscard]] bool isWellFormed() const noexcept {
        if (metadata.schemaVersion != PatternProposalMetadata::kSchemaVersion ||
            !std::isfinite(metadata.confidence) ||
            metadata.confidence < 0.0 ||
            metadata.confidence > 1.0 ||
            noteEvents.size() > kMaxNoteEvents ||
            controlEvents.size() > kMaxControlEvents) {
            return false;
        }

        for (const auto& event : noteEvents) {
            if (!std::isfinite(event.startBeat) ||
                !std::isfinite(event.durationBeats) ||
                event.startBeat < 0.0 ||
                event.durationBeats <= 0.0 ||
                event.note > 127 ||
                event.velocity > 127 ||
                event.channel > 15) {
                return false;
            }
        }

        for (const auto& event : controlEvents) {
            if (!std::isfinite(event.startBeat) ||
                event.startBeat < 0.0 ||
                event.channel > 15 ||
                event.controller > 127 ||
                event.value > 127) {
                return false;
            }
        }

        return true;
    }
};

} // namespace mozart::generation
