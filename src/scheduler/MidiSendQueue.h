#pragma once

#include "core/MidiTypes.h"

#include <cstddef>
#include <cstdint>
#include <mutex>
#include <queue>
#include <vector>

namespace mozart::scheduler {

//----------------------------------------------------------------------
// MidiSendQueue - thread-safe priority queue of timestamped MIDI messages
//----------------------------------------------------------------------
// Messages are ordered by timestampNanos so the earliest-scheduled message
// is always popped first. Safe for concurrent push/pop from different threads
// (e.g. scheduler pushes, transport thread pops).
//
// No musical decision logic lives here — only byte transport ordering.
//----------------------------------------------------------------------

class MidiSendQueue final {
public:
    MidiSendQueue() = default;
    ~MidiSendQueue() = default;

    MidiSendQueue(const MidiSendQueue&) = delete;
    MidiSendQueue& operator=(const MidiSendQueue&) = delete;
    MidiSendQueue(MidiSendQueue&&) = default;
    MidiSendQueue& operator=(MidiSendQueue&&) = default;

    // Push a MIDI message into the queue. Thread-safe.
    void push(const midi::MidiShortMessage& message) noexcept;

    // Pop the earliest message by timestamp. Returns false if queue is empty.
    // Thread-safe.
    bool tryPop(midi::MidiShortMessage& message) noexcept;

    // Return true if no messages are queued. Thread-safe.
    [[nodiscard]] bool empty() const noexcept;

    // Number of messages currently queued. Thread-safe.
    [[nodiscard]] std::size_t size() const noexcept;

    // Remove all messages from the queue. Thread-safe.
    void clear() noexcept;

private:
    struct TimestampedMessage {
        midi::MidiShortMessage message;
        std::uint64_t timestampNanos = 0;
        std::uint64_t insertionOrder = 0;

        [[nodiscard]] bool operator>(const TimestampedMessage& other) const noexcept {
            if (timestampNanos != other.timestampNanos) {
                return timestampNanos > other.timestampNanos;
            }
            return insertionOrder > other.insertionOrder;
        }
    };

    std::priority_queue<
        TimestampedMessage,
        std::vector<TimestampedMessage>,
        std::greater<TimestampedMessage>
    > queue_;

    std::uint64_t nextInsertionOrder_ = 0;
    mutable std::mutex mutex_;
};

} // namespace mozart::scheduler
