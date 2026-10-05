#pragma once

#include <cstdint>

namespace mozart::musical {

struct MusicalNoteEvent {
    double startBeat = 0.0;
    double durationBeats = 0.0;
    std::uint8_t note = 0;
    std::uint8_t velocity = 0;
    std::uint8_t channel = 0;

    friend bool operator==(const MusicalNoteEvent&, const MusicalNoteEvent&) = default;
};

} // namespace mozart::musical
