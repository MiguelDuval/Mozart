#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace mozart::midi {

enum class PortDirection : std::uint8_t {
    Input = 1,
    Output = 2
};

enum class TransportKind : std::uint8_t {
    Unknown = 0,
    Usb = 1,
    Bluetooth = 2,
    Virtual = 3
};

struct MidiEndpointDescriptor {
    std::uint32_t deviceId = 0;
    std::uint32_t portNumber = 0;
    PortDirection direction = PortDirection::Output;
    TransportKind transport = TransportKind::Unknown;
    std::string name;
    std::string manufacturer;
    std::string product;

    [[nodiscard]] bool canReceiveFromMozart() const noexcept {
        return direction == PortDirection::Input;
    }
};

enum class MidiEndpointSelectionStatus : std::uint8_t {
    Selected,
    NoMatchingEndpoint
};

struct MidiEndpointSelection {
    MidiEndpointSelectionStatus status = MidiEndpointSelectionStatus::NoMatchingEndpoint;
    std::optional<std::size_t> candidateIndex;

    [[nodiscard]] bool selected() const noexcept {
        return status == MidiEndpointSelectionStatus::Selected &&
               candidateIndex.has_value();
    }
};

class MidiEndpointSelector final {
public:
    [[nodiscard]] static MidiEndpointSelection selectPreferredOutput(
            const std::vector<MidiEndpointDescriptor>& candidates,
            const std::string& preferredManufacturer,
            const std::string& preferredProduct) noexcept;
};

} // namespace mozart::midi
