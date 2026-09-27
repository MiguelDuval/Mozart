#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace mozart::musical {

enum class ChordQuality : std::uint8_t {
    Major = 0,
    Minor = 1,
    Diminished = 2,
    Augmented = 3,
    Major7 = 4,
    Dominant7 = 5,
    Minor7 = 6,
    HalfDiminished7 = 7,
    Diminished7 = 8
};

class Chord final {
public:
    Chord() = default;
    Chord(std::uint8_t rootPitchClass, ChordQuality quality) noexcept;

    [[nodiscard]] bool isValid() const noexcept;
    [[nodiscard]] std::uint8_t rootPitchClass() const noexcept;
    [[nodiscard]] ChordQuality quality() const noexcept;

    [[nodiscard]] std::size_t noteCount() const noexcept;
    [[nodiscard]] std::uint8_t pitchClassAt(std::size_t index) const noexcept;
    [[nodiscard]] bool containsPitchClass(
            std::uint8_t pitchClass) const noexcept;
    [[nodiscard]] bool containsMidiNote(
            std::uint8_t midiNote) const noexcept;

    // Maps chord tones to ascending MIDI notes. The degree wraps around the
    // chord, allowing deterministic extension across octaves.
    [[nodiscard]] std::uint8_t midiNote(
            std::size_t degree,
            std::uint8_t baseOctave) const noexcept;

private:
    [[nodiscard]] static const std::array<int, 4>& intervalsFor(
            ChordQuality quality) noexcept;
    [[nodiscard]] static std::size_t sizeFor(
            ChordQuality quality) noexcept;

    std::uint8_t rootPitchClass_ = 0;
    ChordQuality quality_ = ChordQuality::Major;
};

} // namespace mozart::musical
