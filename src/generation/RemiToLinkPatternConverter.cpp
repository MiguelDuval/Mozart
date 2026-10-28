#include "RemiToLinkPatternConverter.h"

#include <cmath>
#include <limits>

namespace mozart::generation {

RemiToLinkPatternConverter::RemiToLinkPatternConverter(std::uint32_t ticksPerBeat) noexcept
    : ticksPerBeat_(ticksPerBeat) {}

std::optional<musical::MusicalNoteEvent> RemiToLinkPatternConverter::convertNote(
        const remi::NoteEvent& note) const noexcept {
    if (note.pitch > 127 || note.velocity > 127 || note.channel > 15) {
        return std::nullopt;
    }
    if (ticksPerBeat_ == 0) {
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
    if (cc.channel > 15 || cc.controller > 127 || cc.value > 127) {
        return std::nullopt;
    }
    if (ticksPerBeat_ == 0) {
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

    if (!remiProposal.isValid()) {
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

    for (const auto& event : remiProposal.events) {
        std::visit([&](const auto& e) {
            using T = std::decay_t<decltype(e)>;

            if constexpr (std::is_same_v<T, remi::NoteEvent>) {
                auto note = convertNote(e);
                if (note.has_value()) {
                    linkProposal.noteEvents.push_back(*note);
                }
            } else if constexpr (std::is_same_v<T, remi::ControlChangeEvent>) {
                auto ctrl = convertControl(e);
                if (ctrl.has_value()) {
                    linkProposal.controlEvents.push_back(*ctrl);
                }
            }
            // TempoEvent, TimeSignatureEvent, ProgramChangeEvent are
            // meta-events handled by the scheduler's Link clock; they do
            // not produce note or control events in the link-clock proposal.
        }, event);
    }

    if (!linkProposal.isWellFormed()) {
        return std::nullopt;
    }

    return linkProposal;
}

} // namespace mozart::generation
