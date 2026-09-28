#pragma once

#include "generation/GenerationRequest.h"
#include "musical/MusicalNote.h"

#include <algorithm>

#include <cmath>
#include <optional>
#include <cstddef>
#include <cstdint>
#include <string>
#include <utility>
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

    friend bool operator==(const PatternProposal&, const PatternProposal&) = default;

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



enum class PatternValidationStatus : std::uint8_t {
    Ok = 0,
    InvalidRequest = 1,
    InvalidProposal = 2,
    NoUsableEvents = 3
};

struct PatternValidationResult final {
    PatternValidationStatus status = PatternValidationStatus::InvalidProposal;
    PatternProposal proposal{};
    std::string message{};

    [[nodiscard]] bool ok() const noexcept {
        return status == PatternValidationStatus::Ok && proposal.isWellFormed();
    }
};

class PatternProposalValidator final {
public:
    [[nodiscard]] static PatternValidationResult validate(
            const GenerationRequest& request,
            const PatternProposal& input) {
        if (!request.isValid()) {
            return {
                    PatternValidationStatus::InvalidRequest,
                    {},
                    "generation request is invalid"
            };
        }

        if (!input.isWellFormed()) {
            return {
                    PatternValidationStatus::InvalidProposal,
                    {},
                    "pattern proposal is malformed"
            };
        }

        PatternProposal output = input;
        const double patternLengthBeats =
                static_cast<double>(request.bars) * 4.0;

        for (const auto& event : output.noteEvents) {
            if (event.startBeat >= patternLengthBeats ||
                event.startBeat + event.durationBeats > patternLengthBeats) {
                return {
                        PatternValidationStatus::InvalidProposal,
                        {},
                        "note event falls outside requested pattern length"
                };
            }
        }

        for (const auto& event : output.controlEvents) {
            if (event.startBeat >= patternLengthBeats) {
                return {
                        PatternValidationStatus::InvalidProposal,
                        {},
                        "control event falls outside requested pattern length"
                };
            }
        }

        // Canonicalize pitch/velocity before enforcing musical constraints.
        for (auto& event : output.noteEvents) {
            const auto projected =
                    nearestScaleNote(
                            event.note,
                            request.minNote,
                            request.maxNote,
                            request.keyScale);
            if (!projected.has_value()) {
                return {
                        PatternValidationStatus::NoUsableEvents,
                        {},
                        "note cannot be represented inside the requested key/pitch range"
                };
            }
            event.note = *projected;
            if (event.velocity == 0) {
                event.velocity = 1;
            }
        }

        canonicalizeNotes(output.noteEvents);
        canonicalizeControls(output.controlEvents);
        enforcePolyphony(output.noteEvents, request.polyphony);

        const auto maxDenseEvents =
                static_cast<std::size_t>(
                        std::ceil(
                                patternLengthBeats *
                                4.0 *
                                request.density *
                                static_cast<double>(request.polyphony)));
        if (output.noteEvents.size() > maxDenseEvents) {
            output.noteEvents.resize(maxDenseEvents);
        }

        if (output.noteEvents.empty() && output.controlEvents.empty() &&
            request.density > 0.0 &&
            request.probability > 0.0) {
            return {
                    PatternValidationStatus::NoUsableEvents,
                    {},
                    "proposal contains no usable events after validation"
            };
        }

        if (!output.isWellFormed()) {
            return {
                    PatternValidationStatus::InvalidProposal,
                    {},
                    "validated proposal is malformed"
            };
        }

        return {
                PatternValidationStatus::Ok,
                std::move(output),
                {}
        };
    }

private:
    [[nodiscard]] static std::optional<std::uint8_t> nearestScaleNote(
            const std::uint8_t note,
            const std::uint8_t minNote,
            const std::uint8_t maxNote,
            const musical::KeyScale& keyScale) {
        const int center = static_cast<int>(note);
        for (int distance = 0; distance <= 127; ++distance) {
            const int lower = center - distance;
            if (lower >= static_cast<int>(minNote) &&
                lower <= static_cast<int>(maxNote) &&
                keyScale.containsMidiNote(
                        static_cast<std::uint8_t>(lower))) {
                return static_cast<std::uint8_t>(lower);
            }

            if (distance == 0) {
                continue;
            }

            const int upper = center + distance;
            if (upper >= static_cast<int>(minNote) &&
                upper <= static_cast<int>(maxNote) &&
                keyScale.containsMidiNote(
                        static_cast<std::uint8_t>(upper))) {
                return static_cast<std::uint8_t>(upper);
            }
        }

        return std::nullopt;
    }

    static void canonicalizeNotes(
            std::vector<musical::MusicalNoteEvent>& events) {
        std::stable_sort(
                events.begin(),
                events.end(),
                [](const auto& a, const auto& b) {
                    if (a.startBeat != b.startBeat) {
                        return a.startBeat < b.startBeat;
                    }
                    if (a.note != b.note) {
                        return a.note < b.note;
                    }
                    if (a.channel != b.channel) {
                        return a.channel < b.channel;
                    }
                    if (a.durationBeats != b.durationBeats) {
                        return a.durationBeats < b.durationBeats;
                    }
                    return a.velocity < b.velocity;
                });

        events.erase(
                std::unique(
                        events.begin(),
                        events.end(),
                        [](const auto& a, const auto& b) {
                            return a.startBeat == b.startBeat &&
                                    a.durationBeats == b.durationBeats &&
                                    a.note == b.note &&
                                    a.velocity == b.velocity &&
                                    a.channel == b.channel;
                        }),
                events.end());
    }

    static void canonicalizeControls(
            std::vector<PatternControlEvent>& events) {
        std::stable_sort(
                events.begin(),
                events.end(),
                [](const auto& a, const auto& b) {
                    if (a.startBeat != b.startBeat) {
                        return a.startBeat < b.startBeat;
                    }
                    if (a.channel != b.channel) {
                        return a.channel < b.channel;
                    }
                    if (a.controller != b.controller) {
                        return a.controller < b.controller;
                    }
                    return a.value < b.value;
                });

        events.erase(
                std::unique(
                        events.begin(),
                        events.end(),
                        [](const auto& a, const auto& b) {
                            return a.startBeat == b.startBeat &&
                                    a.channel == b.channel &&
                                    a.controller == b.controller &&
                                    a.value == b.value;
                        }),
                events.end());
    }

    static void enforcePolyphony(
            std::vector<musical::MusicalNoteEvent>& events,
            const std::uint8_t maxPolyphony) {
        if (events.empty()) {
            return;
        }

        std::vector<musical::MusicalNoteEvent> accepted;
        accepted.reserve(events.size());

        for (const auto& candidate : events) {
            std::size_t activeCount = 0;
            for (const auto& active : accepted) {
                if (active.startBeat + active.durationBeats >
                        candidate.startBeat) {
                    ++activeCount;
                    if (activeCount >=
                            static_cast<std::size_t>(maxPolyphony)) {
                        break;
                    }
                }
            }

            if (activeCount < static_cast<std::size_t>(maxPolyphony)) {
                accepted.push_back(candidate);
            }
        }

        events = std::move(accepted);
    }
};

} // namespace mozart::generation
