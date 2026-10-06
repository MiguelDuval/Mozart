#pragma once

#include <atomic>
#include <chrono>
#include <cstdint>
#include <limits>

namespace mozart::scheduler {

struct TimingTelemetrySnapshot {
    std::uint64_t scheduledMessages = 0;
    std::uint64_t enqueuedMessages = 0;
    std::uint64_t sendAttempts = 0;
    std::uint64_t successfulSends = 0;
    std::uint64_t failedSends = 0;
    std::uint64_t lateDispatches = 0;
    std::uint64_t maxLateNanos = 0;
    std::uint64_t jitterSamples = 0;
    std::uint64_t totalJitterNanos = 0;
    std::uint64_t maxJitterNanos = 0;
    double lastScheduledBeat = 0.0;
    std::uint64_t lastScheduledTimestampNanos = 0;
    std::uint64_t lastSendTimestampNanos = 0;

    [[nodiscard]] double meanJitterMicros() const noexcept {
        if (jitterSamples == 0) {
            return 0.0;
        }
        return static_cast<double>(totalJitterNanos) /
                static_cast<double>(jitterSamples) /
                1000.0;
    }

    [[nodiscard]] double maxLateMicros() const noexcept {
        return static_cast<double>(maxLateNanos) / 1000.0;
    }

    [[nodiscard]] double maxJitterMicros() const noexcept {
        return static_cast<double>(maxJitterNanos) / 1000.0;
    }
};

class TimingTelemetry final {
public:
    void reset() noexcept {
        scheduledMessages_.store(0, std::memory_order_relaxed);
        enqueuedMessages_.store(0, std::memory_order_relaxed);
        sendAttempts_.store(0, std::memory_order_relaxed);
        successfulSends_.store(0, std::memory_order_relaxed);
        failedSends_.store(0, std::memory_order_relaxed);
        lateDispatches_.store(0, std::memory_order_relaxed);
        maxLateNanos_.store(0, std::memory_order_relaxed);
        jitterSamples_.store(0, std::memory_order_relaxed);
        totalJitterNanos_.store(0, std::memory_order_relaxed);
        maxJitterNanos_.store(0, std::memory_order_relaxed);
        lastScheduledBeat_.store(0.0, std::memory_order_relaxed);
        lastScheduledTimestampNanos_.store(0, std::memory_order_relaxed);
        lastSendTimestampNanos_.store(0, std::memory_order_relaxed);
        previousScheduledTimestampNanos_.store(0, std::memory_order_relaxed);
        previousSendTimestampNanos_.store(0, std::memory_order_relaxed);
    }

    void recordScheduled(
            const double beat,
            const std::uint64_t timestampNanos,
            const bool enqueued) noexcept {
        scheduledMessages_.fetch_add(1, std::memory_order_relaxed);
        if (enqueued) {
            enqueuedMessages_.fetch_add(1, std::memory_order_relaxed);
        }
        lastScheduledBeat_.store(beat, std::memory_order_relaxed);
        lastScheduledTimestampNanos_.store(
                timestampNanos,
                std::memory_order_relaxed);
    }

    void recordSend(
            const std::uint64_t scheduledTimestampNanos,
            const std::uint64_t actualSendTimestampNanos,
            const bool success) noexcept {
        sendAttempts_.fetch_add(1, std::memory_order_relaxed);
        if (success) {
            successfulSends_.fetch_add(1, std::memory_order_relaxed);
        } else {
            failedSends_.fetch_add(1, std::memory_order_relaxed);
        }

        if (scheduledTimestampNanos == 0) {
            lastSendTimestampNanos_.store(
                    actualSendTimestampNanos,
                    std::memory_order_relaxed);
            return;
        }

        if (actualSendTimestampNanos > scheduledTimestampNanos) {
            const auto lateness =
                    actualSendTimestampNanos - scheduledTimestampNanos;
            lateDispatches_.fetch_add(1, std::memory_order_relaxed);
            atomicMax(maxLateNanos_, lateness);
        }

        const auto previousScheduled =
                previousScheduledTimestampNanos_.exchange(
                        scheduledTimestampNanos,
                        std::memory_order_relaxed);
        const auto previousActual =
                previousSendTimestampNanos_.exchange(
                        actualSendTimestampNanos,
                        std::memory_order_relaxed);

        if (previousScheduled != 0 &&
            previousActual != 0 &&
            actualSendTimestampNanos >= previousActual &&
            scheduledTimestampNanos >= previousScheduled) {
            const auto scheduledInterval =
                    scheduledTimestampNanos - previousScheduled;
            const auto actualInterval =
                    actualSendTimestampNanos - previousActual;
            const auto jitter =
                    actualInterval >= scheduledInterval
                            ? actualInterval - scheduledInterval
                            : scheduledInterval - actualInterval;
            jitterSamples_.fetch_add(1, std::memory_order_relaxed);
            atomicSaturatingAdd(totalJitterNanos_, jitter);
            atomicMax(maxJitterNanos_, jitter);
        }

        lastSendTimestampNanos_.store(
                actualSendTimestampNanos,
                std::memory_order_relaxed);
    }

    [[nodiscard]] TimingTelemetrySnapshot snapshot() const noexcept {
        return {
            scheduledMessages_.load(std::memory_order_relaxed),
            enqueuedMessages_.load(std::memory_order_relaxed),
            sendAttempts_.load(std::memory_order_relaxed),
            successfulSends_.load(std::memory_order_relaxed),
            failedSends_.load(std::memory_order_relaxed),
            lateDispatches_.load(std::memory_order_relaxed),
            maxLateNanos_.load(std::memory_order_relaxed),
            jitterSamples_.load(std::memory_order_relaxed),
            totalJitterNanos_.load(std::memory_order_relaxed),
            maxJitterNanos_.load(std::memory_order_relaxed),
            lastScheduledBeat_.load(std::memory_order_relaxed),
            lastScheduledTimestampNanos_.load(std::memory_order_relaxed),
            lastSendTimestampNanos_.load(std::memory_order_relaxed)
        };
    }

private:
    static void atomicSaturatingAdd(
            std::atomic<std::uint64_t>& target,
            const std::uint64_t value) noexcept {
        auto current = target.load(std::memory_order_relaxed);
        for (;;) {
            if (value > std::numeric_limits<std::uint64_t>::max() - current) {
                if (target.compare_exchange_weak(
                            current,
                            std::numeric_limits<std::uint64_t>::max(),
                            std::memory_order_relaxed,
                            std::memory_order_relaxed)) {
                    return;
                }
                continue;
            }
            if (target.compare_exchange_weak(
                        current,
                        current + value,
                        std::memory_order_relaxed,
                        std::memory_order_relaxed)) {
                return;
            }
        }
    }

    static void atomicMax(
            std::atomic<std::uint64_t>& target,
            const std::uint64_t value) noexcept {
        auto current = target.load(std::memory_order_relaxed);
        while (current < value &&
               !target.compare_exchange_weak(
                       current,
                       value,
                       std::memory_order_relaxed,
                       std::memory_order_relaxed)) {
        }
    }

    std::atomic<std::uint64_t> scheduledMessages_{0};
    std::atomic<std::uint64_t> enqueuedMessages_{0};
    std::atomic<std::uint64_t> sendAttempts_{0};
    std::atomic<std::uint64_t> successfulSends_{0};
    std::atomic<std::uint64_t> failedSends_{0};
    std::atomic<std::uint64_t> lateDispatches_{0};
    std::atomic<std::uint64_t> maxLateNanos_{0};
    std::atomic<std::uint64_t> jitterSamples_{0};
    std::atomic<std::uint64_t> totalJitterNanos_{0};
    std::atomic<std::uint64_t> maxJitterNanos_{0};
    std::atomic<double> lastScheduledBeat_{0.0};
    std::atomic<std::uint64_t> lastScheduledTimestampNanos_{0};
    std::atomic<std::uint64_t> lastSendTimestampNanos_{0};
    std::atomic<std::uint64_t> previousScheduledTimestampNanos_{0};
    std::atomic<std::uint64_t> previousSendTimestampNanos_{0};
};

} // namespace mozart::scheduler
