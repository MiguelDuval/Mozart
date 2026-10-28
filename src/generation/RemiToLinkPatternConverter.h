#pragma once

#include "remi/GenerationTypes.h"
#include "generation/PatternProposal.h"

#include <cstdint>

namespace mozart::generation {

//----------------------------------------------------------------------
// RemiToLinkPatternConverter - converts remi::PatternProposal (REMI/BPE
// adapter output) to mozart::generation::PatternProposal (Link-aligned
// scheduler input).
//
// Performs tick-to-beat coordinate conversion using a configurable
// ticks-per-beat resolution. Pure function — no Link, Android, or audio
// dependencies. Fully deterministic given fixed config.
//----------------------------------------------------------------------

class RemiToLinkPatternConverter final {
public:
    explicit RemiToLinkPatternConverter(std::uint32_t ticksPerBeat = 480) noexcept;

    [[nodiscard]] std::uint32_t ticksPerBeat() const noexcept { return ticksPerBeat_; }

    // Convert a remi PatternProposal to a generation PatternProposal.
    // Returns std::nullopt if the remi proposal is invalid or conversion fails.
    // The returned proposal is NOT validated — call
    // PatternProposalValidator::validate() on the result if validation is needed.
    [[nodiscard]] std::optional<PatternProposal> convert(
            const remi::PatternProposal& remiProposal) const noexcept;

private:
    [[nodiscard]] std::optional<musical::MusicalNoteEvent> convertNote(
            const remi::NoteEvent& note) const noexcept;
    [[nodiscard]] std::optional<PatternControlEvent> convertControl(
            const remi::ControlChangeEvent& cc) const noexcept;

    std::uint32_t ticksPerBeat_;
};

} // namespace mozart::generation
