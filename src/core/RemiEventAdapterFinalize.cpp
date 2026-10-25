#include "RemiEventAdapter.h"
#include "GenerationTypes.h"

#include <algorithm>
#include <chrono>

namespace mozart::generation {

//----------------------------------------------------------------------
// Finalize proposal
//----------------------------------------------------------------------

std::pair<PatternProposal, RemiDecodeReport> RemiEventAdapter::finalizeProposal(
    DecodeState& state,
    const GenerationRequest& request,
    const std::string& providerId,
    const std::string& modelId,
    std::chrono::nanoseconds generationTime) const noexcept {
    
    RemiDecodeReport report;
    report.result = RemiDecodeResult::Ok;
    report.processedTokens = state.events.size();
    report.droppedTokens = state.droppedTokens;
    report.warnings = state.warnings;
    
    if (state.events.empty()) {
        report.result = RemiDecodeResult::EmptySequence;
        report.message = "No valid events after decoding";
        return {PatternProposal{}, report};
    }
    
    std::uint32_t maxTick = 0;
    for (const auto& event : state.events) {
        std::uint32_t pos = 0;
        std::visit([&pos](const auto& e) { pos = e.position; }, event);
        maxTick = std::max(maxTick, pos);
    }
    
    std::uint32_t totalTicks = std::max(maxTick + config_.ticksPerBeat, config_.ticksPerBar);
    
    std::uint8_t maxTrack = 0;
    for (const auto& event : state.events) {
        if (std::holds_alternative<NoteEvent>(event)) {
            maxTrack = std::max(maxTrack, std::get<NoteEvent>(event).track);
        } else if (std::holds_alternative<ProgramChangeEvent>(event)) {
            maxTrack = std::max(maxTrack, std::get<ProgramChangeEvent>(event).channel);
        }
    }
    
    PatternProposal proposal;
    proposal.providerId = providerId;
    proposal.modelId = modelId;
    proposal.seed = request.seed.value_or(0);
    proposal.generationTime = generationTime;
    proposal.events = std::move(state.events);
    proposal.totalTicks = totalTicks;
    proposal.trackCount = maxTrack + 1;
    proposal.warnings = std::move(state.warnings);
    proposal.truncated = (report.result == RemiDecodeResult::ExceededMaxEvents || 
                          report.result == RemiDecodeResult::ExceededMaxBars);
    
    if (request.maxTicks.has_value()) {
        proposal.totalTicks = std::min(proposal.totalTicks, request.maxTicks.value());
    }
    if (request.maxEvents.has_value() && proposal.events.size() > request.maxEvents.value()) {
        proposal.events.resize(request.maxEvents.value());
        proposal.truncated = true;
    }
    
    return {proposal, report};
}

} // namespace mozart::generation