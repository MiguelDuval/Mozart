#pragma once

#include "midi/MidiTransport.h"

#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <queue>
#include <thread>
#include <vector>

namespace mozart::scheduler {

class MidiSendQueue final {
public:
    explicit MidiSendQueue(
            midi::MidiOutputTransport& transport,
            std::size_t capacity = 512);

    ~MidiSendQueue();

    MidiSendQueue(const MidiSendQueue&) = delete;
    MidiSendQueue& operator=(const MidiSendQueue&) = delete;

    void start();
    void stop();

    [[nodiscard]] bool enqueue(
            const midi::MidiShortMessage& message) noexcept;

private:
    struct Item {
        midi::MidiShortMessage message;
        std::uint64_t sequence = 0;
    };

    struct EarlierFirst {
        bool operator()(const Item& lhs, const Item& rhs) const noexcept;
    };

    void run();

    midi::MidiOutputTransport& transport_;
    const std::size_t capacity_;

    std::mutex mutex_;
    std::condition_variable condition_;
    std::priority_queue<Item, std::vector<Item>, EarlierFirst> queue_;

    bool running_ = false;
    std::thread worker_;
    std::uint64_t nextSequence_ = 0;
};

} // namespace mozart::scheduler
