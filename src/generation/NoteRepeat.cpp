#include "NoteRepeat.h"

#include <algorithm>
#include <cstddef>

namespace mozart::generation {

std::vector<musical::MusicalNoteEvent> NoteRepeat::apply(
        const std::vector<musical::MusicalNoteEvent>& events,
        const NoteRepeatRate rate) {
    const auto repeats = static_cast<std::size_t>(rate);
    if (events.empty() || repeats <= 1) {
        return events;
    }

    std::vector<musical::MusicalNoteEvent> result;
    result.reserve(events.size() * repeats);

    for (const auto& event : events) {
        const double slice = event.durationBeats /
                static_cast<double>(repeats);
        const double gate = std::max(0.01, slice * 0.85);

        for (std::size_t i = 0; i < repeats; ++i) {
            auto repeated = event;
            repeated.startBeat =
                    event.startBeat + slice * static_cast<double>(i);
            repeated.durationBeats = std::min(gate, slice);
            result.push_back(repeated);
        }
    }

    return result;
}

} // namespace mozart::generation
