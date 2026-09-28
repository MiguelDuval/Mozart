#pragma once

#include <cstddef>
#include <cstdint>

namespace mozart::generation {

using MidiEventToken = std::uint16_t;

namespace midi_event_vocabulary {

constexpr MidiEventToken kPad = 0;
constexpr MidiEventToken kBos = 1;
constexpr MidiEventToken kEos = 2;

constexpr MidiEventToken kChannelBase = 16;
constexpr std::size_t kChannelCount = 16;

constexpr MidiEventToken kNoteBase = 32;
constexpr std::size_t kNoteCount = 128;

constexpr MidiEventToken kVelocityBase =
        kNoteBase + static_cast<MidiEventToken>(kNoteCount);
constexpr std::size_t kVelocityBinCount = 32;

constexpr MidiEventToken kTimeShiftBase =
        kVelocityBase + static_cast<MidiEventToken>(kVelocityBinCount);
constexpr std::size_t kTimeShiftBinCount = 64;

constexpr MidiEventToken kDurationBase =
        kTimeShiftBase + static_cast<MidiEventToken>(kTimeShiftBinCount);
constexpr std::size_t kDurationBinCount = 96;

constexpr MidiEventToken kControllerBase =
        kDurationBase + static_cast<MidiEventToken>(kDurationBinCount);
constexpr std::size_t kControllerCount = 128;

constexpr MidiEventToken kControlValueBase =
        kControllerBase + static_cast<MidiEventToken>(kControllerCount);
constexpr std::size_t kControlValueBinCount = 32;

constexpr std::size_t kVocabularySize =
        static_cast<std::size_t>(kControlValueBase) +
        kControlValueBinCount;

constexpr double kBeatGrid = 1.0 / 16.0;
constexpr std::size_t kMaxTimeShiftSteps = kTimeShiftBinCount;
constexpr std::size_t kMaxDurationSteps = kDurationBinCount;

[[nodiscard]] constexpr bool isValidToken(
        const MidiEventToken token) noexcept {
    return static_cast<std::size_t>(token) < kVocabularySize;
}

[[nodiscard]] constexpr MidiEventToken channelToken(
        const std::uint8_t channel) noexcept {
    return static_cast<MidiEventToken>(kChannelBase + channel);
}

[[nodiscard]] constexpr MidiEventToken noteToken(
        const std::uint8_t note) noexcept {
    return static_cast<MidiEventToken>(kNoteBase + note);
}

[[nodiscard]] constexpr MidiEventToken velocityToken(
        const std::uint8_t bin) noexcept {
    return static_cast<MidiEventToken>(kVelocityBase + bin - 1);
}

[[nodiscard]] constexpr MidiEventToken timeShiftToken(
        const std::uint8_t steps) noexcept {
    return static_cast<MidiEventToken>(kTimeShiftBase + steps - 1);
}

[[nodiscard]] constexpr MidiEventToken durationToken(
        const std::uint8_t steps) noexcept {
    return static_cast<MidiEventToken>(kDurationBase + steps - 1);
}

[[nodiscard]] constexpr MidiEventToken controllerToken(
        const std::uint8_t controller) noexcept {
    return static_cast<MidiEventToken>(kControllerBase + controller);
}

[[nodiscard]] constexpr MidiEventToken controlValueToken(
        const std::uint8_t bin) noexcept {
    return static_cast<MidiEventToken>(kControlValueBase + bin - 1);
}

} // namespace midi_event_vocabulary

} // namespace mozart::generation
