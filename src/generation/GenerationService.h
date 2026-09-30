#pragma once

#include "generation/GenerationResult.h"
#include "generation/ModelCatalog.h"

#include <condition_variable>
#include <cstddef>
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
    void stop();

    [[nodiscard]] bool running() const noexcept;

    // Resolves the selected backend on the caller thread, then queues the
    // request for the dedicated worker. The backend itself is never invoked
    // on the caller thread.
    [[nodiscard]] std::future<GenerationResult> submit(
            GenerationRequest request);

private:
    struct Job final {
        TokenInferenceBackend* backend = nullptr;
        GenerationRequest request{};
        std::promise<GenerationResult> promise{};
    };

    [[nodiscard]] static std::future<GenerationResult> unavailableFuture(
            const char* message);

    void run();

    ModelCatalog& catalog_;

    mutable std::mutex queueMutex_;
    std::condition_variable wakeCondition_;
    std::deque<Job> queue_;
    bool running_ = false;
    std::thread worker_;
};

} // namespace mozart::generation
