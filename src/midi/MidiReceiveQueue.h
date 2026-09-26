#pragma once

#include "core/MidiTypes.h"

#include <cstddef>
#include <cstdint>
#include <deque>
#include <mutex>

namespace mozart::midi {

/**
 * Bounded transport-neutral queue for already parsed incoming MIDI 1.0
 * channel-voice messages.
 *
 * The queue is intentionally independent from Android/JNI so future harmony
 * and key/scale consumers can use the same input stream with test doubles.
 *
 * When full, the oldest event is discarded so a stalled consumer cannot cause
 * the receive path to grow without bound or retain arbitrarily stale notes.
 */
class MidiReceiveQueue final {
public:
    explicit MidiReceiveQueue(std::size_t capacity = 512);

    MidiReceiveQueue(const MidiReceiveQueue&) = delete;
    MidiReceiveQueue& operator=(const MidiReceiveQueue&) = delete;

    /**
     * Enqueue one validated incoming MIDI event.
     *
     * Returns false only when capacity is zero. With a positive capacity the
     * newest event is always retained; an older event may be dropped.
     */
    [[nodiscard]] bool push(const MidiShortMessage& message);

    /**
     * Remove the oldest queued event.
     */
    [[nodiscard]] bool tryPop(MidiShortMessage& message);

    void clear();

    [[nodiscard]] std::size_t size() const;
    [[nodiscard]] std::size_t capacity() const noexcept;
    [[nodiscard]] std::uint64_t droppedCount() const noexcept;

private:
    const std::size_t capacity_;
    mutable std::mutex mutex_;
    std::deque<MidiShortMessage> queue_;
    std::uint64_t droppedCount_ = 0;
};

/**
 * Stateful MIDI 1.0 byte-stream parser for incoming channel-voice messages.
 *
 * Android MidiReceiver callbacks may contain several messages or fragments of
 * one message, so callback boundaries are deliberately not treated as MIDI
 * message boundaries.
 *
 * System common, system realtime and SysEx bytes are ignored by this
 * channel-voice parser. Realtime bytes may appear between ordinary message
 * bytes without disturbing running status.
 */
class MidiInputParser final {
public:
    void reset() noexcept;

    void feed(
            const std::uint8_t* data,
            std::size_t size,
            std::uint64_t timestampNanos,
            std::uint32_t portId,
            MidiReceiveQueue& queue) noexcept;

private:
    void startStatus(std::uint8_t status) noexcept;
    void emitIfComplete(
            std::uint64_t timestampNanos,
            std::uint32_t portId,
            MidiReceiveQueue& queue) noexcept;

    std::uint8_t runningStatus_ = 0;
    std::uint8_t pendingStatus_ = 0;
    std::uint8_t data_[2]{};
    std::uint8_t dataCount_ = 0;
    std::uint8_t expectedDataCount_ = 0;
    bool inSysEx_ = false;
};

} // namespace mozart::midi
