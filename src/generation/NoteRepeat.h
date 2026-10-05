#pragma once

#include "musical/MusicalNote.h"

#include <cstdint>
#include <vector>

namespace mozart::generation {

enum class NoteRepeatRate : std::uint8_t {
    Off = 1,
    Double = 2,
    Triple = 3,
    Quadruple = 4
};

class NoteRepeat final {
public:
    [[nodiscard]] static std::vector<musical::MusicalNoteEvent> apply(
            const std::vector<musical::MusicalNoteEvent>& events,
            NoteRepeatRate rate) ;
};

} // namespace mozart::generation
