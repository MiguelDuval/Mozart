#include "generation/GenerationService.h"
#include "generation/ModelCatalog.h"
#include "generation/TokenInferenceBackend.h"

#include <cassert>
#include <chrono>
#include <future>
#include <atomic>
#include <condition_variable>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

using namespace mozart::generation;

namespace {

class WorkerBackend final : public TokenInferenceBackend {
public:
    bool available = true;
    std::thread::id executionThread{};
    mutable std::thread::id availabilityThread{};
    int calls = 0;

    [[nodiscard]] TokenInferenceResult generateTokens(
            const GenerationRequest&,
            std::size_t) override {
        executionThread = std::this_thread::get_id();
        ++calls;
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
        return {
                TokenInferenceStatus::Failed,
                {},
                0.0,
                5,
                "worker-test"
        };
    }

    [[nodiscard]] bool isAvailable() const noexcept override {
        availabilityThread = std::this_thread::get_id();
        return available;
    }

    [[nodiscard]] std::string id() const override {
        return "worker-test-backend";
    }
};

class BlockingBackend final : public TokenInferenceBackend {
public:
    std::string backendId = "blocking-test-backend";

    [[nodiscard]] TokenInferenceResult generateTokens(
            const GenerationRequest&,
            std::size_t) override {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            entered_ = true;
        }
        condition_.notify_all();

        std::unique_lock<std::mutex> lock(mutex_);
        condition_.wait(lock, [this] { return release_; });

        return {
                TokenInferenceStatus::Failed,
                {},
                0.0,
                0,
                "blocking-test"
        };
    }

    [[nodiscard]] bool isAvailable() const noexcept override {
        return true;
    }

    [[nodiscard]] std::string id() const override {
        return backendId;
    }

    void waitUntilEntered() {
        std::unique_lock<std::mutex> lock(mutex_);
        assert(condition_.wait_for(
                lock,
                std::chrono::seconds(1),
                [this] { return entered_; }));
    }

    void release() {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            release_ = true;
        }
        condition_.notify_all();
    }

private:
    mutable std::mutex mutex_;
    std::condition_variable condition_;
    bool entered_ = false;
    bool release_ = false;
};

ModelCatalogEntry experimentalEntry() {
    ModelCatalogEntry entry;
    entry.modelId = "experimental-worker";
    entry.displayName = "Experimental Worker";
    entry.backendId = "worker-test-backend";
    entry.artifactPath = "/private/experimental-worker/model";
    entry.manifestPath = "/private/experimental-worker/manifest";
    entry.distributionClass = ModelDistributionClass::PrivateExperimental;
    return entry;
}

void testLifecycleGenerationChangesAtSessionBoundaries() {
    ModelCatalog catalog;
    WorkerBackend backend;

    assert(catalog.registerBackend(backend));
    assert(catalog.registerModel(experimentalEntry()));
    assert(catalog.selectModel("experimental-worker"));

    GenerationService service(catalog);
    assert(service.lifecycleGeneration() == 0);

    service.start();
    const auto firstGeneration = service.lifecycleGeneration();
    assert(firstGeneration == 1);

    service.stop();
    const auto stoppedGeneration = service.lifecycleGeneration();
    assert(stoppedGeneration == firstGeneration + 1);

    service.start();
    assert(service.lifecycleGeneration() == stoppedGeneration + 1);

    service.stop();
}

void testStopWaitsForActiveInference() {
    ModelCatalog catalog;
    BlockingBackend backend;

    assert(catalog.registerBackend(backend));
    ModelCatalogEntry entry = experimentalEntry();
    entry.backendId = backend.id();
    entry.modelId = "experimental-blocking";
    entry.displayName = "Experimental Blocking";
    assert(catalog.registerModel(entry));
    assert(catalog.selectModel(entry.modelId));

    GenerationService service(catalog);
    service.start();
    const auto sessionGeneration = service.lifecycleGeneration();

    auto future = service.submit(GenerationRequest{});
    backend.waitUntilEntered();

    std::atomic_bool stopFinished{false};
    std::thread stopper([&] {
        service.stop();
        stopFinished.store(true);
    });

    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    assert(!stopFinished.load());

    backend.release();
    stopper.join();

    assert(stopFinished.load());
    assert(future.wait_for(std::chrono::seconds(1)) == std::future_status::ready);
    const auto result = future.get();
    assert(result.status == GenerationStatus::Failed);
    assert(result.message == "blocking-test");
    assert(result.ticket.lifecycleGeneration == sessionGeneration);
    assert(service.lifecycleGeneration() == sessionGeneration + 1);
}

void testGenerationRunsOffCallerThread() {
    ModelCatalog catalog;
    WorkerBackend backend;

    assert(catalog.registerBackend(backend));
    assert(catalog.registerModel(experimentalEntry()));
    assert(catalog.selectModel("experimental-worker"));

    GenerationService service(catalog);
    service.start();

    const auto callerThread = std::this_thread::get_id();
    const auto selectionGeneration = catalog.selectionGeneration();
    auto future = service.submit(GenerationRequest{});

    assert(future.wait_for(std::chrono::seconds(1)) == std::future_status::ready);
    const auto result = future.get();

    assert(result.status == GenerationStatus::Failed);
    assert(result.message == "worker-test");
    assert(result.ticket.matches("experimental-worker", selectionGeneration));
    assert(result.ticket.lifecycleGeneration == service.lifecycleGeneration());
    assert(backend.calls == 1);
    assert(backend.executionThread != callerThread);

    service.stop();
}


void testBackendAvailabilityRunsOnWorkerThread() {
    ModelCatalog catalog;
    WorkerBackend backend;

    assert(catalog.registerBackend(backend));
    assert(catalog.registerModel(experimentalEntry()));
    assert(catalog.selectModel("experimental-worker"));

    GenerationService service(catalog);
    service.start();

    const auto callerThread = std::this_thread::get_id();
    auto future = service.submit(GenerationRequest{});

    assert(future.wait_for(std::chrono::seconds(1)) == std::future_status::ready);
    (void) future.get();

    assert(backend.availabilityThread != callerThread);

    service.stop();
}


void testInvalidRequestIsRejectedBeforeWorkerQueue() {
    ModelCatalog catalog;
    WorkerBackend backend;

    assert(catalog.registerBackend(backend));
    assert(catalog.registerModel(experimentalEntry()));
    assert(catalog.selectModel("experimental-worker"));

    GenerationService service(catalog);
    service.start();

    GenerationRequest invalid;
    invalid.tempoBpm = 10.0;

    auto future = service.submit(invalid);
    assert(future.wait_for(std::chrono::seconds(1)) == std::future_status::ready);
    const auto result = future.get();

    assert(result.status == GenerationStatus::InvalidRequest);
    assert(result.message == "invalid generation request");
    assert(backend.calls == 0);
    assert(result.ticket.modelId.empty());

    service.stop();
}

void testUnavailableSelectionDoesNotEnterWorker() {
    ModelCatalog catalog;
    WorkerBackend backend;

    assert(catalog.registerBackend(backend));
    assert(catalog.registerModel(experimentalEntry()));
    assert(catalog.selectModel("experimental-worker"));
    backend.available = false;

    GenerationService service(catalog);
    service.start();

    auto future = service.submit(GenerationRequest{});
    assert(future.wait_for(std::chrono::seconds(1)) == std::future_status::ready);
    const auto result = future.get();

    assert(result.status == GenerationStatus::Unavailable);
    assert(backend.calls == 0);

    service.stop();
}

void testUnselectedModelIsUnavailable() {
    ModelCatalog catalog;
    WorkerBackend backend;

    assert(catalog.registerBackend(backend));
    assert(catalog.registerModel(experimentalEntry()));

    GenerationService service(catalog);
    service.start();

    auto future = service.submit(GenerationRequest{});
    assert(future.wait_for(std::chrono::seconds(1)) == std::future_status::ready);
    const auto result = future.get();

    assert(result.status == GenerationStatus::Unavailable);
    assert(backend.calls == 0);
}

void testStartWaitsForConcurrentStop() {
    ModelCatalog catalog;
    BlockingBackend backend;

    assert(catalog.registerBackend(backend));
    ModelCatalogEntry entry = experimentalEntry();
    entry.backendId = backend.id();
    entry.modelId = "experimental-restart-race";
    entry.displayName = "Experimental Restart Race";
    assert(catalog.registerModel(entry));
    assert(catalog.selectModel(entry.modelId));

    GenerationService service(catalog);
    service.start();
    const auto firstGeneration = service.lifecycleGeneration();

    auto future = service.submit(GenerationRequest{});
    backend.waitUntilEntered();

    std::thread stopper([&] { service.stop(); });

    const auto stopDeadline =
            std::chrono::steady_clock::now() + std::chrono::seconds(1);
    while (service.running() &&
            std::chrono::steady_clock::now() < stopDeadline) {
        std::this_thread::yield();
    }
    assert(!service.running());

    std::atomic_bool restartFinished{false};
    std::thread restarter([&] {
        service.start();
        restartFinished.store(true);
    });

    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    assert(!restartFinished.load());

    backend.release();
    stopper.join();
    restarter.join();

    assert(restartFinished.load());
    assert(service.running());
    assert(service.lifecycleGeneration() == firstGeneration + 2);

    assert(
            future.wait_for(std::chrono::seconds(1)) ==
            std::future_status::ready);
    assert(future.get().status == GenerationStatus::Failed);

    service.stop();
}

void testBoundedQueueWithConcurrentSubmit() {
    ModelCatalog catalog;
    BlockingBackend backend;

    assert(catalog.registerBackend(backend));
    ModelCatalogEntry entry = experimentalEntry();
    entry.backendId = backend.id();
    entry.modelId = "experimental-bounded";
    entry.displayName = "Experimental Bounded";
    assert(catalog.registerModel(entry));
    assert(catalog.selectModel(entry.modelId));

    GenerationService service(catalog);
    service.start();

    auto activeFuture = service.submit(GenerationRequest{});
    backend.waitUntilEntered();

    constexpr std::size_t kConcurrentSubmits = 5;
    std::vector<std::future<GenerationResult>> futures(kConcurrentSubmits);
    std::vector<std::thread> submitters;
    submitters.reserve(kConcurrentSubmits);

    for (std::size_t index = 0; index < kConcurrentSubmits; ++index) {
        submitters.emplace_back([&, index] {
            futures[index] = service.submit(GenerationRequest{});
        });
    }

    for (auto& submitter : submitters) {
        submitter.join();
    }

    std::size_t immediatelyReady = 0;
    for (auto& future : futures) {
        if (future.wait_for(std::chrono::milliseconds(0)) ==
                std::future_status::ready) {
            ++immediatelyReady;
        }
    }

    assert(immediatelyReady ==
            kConcurrentSubmits - GenerationService::kMaxPendingRequests);

    backend.release();

    std::size_t accepted = 0;
    std::size_t rejected = 0;
    for (auto& future : futures) {
        assert(
                future.wait_for(std::chrono::seconds(1)) ==
                std::future_status::ready);
        const auto result = future.get();
        if (result.status == GenerationStatus::Failed) {
            ++accepted;
            assert(result.message == "blocking-test");
        } else {
            assert(result.status == GenerationStatus::Unavailable);
            assert(result.message == "generation service queue is full");
            ++rejected;
        }
    }

    assert(accepted == GenerationService::kMaxPendingRequests);
    assert(rejected ==
            kConcurrentSubmits - GenerationService::kMaxPendingRequests);

    assert(
            activeFuture.wait_for(std::chrono::seconds(1)) ==
            std::future_status::ready);
    assert(activeFuture.get().status == GenerationStatus::Failed);
    service.stop();
}

void testStopDrainsQueuedJobsButWaitsForActiveInference() {
    ModelCatalog catalog;
    BlockingBackend backend;

    assert(catalog.registerBackend(backend));
    ModelCatalogEntry entry = experimentalEntry();
    entry.backendId = backend.id();
    entry.modelId = "experimental-stop-queue";
    entry.displayName = "Experimental Stop Queue";
    assert(catalog.registerModel(entry));
    assert(catalog.selectModel(entry.modelId));

    GenerationService service(catalog);
    service.start();

    auto activeFuture = service.submit(GenerationRequest{});
    backend.waitUntilEntered();
    auto queuedFutureA = service.submit(GenerationRequest{});
    auto queuedFutureB = service.submit(GenerationRequest{});

    std::thread stopper([&] { service.stop(); });

    const auto deadline =
            std::chrono::steady_clock::now() + std::chrono::seconds(1);
    while (service.running() &&
            std::chrono::steady_clock::now() < deadline) {
        std::this_thread::yield();
    }

    assert(!service.running());

    assert(
            queuedFutureA.wait_for(std::chrono::milliseconds(0)) ==
            std::future_status::ready);
    assert(
            queuedFutureB.wait_for(std::chrono::milliseconds(0)) ==
            std::future_status::ready);
    const auto queuedResultA = queuedFutureA.get();
    const auto queuedResultB = queuedFutureB.get();
    assert(queuedResultA.status == GenerationStatus::Unavailable);
    assert(queuedResultA.message == "generation service stopped");
    assert(queuedResultB.status == GenerationStatus::Unavailable);
    assert(queuedResultB.message == "generation service stopped");

    assert(
            activeFuture.wait_for(std::chrono::milliseconds(0)) !=
            std::future_status::ready);

    backend.release();
    stopper.join();

    assert(
            activeFuture.wait_for(std::chrono::seconds(1)) ==
            std::future_status::ready);
    assert(activeFuture.get().status == GenerationStatus::Failed);
}

void testSelectionSwitchInvalidatesPendingAndInFlightTickets() {
    ModelCatalog catalog;
    BlockingBackend backend;

    assert(catalog.registerBackend(backend));
    ModelCatalogEntry entry = experimentalEntry();
    entry.backendId = backend.id();
    entry.modelId = "experimental-switch";
    entry.displayName = "Experimental Switch";
    assert(catalog.registerModel(entry));
    assert(catalog.selectModel(entry.modelId));

    GenerationService service(catalog);
    service.start();

    const auto firstSelectionGeneration = catalog.selectionGeneration();
    auto activeFuture = service.submit(GenerationRequest{});
    backend.waitUntilEntered();

    assert(catalog.selectModel(entry.modelId));
    const auto secondSelectionGeneration = catalog.selectionGeneration();
    assert(secondSelectionGeneration == firstSelectionGeneration + 1);

    auto queuedFuture = service.submit(GenerationRequest{});

    backend.release();

    assert(
            activeFuture.wait_for(std::chrono::seconds(1)) ==
            std::future_status::ready);
    const auto activeResult = activeFuture.get();
    assert(activeResult.ticket.modelId == entry.modelId);
    assert(activeResult.ticket.selectionGeneration ==
            firstSelectionGeneration);

    assert(
            queuedFuture.wait_for(std::chrono::seconds(1)) ==
            std::future_status::ready);
    const auto queuedResult = queuedFuture.get();
    assert(queuedResult.ticket.modelId == entry.modelId);
    assert(queuedResult.ticket.selectionGeneration ==
            secondSelectionGeneration);

    service.stop();
}

void testStoppedServiceRejectsRequestWithoutBackendCall() {
    ModelCatalog catalog;
    WorkerBackend backend;

    assert(catalog.registerBackend(backend));
    assert(catalog.registerModel(experimentalEntry()));
    assert(catalog.selectModel("experimental-worker"));

    GenerationService service(catalog);
    const auto selectionGeneration = catalog.selectionGeneration();
    auto future = service.submit(GenerationRequest{});

    assert(future.wait_for(std::chrono::seconds(1)) == std::future_status::ready);
    const auto result = future.get();

    assert(result.status == GenerationStatus::Unavailable);
    assert(result.ticket.matches("experimental-worker", selectionGeneration));
    assert(backend.calls == 0);
}

} // namespace

int main() {
    testLifecycleGenerationChangesAtSessionBoundaries();
    testStopWaitsForActiveInference();
    testGenerationRunsOffCallerThread();
    testInvalidRequestIsRejectedBeforeWorkerQueue();
    testBackendAvailabilityRunsOnWorkerThread();
    testUnavailableSelectionDoesNotEnterWorker();
    testUnselectedModelIsUnavailable();
    testStoppedServiceRejectsRequestWithoutBackendCall();
    testStartWaitsForConcurrentStop();
    testBoundedQueueWithConcurrentSubmit();
    testStopDrainsQueuedJobsButWaitsForActiveInference();
    testSelectionSwitchInvalidatesPendingAndInFlightTickets();
    return 0;
}
