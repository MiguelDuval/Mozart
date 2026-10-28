#include "RemiToLinkPatternConverter.h"

#include <type_traits>

namespace mozart::generation {

RemiToLinkPatternConverter::RemiToLinkPatternConverter(std::uint32_t ticksPerBeat) noexcept
    : ticksPerBeat_(ticksPerBeat) {}

std::optional<musical::MusicalNoteEvent> RemiToLinkPatternConverter::convertNote(
        const remi::NoteEvent& note) const noexcept {
    if (note.pitch > 127 || note.velocity > 127 || note.channel > 15 ||
        note.duration == 0 || ticksPerBeat_ == 0) {
        return std::nullopt;
    }

    musical::MusicalNoteEvent result;
    result.startBeat = static_cast<double>(note.position) / static_cast<double>(ticksPerBeat_);
    result.durationBeats = static_cast<double>(note.duration) / static_cast<double>(ticksPerBeat_);
    result.note = note.pitch;
    result.velocity = note.velocity;
    result.channel = note.channel;

    return result;
}

std::optional<PatternControlEvent> RemiToLinkPatternConverter::convertControl(
        const remi::ControlChangeEvent& cc) const noexcept {
    if (cc.channel > 15 || cc.controller > 127 || cc.value > 127 || ticksPerBeat_ == 0) {
        return std::nullopt;
    }

    PatternControlEvent result;
    result.startBeat = static_cast<double>(cc.position) / static_cast<double>(ticksPerBeat_);
    result.channel = cc.channel;
    result.controller = cc.controller;
    result.value = cc.value;

    return result;
}

std::optional<PatternProposal> RemiToLinkPatternConverter::convert(
        const remi::PatternProposal& remiProposal) const noexcept {
    if (ticksPerBeat_ == 0 || !remiProposal.isValid()) {
        return std::nullopt;
    }

    // Validate every event before converting any of them. This ensures that
    // malformed proposals are rejected as a whole instead of silently
    // dropping invalid events and scheduling a partial pattern.
    const remi::PatternProposalValidator validator;
    if (!validator.validate(remiProposal).isOk()) {
        return std::nullopt;
    }

    PatternProposal linkProposal;
    linkProposal.metadata.schemaVersion = PatternProposalMetadata::kSchemaVersion;
    linkProposal.metadata.seed = remiProposal.seed;
    linkProposal.metadata.confidence = 1.0;
    linkProposal.metadata.generationTimeMs =
        static_cast<std::uint32_t>(remiProposal.generationTime.count() / 1000000ULL);
    linkProposal.metadata.lengthBeats =
        static_cast<double>(remiProposal.totalTicks) / static_cast<double>(ticksPerBeat_);
    linkProposal.metadata.generatorId = remiProposal.providerId.empty()
        ? "remi-bpe"
        : remiProposal.providerId;

    bool conversionFailed = false;
    bool unsupportedProgramChange = false;

    for (const auto& event : remiProposal.events) {
        std::visit([&](const auto& e) {
            using T = std::decay_t<decltype(e)>;

            if constexpr (std::is_same_v<T, remi::NoteEvent>) {
                const auto note = convertNote(e);
                if (note.has_value()) {
                    linkProposal.noteEvents.push_back(*note);
                } else {
                    conversionFailed = true;
                }
            } else if constexpr (std::is_same_v<T, remi::ControlChangeEvent>) {
                const auto control = convertControl(e);
                if (control.has_value()) {
                    linkProposal.controlEvents.push_back(*control);
                } else {
                    conversionFailed = true;
                }
            } else if constexpr (std::is_same_v<T, remi::ProgramChangeEvent>) {
                // The Link scheduler proposal currently has no program-change
                // representation. Reject instead of silently losing instrument
                // changes while scheduling the remaining notes.
                unsupportedProgramChange = true;
            }
            // Tempo and time-signature events are proposal metadata here.
            // The active Ableton Link session owns clock tempo and phase;
            // this converter does not publish a competing tempo timeline.
        }, event);
    }

    if (conversionFailed || unsupportedProgramChange ||
        (linkProposal.noteEvents.empty() && linkProposal.controlEvents.empty()) ||
        !linkProposal.isWellFormed()) {
        return std::nullopt;
    }

    return linkProposal;
}

} // namespace mozart::generation
