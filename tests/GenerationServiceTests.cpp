#include "generation/GenerationService.h"
#include "generation/ModelCatalog.h"
#include "generation/TokenInferenceBackend.h"

#include <cassert>
#include <chrono>
#include <future>
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
    testGenerationRunsOffCallerThread();
    testBackendAvailabilityRunsOnWorkerThread();
    testUnavailableSelectionDoesNotEnterWorker();
    testUnselectedModelIsUnavailable();
    testStoppedServiceRejectsRequestWithoutBackendCall();
    return 0;
}
