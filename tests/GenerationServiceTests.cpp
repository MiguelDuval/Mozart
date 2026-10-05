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
    return 0;
}
