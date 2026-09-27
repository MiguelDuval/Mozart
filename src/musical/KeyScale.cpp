#include "KeyScale.h"

namespace mozart::musical {

KeyScale::KeyScale(
        const std::uint8_t rootPitchClass,
        const Scale scale)
    : rootPitchClass_(rootPitchClass),
      scale_(scale) {}

bool KeyScale::isValid() const noexcept {
    return rootPitchClass_ < 12;
}

std::uint8_t KeyScale::rootPitchClass() const noexcept {
    return rootPitchClass_;
}

Scale KeyScale::scale() const noexcept {
    return scale_;
}

const std::array<int, 7>& KeyScale::intervalsFor(
        const Scale scale) noexcept {
    static constexpr std::array<int, 7> major{0, 2, 4, 5, 7, 9, 11};
    static constexpr std::array<int, 7> minor{0, 2, 3, 5, 7, 8, 10};
    static constexpr std::array<int, 7> dorian{0, 2, 3, 5, 7, 9, 10};

    switch (scale) {
        case Scale::NaturalMinor:
            return minor;
        case Scale::Dorian:
            return dorian;
        case Scale::Major:
        default:
            return major;
    }
}

bool KeyScale::containsMidiNote(const std::uint8_t midiNote) const noexcept {
    if (!isValid()) {
        return false;
    }

    const int pitchClass =
            (static_cast<int>(midiNote) - static_cast<int>(rootPitchClass_) + 120) % 12;

    const auto& intervals = intervalsFor(scale_);
    for (const auto interval : intervals) {
        if (pitchClass == interval) {
            return true;
        }
    }

    return false;
}

std::uint8_t KeyScale::degreeToMidiNote(
        const std::size_t degree,
        const std::uint8_t baseOctave) const noexcept {
    const auto& intervals = intervalsFor(scale_);
    const auto octaveOffset = static_cast<int>(degree / intervals.size());
    const auto degreeIndex = degree % intervals.size();

    const int note =
            12 * (static_cast<int>(baseOctave) + 1)
            + static_cast<int>(rootPitchClass_)
            + intervals[degreeIndex]
            + 12 * octaveOffset;

    if (note < 0) {
        return 0;
    }

    if (note > 127) {
        return 127;
    }

    return static_cast<std::uint8_t>(note);
}

} // namespace mozart::musical
