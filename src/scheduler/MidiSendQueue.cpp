#include "MidiSendQueue.h"

namespace mozart::scheduler {

MidiSendQueue::MidiSendQueue(
        midi::MidiOutputTransport& transport,
        const std::size_t capacity)
    : transport_(transport),
      capacity_(capacity) {}

MidiSendQueue::~MidiSendQueue() {
    stop();
}

bool MidiSendQueue::EarlierFirst::operator()(
        const Item& lhs,
        const Item& rhs) const noexcept {
    if (lhs.message.timestampNanos != rhs.message.timestampNanos) {
        return lhs.message.timestampNanos > rhs.message.timestampNanos;
    }

    return lhs.sequence > rhs.sequence;
}

void MidiSendQueue::start() {
    std::lock_guard<std::mutex> lock(mutex_);

    if (running_) {
        return;
    }

    running_ = true;
    worker_ = std::thread(&MidiSendQueue::run, this);
}

void MidiSendQueue::stop() {
    {
        std::lock_guard<std::mutex> lock(mutex_);

        if (!running_ && !worker_.joinable()) {
            return;
        }

        running_ = false;
    }

    condition_.notify_all();

    if (worker_.joinable()) {
        worker_.join();
    }

    std::lock_guard<std::mutex> lock(mutex_);
    while (!queue_.empty()) {
        queue_.pop();
    }
}

bool MidiSendQueue::enqueue(
        const midi::MidiShortMessage& message) noexcept {
    if (!message.isValid()) {
        return false;
    }

    {
        std::lock_guard<std::mutex> lock(mutex_);

        if (!running_ || queue_.size() >= capacity_) {
            return false;
        }

        queue_.push(Item{message, nextSequence_++});
    }

    condition_.notify_one();
    return true;
}

void MidiSendQueue::run() {
    for (;;) {
        Item item{};

        {
            std::unique_lock<std::mutex> lock(mutex_);
            condition_.wait(lock, [this] {
                return !running_ || !queue_.empty();
            });

            if (!running_ && queue_.empty()) {
                return;
            }

            item = queue_.top();
            queue_.pop();
        }

        (void) transport_.send(item.message);
    }
}

} // namespace mozart::scheduler
