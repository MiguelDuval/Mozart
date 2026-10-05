#include "MidiTypes.h"

namespace mozart::midi {
namespace {

[[nodiscard]] bool channelIsValid(std::uint8_t channel) noexcept {
    return channel < 16;
}

[[nodiscard]] bool dataIsValid(std::uint8_t value) noexcept {
    return value < 128;
}

} // namespace

bool MidiShortMessage::isValid() const noexcept {
    if (status < 0x80 || status > 0xEF || size < 1 || size > 3) {
        return false;
    }

    const auto messageType = static_cast<std::uint8_t>(status & 0xF0);

    if (messageType == 0xC0 || messageType == 0xD0) {
        return size == 2 && dataIsValid(data1);
    }

    return size == 3 && dataIsValid(data1) && dataIsValid(data2);
}

std::optional<MidiShortMessage> noteOn(
        std::uint8_t channel,
        std::uint8_t note,
        std::uint8_t velocity,
        std::uint64_t timestampNanos,
        std::uint32_t portId) noexcept {
    if (!channelIsValid(channel) || !dataIsValid(note) || !dataIsValid(velocity)) {
        return std::nullopt;
    }

    return MidiShortMessage{
        static_cast<std::uint8_t>(0x90 | channel),
        note,
        velocity,
        3,
        timestampNanos,
        portId
    };
}

std::optional<MidiShortMessage> noteOff(
        std::uint8_t channel,
        std::uint8_t note,
        std::uint8_t velocity,
        std::uint64_t timestampNanos,
        std::uint32_t portId) noexcept {
    if (!channelIsValid(channel) || !dataIsValid(note) || !dataIsValid(velocity)) {
        return std::nullopt;
    }

    return MidiShortMessage{
        static_cast<std::uint8_t>(0x80 | channel),
        note,
        velocity,
        3,
        timestampNanos,
        portId
    };
}

std::optional<MidiShortMessage> controlChange(
        std::uint8_t channel,
        std::uint8_t controller,
        std::uint8_t value,
        std::uint64_t timestampNanos,
        std::uint32_t portId) noexcept {
    if (!channelIsValid(channel) || !dataIsValid(controller) || !dataIsValid(value)) {
        return std::nullopt;
    }

    return MidiShortMessage{
        static_cast<std::uint8_t>(0xB0 | channel),
        controller,
        value,
        3,
        timestampNanos,
        portId
    };
}

} // namespace mozart::midi
