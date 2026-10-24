#pragma once

#include "core/MidiTypes.h"

#include <cstddef>
#include <cstdint>

namespace mozart::midi {

enum class MidiTransportStatus : std::int32_t {
    Ok = 0,
    NotOpen = 1,
    InvalidMessage = 2,
    Unsupported = 3,
    PlatformError = 4,
    PartialSend = 5
};

struct MidiSendResult {
    MidiTransportStatus status = MidiTransportStatus::PlatformError;
    std::size_t bytesSent = 0;

    [[nodiscard]] bool ok() const noexcept {
        return status == MidiTransportStatus::Ok;
    }
};

/**
 * Transport-neutral MIDI output boundary.
 *
 * Implementations own platform handles, port objects and byte packing.
 * Callers provide validated semantic/native MIDI messages only.
 *
 * Implementations may block while performing the actual transport write.
 * Realtime scheduling code must therefore place blocking transport I/O on
 * its dedicated transport/send path rather than an audio callback.
 */
class MidiOutputTransport {
public:
    virtual ~MidiOutputTransport() = default;

    [[nodiscard]] virtual MidiSendResult send(
            const MidiShortMessage& message) noexcept = 0;

    virtual void close() noexcept = 0;
};

} // namespace mozart::midi
