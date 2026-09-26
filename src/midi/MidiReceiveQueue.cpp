#include "MidiReceiveQueue.h"

#include <algorithm>

namespace mozart::midi {
namespace {

[[nodiscard]] std::uint8_t dataBytesForStatus(
        const std::uint8_t status) noexcept {
    const auto type = static_cast<std::uint8_t>(status & 0xF0u);
    switch (type) {
        case 0xC0:
        case 0xD0:
            return 1;
        case 0x80:
        case 0x90:
        case 0xA0:
        case 0xB0:
        case 0xE0:
            return 2;
        default:
            return 0;
    }
}

[[nodiscard]] bool isChannelVoiceStatus(
        const std::uint8_t value) noexcept {
    return value >= 0x80 && value <= 0xEF;
}

} // namespace

MidiReceiveQueue::MidiReceiveQueue(const std::size_t capacity)
    : capacity_(capacity) {
    queue_.clear();
}

bool MidiReceiveQueue::push(const MidiShortMessage& message) {
    if (!message.isValid() || capacity_ == 0) {
        return false;
    }

    std::lock_guard<std::mutex> lock(mutex_);

    if (queue_.size() >= capacity_) {
        queue_.pop_front();
        ++droppedCount_;
    }

    queue_.push_back(message);
    ++acceptedCount_;
    lastMessage_ = message;
    hasLast_ = true;
    return true;
}

bool MidiReceiveQueue::tryPop(MidiShortMessage& message) {
    std::lock_guard<std::mutex> lock(mutex_);

    if (queue_.empty()) {
        return false;
    }

    message = queue_.front();
    queue_.pop_front();
    return true;
}

void MidiReceiveQueue::clear() {
    std::lock_guard<std::mutex> lock(mutex_);
    queue_.clear();
}

void MidiReceiveQueue::reset() {
    std::lock_guard<std::mutex> lock(mutex_);
    queue_.clear();
    acceptedCount_ = 0;
    droppedCount_ = 0;
    hasLast_ = false;
    lastMessage_ = {};
}

MidiReceiveSnapshot MidiReceiveQueue::snapshot() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return MidiReceiveSnapshot{
        queue_.size(),
        acceptedCount_,
        droppedCount_,
        hasLast_,
        lastMessage_
    };
}

std::size_t MidiReceiveQueue::size() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return queue_.size();
}

std::size_t MidiReceiveQueue::capacity() const noexcept {
    return capacity_;
}

std::uint64_t MidiReceiveQueue::droppedCount() const noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    return droppedCount_;
}

void MidiInputParser::reset() noexcept {
    runningStatus_ = 0;
    pendingStatus_ = 0;
    data_[0] = 0;
    data_[1] = 0;
    dataCount_ = 0;
    expectedDataCount_ = 0;
    inSysEx_ = false;
}

void MidiInputParser::startStatus(const std::uint8_t status) noexcept {
    pendingStatus_ = status;
    dataCount_ = 0;
    expectedDataCount_ = dataBytesForStatus(status);

    if (expectedDataCount_ == 0) {
        pendingStatus_ = 0;
        return;
    }

    // Channel-voice statuses establish or replace running status.
    runningStatus_ = status;
}

void MidiInputParser::emitIfComplete(
        const std::uint64_t timestampNanos,
        const std::uint32_t portId,
        MidiReceiveQueue& queue) noexcept {
    if (pendingStatus_ == 0 || dataCount_ != expectedDataCount_) {
        return;
    }

    MidiShortMessage message{
        pendingStatus_,
        data_[0],
        static_cast<std::uint8_t>(expectedDataCount_ > 1 ? data_[1] : 0),
        static_cast<std::uint8_t>(expectedDataCount_ + 1),
        timestampNanos,
        portId
    };

    queue.push(message);

    dataCount_ = 0;
    // Keep runningStatus_ for MIDI running-status continuation.
    pendingStatus_ = runningStatus_;
    expectedDataCount_ = dataBytesForStatus(pendingStatus_);
}

void MidiInputParser::feed(
        const std::uint8_t* data,
        const std::size_t size,
        const std::uint64_t timestampNanos,
        const std::uint32_t portId,
        MidiReceiveQueue& queue) noexcept {
    if (data == nullptr || size == 0) {
        return;
    }

    for (std::size_t i = 0; i < size; ++i) {
        const auto value = data[i];

        // MIDI realtime messages are single-byte and may be interleaved
        // anywhere without changing running status or parser state.
        if (value >= 0xF8) {
            continue;
        }

        if (inSysEx_) {
            if (value == 0xF7) {
                inSysEx_ = false;
                pendingStatus_ = runningStatus_;
                dataCount_ = 0;
                expectedDataCount_ = dataBytesForStatus(runningStatus_);
            }
            continue;
        }

        if (value == 0xF0) {
            inSysEx_ = true;
            runningStatus_ = 0;
            pendingStatus_ = 0;
            dataCount_ = 0;
            expectedDataCount_ = 0;
            continue;
        }

        if (value & 0x80u) {
            // System common messages are deliberately outside this
            // transport-neutral channel-voice queue.
            if (!isChannelVoiceStatus(value)) {
                runningStatus_ = 0;
                pendingStatus_ = 0;
                dataCount_ = 0;
                expectedDataCount_ = 0;
                continue;
            }

            startStatus(value);
            continue;
        }

        // Data byte. Use running status when a complete status byte has not
        // just been supplied in the current fragment.
        if (pendingStatus_ == 0) {
            if (runningStatus_ == 0) {
                continue;
            }
            pendingStatus_ = runningStatus_;
            expectedDataCount_ = dataBytesForStatus(runningStatus_);
        }

        if (expectedDataCount_ == 0 || dataCount_ >= 2) {
            dataCount_ = 0;
            pendingStatus_ = runningStatus_;
            expectedDataCount_ = dataBytesForStatus(runningStatus_);
        }

        data_[dataCount_++] = value;
        emitIfComplete(timestampNanos, portId, queue);
    }
}

} // namespace mozart::midi
