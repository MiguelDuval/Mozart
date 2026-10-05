#include "generation/ModelCatalog.h"
#include "generation/TokenInferenceBackend.h"

#include <cassert>
#include <atomic>
#include <string>
#include <thread>
#include <vector>

using namespace mozart::generation;

namespace {

class TestBackend final : public TokenInferenceBackend {
public:
    explicit TestBackend(bool available = true) noexcept
        : available_(available) {}

    [[nodiscard]] TokenInferenceResult generateTokens(
            const GenerationRequest&,
            std::size_t) override {
        return {};
    }

    [[nodiscard]] bool isAvailable() const noexcept override {
        ++availabilityCalls_;
        return available_;
    }

    [[nodiscard]] int availabilityCalls() const noexcept {
        return availabilityCalls_.load();
    }

    [[nodiscard]] std::string id() const override {
        return "test-backend";
    }

private:
    bool available_ = true;
    mutable std::atomic_int availabilityCalls_{0};
};

void testSelectionDefersRuntimeAvailabilityToWorker() {
    ModelCatalog catalog;
    TestBackend unavailableBackend(false);

    ModelCatalogEntry entry;
    entry.modelId = "experimental-unavailable";
    entry.displayName = "Experimental Unavailable";
    entry.backendId = unavailableBackend.id();
    entry.artifactPath = "/private/experimental/model.onnx";
    entry.manifestPath = "/private/experimental/model.manifest";

    assert(catalog.registerBackend(unavailableBackend));
    assert(catalog.registerModel(entry));
    assert(catalog.selectModel(entry.modelId));
    assert(catalog.selectedModelId() == entry.modelId);
    assert(unavailableBackend.availabilityCalls() == 0);

    ModelCatalogEntry missingBackendEntry = entry;
    missingBackendEntry.modelId = "experimental-missing-backend";
    missingBackendEntry.displayName = "Experimental Missing Backend";
    missingBackendEntry.backendId = "missing-backend";
    assert(catalog.registerModel(missingBackendEntry));
    assert(!catalog.selectModel(missingBackendEntry.modelId));
    assert(catalog.selectedModelId() == entry.modelId);
}


void testSelectionGenerationInvalidatesPriorResults() {
    ModelCatalog catalog;
    TestBackend backend;

    assert(catalog.selectionGeneration() == 0);
    assert(catalog.registerBackend(backend));

    ModelCatalogEntry first;
    first.modelId = "experimental-a";
    first.displayName = "Experimental A";
    first.backendId = backend.id();
    first.artifactPath = "/private/experimental-a/model.onnx";
    first.manifestPath = "/private/experimental-a/manifest";
    assert(catalog.registerModel(first));

    assert(catalog.selectModel(first.modelId));
    const auto firstGeneration = catalog.selectionGeneration();
    assert(firstGeneration == 1);

    const auto snapshot = catalog.selectionSnapshot();
    assert(snapshot.modelId == first.modelId);
    assert(snapshot.backend == &backend);
    assert(snapshot.selectionGeneration == firstGeneration);

    assert(catalog.selectModel(first.modelId));
    assert(catalog.selectionGeneration() == firstGeneration + 1);

    catalog.clearSelection();
    assert(catalog.selectedModelId().empty());
    assert(catalog.selectionGeneration() == firstGeneration + 2);

    const auto clearedSnapshot = catalog.selectionSnapshot();
    assert(clearedSnapshot.modelId.empty());
    assert(clearedSnapshot.backend == nullptr);
    assert(clearedSnapshot.selectionGeneration == firstGeneration + 2);
}

void testDisablingSelectedModelClearsSelection() {
    ModelCatalog catalog;
    TestBackend backend;

    assert(catalog.registerBackend(backend));

    ModelCatalogEntry entry;
    entry.modelId = "experimental-a";
    entry.displayName = "Experimental A";
    entry.backendId = backend.id();
    entry.artifactPath = "/private/experimental-a/model.onnx";
    entry.manifestPath = "/private/experimental-a/model.manifest";
    entry.distributionClass = ModelDistributionClass::PrivateExperimental;

    assert(catalog.registerModel(entry));
    assert(catalog.selectModel(entry.modelId));
    assert(catalog.selectedModelId() == entry.modelId);
    assert(catalog.resolveSelectedBackend() == &backend);
    assert(catalog.selectedBackendRegistered());
    assert(catalog.selectionGeneration() == 1);

    assert(catalog.setEnabled(entry.modelId, false));

    assert(catalog.selectedModelId().empty());
    assert(!catalog.selectedModelSnapshot().has_value());
    assert(catalog.resolveSelectedBackend() == nullptr);
    assert(!catalog.selectedBackendRegistered());
    assert(catalog.selectionGeneration() == 2);
}


void testConcurrentRegistrationAndSelectionSnapshotIsSafe() {
    ModelCatalog catalog;
    TestBackend backend;

    assert(catalog.registerBackend(backend));

    ModelCatalogEntry seed;
    seed.modelId = "seed";
    seed.displayName = "Seed";
    seed.backendId = backend.id();
    seed.artifactPath = "/private/seed/model.onnx";
    seed.manifestPath = "/private/seed/manifest";
    assert(catalog.registerModel(seed));
    assert(catalog.selectModel(seed.modelId));

    constexpr int kModelsToRegister = 256;
    std::atomic_bool registrationDone{false};
    std::atomic_int registrationFailures{0};

    std::thread registrar([&] {
        for (int index = 0; index < kModelsToRegister; ++index) {
            ModelCatalogEntry entry;
            entry.modelId = "concurrent-" + std::to_string(index);
            entry.displayName = "Concurrent " + std::to_string(index);
            entry.backendId = backend.id();
            entry.artifactPath = "/private/concurrent/model.onnx";
            entry.manifestPath = "/private/concurrent/manifest";
            if (!catalog.registerModel(std::move(entry))) {
                registrationFailures.fetch_add(1);
            }
        }
        registrationDone.store(true, std::memory_order_release);
    });

    std::thread reader([&] {
        while (!registrationDone.load(std::memory_order_acquire)) {
            const auto snapshot = catalog.selectionSnapshot();
            assert(snapshot.modelId == "seed");
            assert(snapshot.backend == &backend);
            const auto modelSnapshot = catalog.findModelSnapshot("seed");
            assert(modelSnapshot.has_value());
            assert(modelSnapshot->modelId == "seed");
            assert(modelSnapshot->backendId == backend.id());
            assert(catalog.selectedBackendRegistered());
            (void) catalog.modelCount();
            (void) catalog.backendCount();
        }
    });

    registrar.join();
    reader.join();

    assert(registrationFailures.load() == 0);
    assert(catalog.modelCount() == static_cast<std::size_t>(kModelsToRegister + 1));
    const auto finalSnapshot = catalog.selectionSnapshot();
    assert(finalSnapshot.modelId == "seed");
    assert(finalSnapshot.backend == &backend);
}

} // namespace

int main() {
    testSelectionDefersRuntimeAvailabilityToWorker();
    testSelectionGenerationInvalidatesPriorResults();
    testConcurrentRegistrationAndSelectionSnapshotIsSafe();
    testDisablingSelectedModelClearsSelection();
    return 0;
}
