#include "LocalNeuralPatternProvider.h"
#include "GenerationTypes.h"
#include "RemiEventAdapter.h"
#include "generation/RhythmGenerator.h"

#include <algorithm>
#include <chrono>

namespace mozart::generation {

std::optional<PatternProposal> LocalNeuralPatternProvider::generateDeterministic(const GenerationRequest& request) const noexcept {
    auto startTime = std::chrono::high_resolution_clock::now();
    
    const std::uint32_t seed = request.seed.value_or(std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::high_resolution_clock::now().time_since_epoch()).count());
    
    const std::uint32_t bars = request.barCount.value_or(4);
    const std::uint32_t ticksPerBeat = 480;
    const std::uint32_t ticksPerBar = ticksPerBeat * 4;
    const std::uint32_t totalTicks = bars * ticksPerBar;
    
    const std::size_t steps = bars * 16;
    const std::size_t pulses = bars * 4;
    const auto kickPattern = RhythmGenerator::euclidean(steps, pulses);
    const auto velocities = RhythmGenerator::seededVelocityPattern(steps, seed);
    
    PatternProposal proposal;
    proposal.providerId = providerId_ + "-deterministic";
    proposal.modelId = "deterministic-fallback";
    proposal.seed = seed;
    proposal.generationTime = std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::high_resolution_clock::now() - startTime);
    
    double bpm = 120.0;
    if (request.targetBpm.has_value()) {
        bpm = request.targetBpm.value();
    } else if (request.minBpm.has_value() && request.maxBpm.has_value()) {
        bpm = (request.minBpm.value() + request.maxBpm.value()) / 2.0;
    }
    proposal.events.push_back(TempoEvent{0, bpm});
    proposal.events.push_back(TimeSignatureEvent{0, 4, 4});
    
    // Drum track (channel 9)
    for (std::size_t i = 0; i < kickPattern.size(); ++i) {
        if (kickPattern[i]) {
            NoteEvent kick;
            kick.pitch = 36;
            kick.velocity = velocities[i];
            kick.position = static_cast<std::uint32_t>(i * ticksPerBeat / 4);
            kick.duration = ticksPerBeat / 8;
            kick.channel = 9;
            kick.track = 0;
            proposal.events.push_back(kick);
        }
    }
    
    // Bass track (channel 0)
    const auto bassPattern = RhythmGenerator::euclidean(steps, bars * 2);
    const auto bassVelocities = RhythmGenerator::seededVelocityPattern(steps, seed + 1);
    for (std::size_t i = 0; i < bassPattern.size(); ++i) {
        if (bassPattern[i]) {
            NoteEvent bass;
            bass.pitch = 36 + (i % 12);
            bass.velocity = static_cast<std::uint8_t>(bassVelocities[i] * 0.8);
            bass.position = static_cast<std::uint32_t>(i * ticksPerBeat / 4);
            bass.duration = ticksPerBeat / 2;
            bass.channel = 0;
            bass.track = 1;
            proposal.events.push_back(bass);
        }
    }
    
    proposal.totalTicks = totalTicks;
    proposal.trackCount = 2;
    
    auto [sanitized, report] = validator_.sanitize(proposal);
    if (!report.isOk()) {
        return std::nullopt;
    }
    
    return sanitized;
}

} // namespace mozart::generation