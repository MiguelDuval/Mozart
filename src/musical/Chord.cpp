#include "Chord.h"

#include <algorithm>

namespace mozart::musical {

Chord::Chord(
        const std::uint8_t rootPitchClass,
        const ChordQuality quality) noexcept
    : rootPitchClass_(rootPitchClass),
      quality_(quality) {}

bool Chord::isValid() const noexcept {
    return rootPitchClass_ < 12 &&
            static_cast<std::uint8_t>(quality_) <=
                    static_cast<std::uint8_t>(ChordQuality::Diminished7);
}

std::uint8_t Chord::rootPitchClass() const noexcept {
    return rootPitchClass_;
}

ChordQuality Chord::quality() const noexcept {
    return quality_;
}

std::size_t Chord::noteCount() const noexcept {
    return sizeFor(quality_);
}

std::uint8_t Chord::pitchClassAt(const std::size_t index) const noexcept {
    const auto count = noteCount();
    if (!isValid() || index >= count) {
        return 0;
    }

    const auto interval = intervalsFor(quality_)[index];
    return static_cast<std::uint8_t>(
            (static_cast<int>(rootPitchClass_) + interval) % 12);
}

bool Chord::containsPitchClass(const std::uint8_t pitchClass) const noexcept {
    if (!isValid() || pitchClass >= 12) {
        return false;
    }

    for (std::size_t i = 0; i < noteCount(); ++i) {
        if (pitchClassAt(i) == pitchClass) {
            return true;
        }
    }
    return false;
}

bool Chord::containsMidiNote(const std::uint8_t midiNote) const noexcept {
    return containsPitchClass(static_cast<std::uint8_t>(midiNote % 12));
}

std::uint8_t Chord::midiNote(
        const std::size_t degree,
        const std::uint8_t baseOctave) const noexcept {
    if (!isValid()) {
        return 0;
    }

    const auto count = noteCount();
    const auto octaveOffset = degree / count;
    const auto index = degree % count;
    const auto note =
            12 * (static_cast<int>(baseOctave) + 1) +
            static_cast<int>(rootPitchClass_) +
            intervalsFor(quality_)[index] +
            12 * static_cast<int>(octaveOffset);

    return static_cast<std::uint8_t>(
            std::clamp(note, 0, 127));
}

const std::array<int, 4>& Chord::intervalsFor(
        const ChordQuality quality) noexcept {
    static constexpr std::array<int, 4> major{0, 4, 7, 0};
    static constexpr std::array<int, 4> minor{0, 3, 7, 0};
    static constexpr std::array<int, 4> diminished{0, 3, 6, 0};
    static constexpr std::array<int, 4> augmented{0, 4, 8, 0};
    static constexpr std::array<int, 4> major7{0, 4, 7, 11};
    static constexpr std::array<int, 4> dominant7{0, 4, 7, 10};
    static constexpr std::array<int, 4> minor7{0, 3, 7, 10};
    static constexpr std::array<int, 4> halfDiminished7{0, 3, 6, 10};
    static constexpr std::array<int, 4> diminished7{0, 3, 6, 9};

    switch (quality) {
        case ChordQuality::Minor:
            return minor;
        case ChordQuality::Diminished:
            return diminished;
        case ChordQuality::Augmented:
            return augmented;
        case ChordQuality::Major7:
            return major7;
        case ChordQuality::Dominant7:
            return dominant7;
        case ChordQuality::Minor7:
            return minor7;
        case ChordQuality::HalfDiminished7:
            return halfDiminished7;
        case ChordQuality::Diminished7:
            return diminished7;
        case ChordQuality::Major:
        default:
            return major;
    }
}

std::size_t Chord::sizeFor(const ChordQuality quality) noexcept {
    switch (quality) {
        case ChordQuality::Major7:
        case ChordQuality::Dominant7:
        case ChordQuality::Minor7:
        case ChordQuality::HalfDiminished7:
        case ChordQuality::Diminished7:
            return 4;
        case ChordQuality::Major:
        case ChordQuality::Minor:
        case ChordQuality::Diminished:
        case ChordQuality::Augmented:
        default:
            return 3;
    }
}

} // namespace mozart::musical
