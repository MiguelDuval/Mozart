#pragma once

#include <array>
#include <cstdint>

namespace mozart::musical {

enum class Scale : std::uint8_t {
    Major = 0,
    NaturalMinor = 1,
    Dorian = 2
};

class KeyScale final {
public:
    KeyScale() = default;
    KeyScale(std::uint8_t rootPitchClass, Scale scale);

    [[nodiscard]] bool isValid() const noexcept;
    [[nodiscard]] std::uint8_t rootPitchClass() const noexcept;
    [[nodiscard]] Scale scale() const noexcept;

    [[nodiscard]] bool containsMidiNote(std::uint8_t midiNote) const noexcept;
    [[nodiscard]] std::uint8_t degreeToMidiNote(
            std::size_t degree,
            std::uint8_t baseOctave) const noexcept;

private:
    [[nodiscard]] static const std::array<int, 7>& intervalsFor(
            Scale scale) noexcept;

    std::uint8_t rootPitchClass_ = 0;
    Scale scale_ = Scale::Major;
};

} // namespace mozart::musical
