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

    // Convert a REMI proposal to the Link scheduler's semantic proposal.
    // The complete source proposal is validated before conversion; malformed
    // proposals and unsupported program-change events are rejected atomically.
    // Request-specific constraints are still enforced at the runtime boundary.
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
