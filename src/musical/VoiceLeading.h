#pragma once

#include "musical/Chord.h"

#include <cstdint>
#include <vector>

namespace mozart::musical {

struct VoiceLeadingOptions final {
    std::uint8_t baseOctave = 3;
    std::uint8_t minNote = 48;
    std::uint8_t maxNote = 84;
};

class VoiceLeading final {
public:
    // Converts a chord progression into deterministic close-position
    // voicings. Each successive chord is chosen by minimizing total
    // semitone movement against the preceding voicing.
    //
    // The result contains one ascending MIDI-note vector per input chord.
    // Empty input returns empty output; invalid chords or an invalid note
    // range return empty output.
    [[nodiscard]] static std::vector<std::vector<std::uint8_t>> generate(
            const std::vector<Chord>& progression,
            const VoiceLeadingOptions& options = {}) noexcept;
};

} // namespace mozart::musical
