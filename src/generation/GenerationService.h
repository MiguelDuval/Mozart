#pragma once

#include "generation/LocalPatternProvider.h"
#include "generation/ModelCatalog.h"
#include "generation/GenerationRequestTicket.h"

#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <future>
#include <mutex>
#include <thread>

namespace mozart::generation {

class GenerationService final {
public:
    static constexpr std::size_t kMaxPendingRequests = 2;

    explicit GenerationService(ModelCatalog& catalog) noexcept
        : catalog_(catalog) {}

    ~GenerationService();

    GenerationService(const GenerationService&) = delete;
    GenerationService& operator=(const GenerationService&) = delete;

    void start();
    // Stops accepting new requests, drains queued jobs, and waits for any
    // active backend inference to return. Backend inference is currently
    // non-cancellable, so stop() may block until the backend completes.
    void stop();

    [[nodiscard]] bool running() const noexcept;

    [[nodiscard]] std::uint64_t lifecycleGeneration() const noexcept;

    // Resolves the selected backend on the caller thread, then queues the
    // request for the dedicated worker. The backend itself is never invoked
    // on the caller thread.
    [[nodiscard]] std::future<GenerationResult> submit(
            GenerationRequest request);

private:
    struct Job final {
        TokenInferenceBackend* backend = nullptr;
        GenerationRequest request{};
        GenerationRequestTicket ticket{};
        std::promise<GenerationResult> promise{};
    };

    [[nodiscard]] static std::future<GenerationResult> completedFuture(
            GenerationStatus status,
            const char* message,
            GenerationRequestTicket ticket = {});

    void run();

    ModelCatalog& catalog_;

    mutable std::mutex queueMutex_;
    std::condition_variable wakeCondition_;
    std::deque<Job> queue_;
    bool running_ = false;
    std::uint64_t lifecycleGeneration_ = 0;
    std::thread worker_;
};

} // namespace mozart::generation
