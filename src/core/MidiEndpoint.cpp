#include "MidiEndpoint.h"

#include <algorithm>
#include <cctype>
#include <limits>
#include <tuple>

namespace mozart::midi {
namespace {

[[nodiscard]] std::string lowerAscii(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return value;
}

[[nodiscard]] bool containsIgnoreCase(
        const std::string& value,
        const std::string& needle) {
    if (needle.empty()) {
        return false;
    }

    return lowerAscii(value).find(lowerAscii(needle)) != std::string::npos;
}

[[nodiscard]] bool equalsIgnoreCase(
        const std::string& value,
        const std::string& expected) {
    if (value.empty() || expected.empty()) {
        return false;
    }

    return lowerAscii(value) == lowerAscii(expected);
}

} // namespace

MidiEndpointSelection MidiEndpointSelector::selectPreferredOutput(
        const std::vector<MidiEndpointDescriptor>& candidates,
        const std::string& preferredManufacturer,
        const std::string& preferredProduct) {
    struct RankedCandidate {
        std::size_t index = 0;
        int score = std::numeric_limits<int>::min();
        std::uint32_t deviceId = 0;
        std::uint32_t portNumber = 0;
    };

    std::optional<RankedCandidate> best;

    for (std::size_t i = 0; i < candidates.size(); ++i) {
        const auto& candidate = candidates[i];

        // Android's input port is the port into which Mozart sends MIDI.
        if (!candidate.canReceiveFromMozart()) {
            continue;
        }

        // Automatic Stage 1 selection is intentionally target-specific:
        // do not silently route to an unrelated MIDI device.
        // The initial MicroFreak path is USB-only; other transports remain
        // discoverable for explicit future selection.
        if (candidate.transport != TransportKind::Usb) {
            continue;
        }

        // A preferred product/name match is mandatory for automatic selection.
        // Manufacturer matching only refines the ranking; it is never enough
        // to route MIDI to an otherwise unrelated instrument.
        if (!containsIgnoreCase(candidate.product, preferredProduct) &&
            !containsIgnoreCase(candidate.name, preferredProduct)) {
            continue;
        }

        int score = 0;

        if (equalsIgnoreCase(candidate.product, preferredProduct)) {
            score += 4000;
        } else if (containsIgnoreCase(candidate.product, preferredProduct)) {
            score += 3000;
        } else if (containsIgnoreCase(candidate.name, preferredProduct)) {
            score += 2000;
        }

        if (equalsIgnoreCase(candidate.manufacturer, preferredManufacturer)) {
            score += 2000;
        } else if (containsIgnoreCase(candidate.manufacturer, preferredManufacturer)) {
            score += 1000;
        }

        // Physical USB is preferred over other transports for the initial
        // MicroFreak target, while the descriptor remains transport-neutral.
        if (candidate.transport == TransportKind::Usb) {
            score += 500;
        }

        const RankedCandidate ranked{ i, score, candidate.deviceId, candidate.portNumber };

        if (!best.has_value() ||
            std::tie(ranked.score, ranked.deviceId, ranked.portNumber) >
            std::tie(best->score, best->deviceId, best->portNumber)) {
            best = ranked;
        }
    }

    if (!best.has_value()) {
        return {};
    }

    return MidiEndpointSelection{
        MidiEndpointSelectionStatus::Selected,
        best->index
    };
}

} // namespace mozart::midi
