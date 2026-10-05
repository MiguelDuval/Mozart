#include "generation/GenerationService.h"

#include "generation/LocalNeuralPatternProvider.h"

#include <utility>

namespace mozart::generation {

GenerationService::~GenerationService() {
    stop();
}

void GenerationService::start() {
    std::lock_guard<std::mutex> lock(queueMutex_);
    if (running_) {
        return;
    }

    running_ = true;
    worker_ = std::thread(&GenerationService::run, this);
}

void GenerationService::stop() {
    {
        std::lock_guard<std::mutex> lock(queueMutex_);
        if (!running_ && !worker_.joinable()) {
            return;
        }

        running_ = false;

        while (!queue_.empty()) {
            auto job = std::move(queue_.front());
            queue_.pop_front();
            job.promise.set_value({
                    GenerationStatus::Unavailable,
                    {},
                    "generation service stopped",
                    job.ticket
            });
        }
    }

    wakeCondition_.notify_all();

    if (worker_.joinable()) {
        worker_.join();
    }
}

bool GenerationService::running() const noexcept {
    std::lock_guard<std::mutex> lock(queueMutex_);
    return running_;
}

std::future<GenerationResult> GenerationService::unavailableFuture(
        const char* message,
        GenerationRequestTicket ticket) {
    std::promise<GenerationResult> promise;
    auto future = promise.get_future();
    promise.set_value({
            GenerationStatus::Unavailable,
            {},
            message,
            std::move(ticket)
    });
    return future;
}

std::future<GenerationResult> GenerationService::submit(
        GenerationRequest request) {
    const auto modelId = catalog_.selectedModelId();
    TokenInferenceBackend* backend = catalog_.resolveSelectedBackend();
    if (backend == nullptr || modelId.empty()) {
        return unavailableFuture("selected model backend is unavailable");
    }

    Job job;
    job.backend = backend;
    job.request = std::move(request);
    job.ticket = {modelId, catalog_.selectionGeneration()};
    auto future = job.promise.get_future();

    {
        std::lock_guard<std::mutex> lock(queueMutex_);
        if (!running_) {
            job.promise.set_value({
                    GenerationStatus::Unavailable,
                    {},
                    "generation service is stopped",
                    job.ticket
            });
            return future;
        }

        if (queue_.size() >= kMaxPendingRequests) {
            job.promise.set_value({
                    GenerationStatus::Unavailable,
                    {},
                    "generation service queue is full",
                    job.ticket
            });
            return future;
        }

        queue_.push_back(std::move(job));
    }

    wakeCondition_.notify_one();
    return future;
}

void GenerationService::run() {
    while (true) {
        Job job;

        {
            std::unique_lock<std::mutex> lock(queueMutex_);
            wakeCondition_.wait(
                    lock,
                    [this] {
                        return !running_ || !queue_.empty();
                    });

            if (!running_ && queue_.empty()) {
                return;
            }

            job = std::move(queue_.front());
            queue_.pop_front();
        }

        if (job.backend == nullptr) {
            job.promise.set_value({
                    GenerationStatus::Unavailable,
                    {},
                    "selected model backend is unavailable",
                    job.ticket
            });
            continue;
        }

        LocalNeuralPatternProvider provider(*job.backend);
        auto result = provider.generate(job.request);
        result.ticket = job.ticket;
        job.promise.set_value(std::move(result));
    }
}

} // namespace mozart::generation
