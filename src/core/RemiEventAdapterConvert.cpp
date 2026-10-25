#include "RemiEventAdapter.h"
#include "GenerationTypes.h"

#include <algorithm>
#include <chrono>

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
            NoteEvent note;
            note.pitch = e.pitch;
            note.velocity = e.velocity > 0 ? e.velocity : currentVelocity;
            note.position = currentTick + e.position;
            note.duration = config_.ticksPerBeat / 4;
            note.channel = e.track % 16;
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
            TempoEvent tempo;
            tempo.position = currentTick;
            tempo.bpm = e.bpm;
            return tempo;
        }
        else if constexpr (std::is_same_v<T, RemiTimeSignatureEvent>) {
            TimeSignatureEvent ts;
            ts.position = currentTick;
            ts.numerator = e.numerator;
            ts.denominator = e.denominator;
            return ts;
        }
        else if constexpr (std::is_same_v<T, RemiProgramEvent>) {
            ProgramChangeEvent pc;
            pc.position = currentTick;
            pc.channel = e.track % 16;
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