#include "RemiEventAdapter.h"
#include "GenerationTypes.h"

#include <algorithm>
#include <chrono>
#include <limits>

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
    if (events.empty()) {
        RemiDecodeReport report;
        report.result = RemiDecodeResult::EmptySequence;
        report.message = "Empty event sequence";
        return {PatternProposal{}, report};
    }

    for (std::size_t i = 0; i < events.size(); ++i) {
        if (state.events.size() >= config_.maxEvents) {
            state.result = RemiDecodeResult::ExceededMaxEvents;
            state.message = "Truncated at max events: " + std::to_string(config_.maxEvents);
            state.droppedTokens += events.size() - i;
            state.warnings.push_back(state.message);
            break;
        }

        if (state.currentBar >= config_.maxBars) {
            state.result = RemiDecodeResult::ExceededMaxBars;
            state.message = "Truncated at max bars: " + std::to_string(config_.maxBars);
            state.droppedTokens += events.size() - i;
            state.warnings.push_back(state.message);
            break;
        }

        const auto& event = events[i];
        state.processedTokens++;
        
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
                
                // Длительность: приоритет от токена Duration_ (сохранён в состоянии),
                // иначе фиксированная длительность по умолчанию.
                const bool durationWasAlreadyKnown = state.hasPendingDuration;
                std::uint32_t noteDuration = config_.ticksPerBeat / 4;
                if (state.hasPendingDuration) {
                    noteDuration = state.pendingDurationTicks;
                    state.hasPendingDuration = false;
                }
                const std::uint64_t absolutePosition =
                    static_cast<std::uint64_t>(state.currentTick) + e.position;
                if (absolutePosition > std::numeric_limits<std::uint32_t>::max() ||
                    noteDuration > std::numeric_limits<std::uint32_t>::max() - absolutePosition) {
                    state.warnings.push_back("Note position or end tick exceeds the supported tick range");
                    state.droppedTokens++;
                    state.hasNoteAtCurrentPosition = false;
                    return;
                }
                PatternEvent patternEvent = NoteEvent{
                    e.pitch,
                    e.velocity > 0 ? e.velocity : state.currentVelocity,
                    static_cast<std::uint32_t>(absolutePosition),
                    noteDuration,
                    static_cast<std::uint8_t>(e.track % 16),
                    e.track
                };
                state.events.push_back(patternEvent);
                if (!durationWasAlreadyKnown) {
                    state.activeNotes.push_back(
                        DecodeState::ActiveNote{e.pitch, e.track, state.events.size() - 1});
                }
                state.currentTrack = e.track;
                state.hasNoteAtCurrentPosition = true;
            }
            else if constexpr (std::is_same_v<T, RemiNoteOffEvent>) {
                if (e.pitch == 0) {
                    // Duration_ normally follows the note it describes. Only attach backwards
                    // while the current position is still associated with the most recent note.
                    // If a Position_/Bar_ intervened, keep it pending for the next NoteOn instead.
                    bool applied = false;
                    std::size_t durationNoteIndex = state.events.size();
                    if (state.hasNoteAtCurrentPosition) {
                        for (auto it = state.events.rbegin(); it != state.events.rend(); ++it) {
                            if (std::holds_alternative<NoteEvent>(*it)) {
                                auto& note = std::get<NoteEvent>(*it);
                                if (note.track == state.currentTrack) {
                                    note.duration = e.position;
                                    durationNoteIndex = static_cast<std::size_t>(
                                        it.base() - state.events.begin() - 1);
                                    applied = true;
                                    break;
                                }
                            }
                        }
                    }
                    if (applied) {
                        // Duration_ completes this note; remove it from the active-note set
                        // so a later genuine NoteOff cannot overwrite its duration.
                        for (std::size_t i = state.activeNotes.size(); i > 0; --i) {
                            if (state.activeNotes[i - 1].eventIndex == durationNoteIndex) {
                                state.activeNotes.erase(state.activeNotes.begin() +
                                    static_cast<std::ptrdiff_t>(i - 1));
                                break;
                            }
                        }
                    } else {
                        state.pendingDurationTicks = e.position;
                        state.hasPendingDuration = true;
                    }
                    state.hasNoteAtCurrentPosition = false;
                } else {
                    // Genuine note-off closes the most recently started still-active
                    // note with this pitch/track. Closed notes are removed from activeNotes,
                    // preventing a later note-off from repeatedly extending the same note.
                    const auto offTrack = static_cast<std::uint8_t>(e.track % 16);
                    for (std::size_t i = state.activeNotes.size(); i > 0; --i) {
                        const std::size_t activeIndex = i - 1;
                        const auto active = state.activeNotes[activeIndex];
                        if (active.pitch == e.pitch && active.track == offTrack) {
                            if (active.eventIndex < state.events.size() &&
                                std::holds_alternative<NoteEvent>(state.events[active.eventIndex])) {
                                auto& note = std::get<NoteEvent>(state.events[active.eventIndex]);
                                if (e.position > note.position) {
                                    note.duration = e.position - note.position;
                                }
                            }
                            state.activeNotes.erase(state.activeNotes.begin() +
                                static_cast<std::ptrdiff_t>(activeIndex));
                            break;
                        }
                    }
                    state.hasNoteAtCurrentPosition = false;
                }
            }
            else if constexpr (std::is_same_v<T, RemiVelocityEvent>) {
                state.currentVelocity = velocityBinToMidi(e.velocity);
                // In REMI sequences Velocity_ follows Pitch_. Update the just-created note
                // when the token is at that note's position; this also supports Velocity_
                // appearing before Pitch_ because currentVelocity remains the default source.
                for (auto it = state.events.rbegin(); it != state.events.rend(); ++it) {
                    if (std::holds_alternative<NoteEvent>(*it)) {
                        auto& note = std::get<NoteEvent>(*it);
                        if (note.track == state.currentTrack && note.position == state.currentTick) {
                            note.velocity = state.currentVelocity;
                        }
                        break;
                    }
                }
            }
            else if constexpr (std::is_same_v<T, RemiPositionEvent>) {
                const std::uint32_t ticksPerPosition = config_.ticksPerBeat / 8;
                if (ticksPerPosition == 0 || config_.ticksPerBar == 0) {
                    state.warnings.push_back("Position bin cannot be converted with the current decoder configuration");
                    state.droppedTokens++;
                    state.hasNoteAtCurrentPosition = false;
                    return;
                }
                const std::uint32_t positionsPerBar =
                    config_.ticksPerBar / ticksPerPosition +
                    (config_.ticksPerBar % ticksPerPosition == 0 ? 0U : 1U);
                if (e.position >= positionsPerBar) {
                    state.warnings.push_back("Position bin out of range: " + std::to_string(e.position));
                    state.droppedTokens++;
                    state.hasNoteAtCurrentPosition = false;
                    return;
                }
                const std::uint64_t absoluteTick =
                    static_cast<std::uint64_t>(state.currentBar) * config_.ticksPerBar +
                    static_cast<std::uint64_t>(e.position) * ticksPerPosition;
                if (absoluteTick > std::numeric_limits<std::uint32_t>::max()) {
                    state.warnings.push_back("Position resolves beyond the supported tick range");
                    state.droppedTokens++;
                    state.hasNoteAtCurrentPosition = false;
                    return;
                }
                state.currentTick = static_cast<std::uint32_t>(absoluteTick);
                state.hasNoteAtCurrentPosition = false;
            }
            else if constexpr (std::is_same_v<T, RemiBarEvent>) {
                if (e.barNumber == std::numeric_limits<std::uint32_t>::max()) {
                    // Bar_None has no index in REMI; the token marks a bar boundary.
                    if (state.hasSeenImplicitBarToken) {
                        if (state.currentBar + 1U >= config_.maxBars) {
                            state.currentBar = config_.maxBars;
                            state.result = RemiDecodeResult::ExceededMaxBars;
                            state.message = "Truncated at max bars: " + std::to_string(config_.maxBars);
                            state.warnings.push_back(state.message);
                            return;
                        }
                        ++state.currentBar;
                    } else {
                        state.currentBar = 0;
                        state.hasSeenImplicitBarToken = true;
                    }
                } else {
                    // Preserve explicit indexed-bar behavior for direct adapter callers/tests.
                    if (e.barNumber >= config_.maxBars) {
                        state.warnings.push_back("Bar index out of range: " + std::to_string(e.barNumber));
                        state.droppedTokens++;
                        state.hasNoteAtCurrentPosition = false;
                        return;
                    }
                    state.currentBar = e.barNumber;
                    state.hasSeenImplicitBarToken = false;
                }
                const std::uint64_t barTick =
                    static_cast<std::uint64_t>(state.currentBar) * config_.ticksPerBar;
                if (barTick > std::numeric_limits<std::uint32_t>::max()) {
                    state.currentBar = config_.maxBars;
                    state.result = RemiDecodeResult::ExceededMaxBars;
                    state.message = "Bar position exceeds the supported tick range";
                    state.warnings.push_back(state.message);
                    return;
                }
                state.currentTick = static_cast<std::uint32_t>(barTick);
                state.hasNoteAtCurrentPosition = false;
            }
            else if constexpr (std::is_same_v<T, RemiTempoEvent>) {
                if (!state.hasTempo) {
                    PatternEvent tempoEvent = TempoEvent{state.currentTick, e.bpm};
                    state.events.insert(state.events.begin(), tempoEvent);
                    for (auto& active : state.activeNotes) ++active.eventIndex;
                    state.hasTempo = true;
                    state.currentTempo = e.bpm;
                }
            }
            else if constexpr (std::is_same_v<T, RemiTimeSignatureEvent>) {
                if (!state.hasTimeSignature) {
                    PatternEvent tsEvent = TimeSignatureEvent{state.currentTick, e.numerator, e.denominator};
                    const std::size_t insertionIndex = state.hasTempo ? 1U : 0U;
                    state.events.insert(state.events.begin() + insertionIndex, tsEvent);
                    for (auto& active : state.activeNotes) {
                        if (active.eventIndex >= insertionIndex) ++active.eventIndex;
                    }
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