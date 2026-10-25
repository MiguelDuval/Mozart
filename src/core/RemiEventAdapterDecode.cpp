#include "RemiEventAdapter.h"
#include "GenerationTypes.h"

#include <algorithm>
#include <chrono>

namespace mozart::generation {

//----------------------------------------------------------------------
// Decode events to PatternProposal
//----------------------------------------------------------------------

std::pair<PatternProposal, RemiDecodeReport> RemiEventAdapter::decodeEventsToProposal(
    const std::vector<RemiEvent>& events,
    const GenerationRequest& request,
    const std::string& providerId,
    const std::string& modelId) const noexcept {
    
    auto startTime = std::chrono::high_resolution_clock::now();
    DecodeState state;
    RemiDecodeReport report;
    report.result = RemiDecodeResult::Ok;
    
    if (events.empty()) {
        report.result = RemiDecodeResult::EmptySequence;
        report.message = "Empty event sequence";
        return {PatternProposal{}, report};
    }
    
    for (std::size_t i = 0; i < events.size(); ++i) {
        if (state.events.size() >= config_.maxEvents) {
            report.result = RemiDecodeResult::ExceededMaxEvents;
            report.droppedTokens = events.size() - i;
            state.warnings.push_back("Truncated at max events: " + std::to_string(config_.maxEvents));
            break;
        }
        
        if (state.currentBar >= config_.maxBars) {
            report.result = RemiDecodeResult::ExceededMaxBars;
            report.droppedTokens = events.size() - i;
            state.warnings.push_back("Truncated at max bars: " + std::to_string(config_.maxBars));
            break;
        }
        
        const auto& event = events[i];
        report.processedTokens++;
        
        std::visit([&](const auto& e) {
            using T = std::decay_t<decltype(e)>;
            
            if constexpr (std::is_same_v<T, RemiNoteOnEvent>) {
                if (e.pitch < config_.pitchMin || e.pitch > config_.pitchMax) {
                    state.warnings.push_back("Pitch out of range: " + std::to_string(e.pitch));
                    state.droppedTokens++;
                    return;
                }
                if (e.track >= config_.maxTracks) {
                    state.warnings.push_back("Track index out of range: " + std::to_string(e.track));
                    state.droppedTokens++;
                    return;
                }
                
                PatternEvent patternEvent = NoteEvent{
                    e.pitch,
                    e.velocity > 0 ? e.velocity : state.currentVelocity,
                    state.currentTick + e.position,
                    config_.ticksPerBeat / 4,
                    static_cast<std::uint8_t>(e.track % 16),
                    e.track
                };
                state.events.push_back(patternEvent);
                state.currentTrack = e.track;
            }
            else if constexpr (std::is_same_v<T, RemiNoteOffEvent>) {
            }
            else if constexpr (std::is_same_v<T, RemiVelocityEvent>) {
                state.currentVelocity = velocityBinToMidi(e.velocity);
            }
            else if constexpr (std::is_same_v<T, RemiPositionEvent>) {
                state.currentTick = state.currentBar * config_.ticksPerBar + positionBinToTicks(e.position);
            }
            else if constexpr (std::is_same_v<T, RemiBarEvent>) {
                state.currentBar = e.barNumber;
                state.currentTick = state.currentBar * config_.ticksPerBar;
            }
            else if constexpr (std::is_same_v<T, RemiTempoEvent>) {
                if (!state.hasTempo) {
                    PatternEvent tempoEvent = TempoEvent{state.currentTick, e.bpm};
                    state.events.insert(state.events.begin(), tempoEvent);
                    state.hasTempo = true;
                    state.currentTempo = e.bpm;
                }
            }
            else if constexpr (std::is_same_v<T, RemiTimeSignatureEvent>) {
                if (!state.hasTimeSignature) {
                    PatternEvent tsEvent = TimeSignatureEvent{state.currentTick, e.numerator, e.denominator};
                    state.events.insert(state.events.begin() + (state.hasTempo ? 1 : 0), tsEvent);
                    state.hasTimeSignature = true;
                    state.timeSigNumerator = e.numerator;
                    state.timeSigDenominator = e.denominator;
                }
            }
            else if constexpr (std::is_same_v<T, RemiProgramEvent>) {
                if (e.track < config_.maxTracks) {
                    PatternEvent pcEvent = ProgramChangeEvent{state.currentTick, 
                                                              static_cast<std::uint8_t>(e.track % 16), 
                                                              e.program};
                    state.events.push_back(pcEvent);
                }
            }
            else if constexpr (std::is_same_v<T, RemiChordEvent>) {
                state.warnings.push_back("Chord event not supported in PatternProposal");
            }
        }, event);
    }
    
    auto endTime = std::chrono::high_resolution_clock::now();
    auto generationTime = std::chrono::duration_cast<std::chrono::nanoseconds>(endTime - startTime);
    
    return finalizeProposal(state, request, providerId, modelId, generationTime);
}

} // namespace mozart::generation