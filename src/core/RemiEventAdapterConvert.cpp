#include "RemiEventAdapter.h"
#include "GenerationTypes.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <limits>

namespace mozart::generation {

//----------------------------------------------------------------------
// Convert single REMI event to PatternEvent
//----------------------------------------------------------------------

std::optional<PatternEvent> RemiEventAdapter::convertEvent(const RemiEvent& event,
                                                            std::uint32_t currentTick,
                                                            std::uint8_t currentTrack,
                                                            std::uint8_t currentVelocity) const noexcept {
    return std::visit([&](const auto& e) -> std::optional<PatternEvent> {
        using T = std::decay_t<decltype(e)>;
        
        if constexpr (std::is_same_v<T, RemiNoteOnEvent>) {
            if (e.pitch < config_.pitchMin || e.pitch > config_.pitchMax ||
                e.track >= config_.maxTracks) {
                return std::nullopt;
            }
            const std::uint64_t absolutePosition =
                static_cast<std::uint64_t>(currentTick) + e.position;
            const std::uint32_t defaultDuration = config_.ticksPerBeat / 4;
            if (absolutePosition > std::numeric_limits<std::uint32_t>::max() ||
                defaultDuration == 0 ||
                defaultDuration > std::numeric_limits<std::uint32_t>::max() - absolutePosition) {
                return std::nullopt;
            }

            NoteEvent note;
            note.pitch = e.pitch;
            note.velocity = e.velocity > 0 ? e.velocity : currentVelocity;
            note.position = static_cast<std::uint32_t>(absolutePosition);
            note.duration = defaultDuration;
            note.channel = static_cast<std::uint8_t>(e.track % 16);
            note.track = e.track;
            return note;
        }
        else if constexpr (std::is_same_v<T, RemiNoteOffEvent>) {
            return std::nullopt;
        }
        else if constexpr (std::is_same_v<T, RemiVelocityEvent>) {
            return std::nullopt;
        }
        else if constexpr (std::is_same_v<T, RemiPositionEvent>) {
            return std::nullopt;
        }
        else if constexpr (std::is_same_v<T, RemiBarEvent>) {
            return std::nullopt;
        }
        else if constexpr (std::is_same_v<T, RemiTempoEvent>) {
            if (!std::isfinite(e.bpm) || e.bpm < config_.tempoMin || e.bpm > config_.tempoMax) {
                return std::nullopt;
            }
            TempoEvent tempo;
            tempo.position = currentTick;
            tempo.bpm = e.bpm;
            return tempo;
        }
        else if constexpr (std::is_same_v<T, RemiTimeSignatureEvent>) {
            if (e.numerator == 0 || e.denominator == 0 ||
                (e.denominator & (e.denominator - 1U)) != 0) {
                return std::nullopt;
            }
            TimeSignatureEvent ts;
            ts.position = currentTick;
            ts.numerator = e.numerator;
            ts.denominator = e.denominator;
            return ts;
        }
        else if constexpr (std::is_same_v<T, RemiProgramEvent>) {
            if (e.track >= config_.maxTracks) return std::nullopt;
            ProgramChangeEvent pc;
            pc.position = currentTick;
            pc.channel = static_cast<std::uint8_t>(e.track % 16);
            pc.program = e.program;
            return pc;
        }
        else if constexpr (std::is_same_v<T, RemiChordEvent>) {
            return std::nullopt;
        }
        else {
            return std::nullopt;
        }
    }, event);
}

} // namespace mozart::generation