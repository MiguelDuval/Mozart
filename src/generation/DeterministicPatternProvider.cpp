#include "generation/DeterministicPatternProvider.h"

#include "generation/ArpeggioGenerator.h"
#include "generation/BassGenerator.h"
#include "musical/MusicalNote.h"

#include <utility>

namespace mozart::generation {

GenerationResult DeterministicPatternProvider::generate(
        const GenerationRequest& request) {
    if (!request.isValid()) {
        return {
                GenerationStatus::InvalidRequest,
                {},
                "invalid generation request"
        };
    }

    PatternProposal proposal;
    proposal.metadata.seed = request.seed;
    proposal.metadata.generatorId = "deterministic-local-v1";

    for (std::uint8_t bar = 0; bar < request.bars; ++bar) {
        const auto seed = request.seed ^
                (0x9E3779B9u * (static_cast<std::uint32_t>(bar) + 1U));
        const auto events =
                request.role == GenerationRole::Arpeggio
                        ? ArpeggioGenerator::generateBar(
                                request.keyScale,
                                4,
                                seed,
                                0,
                                request.density < 0.34
                                        ? PatternDensity::Sparse
                                        : (request.density < 0.67
                                                   ? PatternDensity::Normal
                                                   : PatternDensity::Full))
                        : BassGenerator::generateBar(
                                request.keyScale,
                                2,
                                seed,
                                0,
                                request.density < 0.34
                                        ? PatternDensity::Sparse
                                        : (request.density < 0.67
                                                   ? PatternDensity::Normal
                                                   : PatternDensity::Full));

        for (auto event : events) {
            event.startBeat += static_cast<double>(bar) * 4.0;
            proposal.noteEvents.push_back(event);
        }
    }

    proposal.metadata.confidence = proposal.noteEvents.empty() ? 0.0 : 1.0;
    if (proposal.noteEvents.size() > PatternProposal::kMaxNoteEvents) {
        return {
                GenerationStatus::Failed,
                {},
                "deterministic provider exceeded proposal event limit"
        };
    }

    return {
            GenerationStatus::Ok,
            std::move(proposal),
            {}
    };
}

} // namespace mozart::generation
