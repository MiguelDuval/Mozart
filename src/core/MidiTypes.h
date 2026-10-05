#pragma once

#include <cstdint>
#include <optional>

namespace mozart::midi {

struct MidiShortMessage {
    std::uint8_t status = 0;
    std::uint8_t data1 = 0;
    std::uint8_t data2 = 0;
    std::uint8_t size = 0;
    std::uint64_t timestampNanos = 0;
    std::uint32_t portId = 0;

    [[nodiscard]] bool isValid() const noexcept;
};

[[nodiscard]] std::optional<MidiShortMessage> noteOn(
        std::uint8_t channel,
        std::uint8_t note,
        std::uint8_t velocity,
        std::uint64_t timestampNanos = 0,
        std::uint32_t portId = 0) noexcept;

[[nodiscard]] std::optional<MidiShortMessage> noteOff(
        std::uint8_t channel,
        std::uint8_t note,
        std::uint8_t velocity = 0,
        std::uint64_t timestampNanos = 0,
        std::uint32_t portId = 0) noexcept;

[[nodiscard]] std::optional<MidiShortMessage> controlChange(
        std::uint8_t channel,
        std::uint8_t controller,
        std::uint8_t value,
        std::uint64_t timestampNanos = 0,
        std::uint32_t portId = 0) noexcept;

} // namespace mozart::midi
