#include "MidiSendQueue.h"

namespace mozart::scheduler {

void MidiSendQueue::push(const midi::MidiShortMessage& message) noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    queue_.push(TimestampedMessage{message, message.timestampNanos});
}

bool MidiSendQueue::tryPop(midi::MidiShortMessage& message) noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    if (queue_.empty()) {
        return false;
    }
    message = queue_.top().message;
    queue_.pop();
    return true;
}

bool MidiSendQueue::empty() const noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    return queue_.empty();
}

std::size_t MidiSendQueue::size() const noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    return queue_.size();
}

void MidiSendQueue::clear() noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    while (!queue_.empty()) {
        queue_.pop();
    }
}

} // namespace mozart::scheduler
