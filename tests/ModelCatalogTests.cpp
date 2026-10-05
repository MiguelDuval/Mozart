#include "generation/ModelCatalog.h"
#include "generation/TokenInferenceBackend.h"

#include <cassert>
#include <string>
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
        return available_;
    }

    [[nodiscard]] std::string id() const override {
        return "test-backend";
    }

private:
    bool available_ = true;
};

void testSelectionRequiresReadyBackend() {
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
    assert(!catalog.selectModel(entry.modelId));
    assert(catalog.selectedModelId().empty());

    ModelCatalogEntry missingBackendEntry = entry;
    missingBackendEntry.modelId = "experimental-missing-backend";
    missingBackendEntry.displayName = "Experimental Missing Backend";
    missingBackendEntry.backendId = "missing-backend";
    assert(catalog.registerModel(missingBackendEntry));
    assert(!catalog.selectModel(missingBackendEntry.modelId));
    assert(catalog.selectedModelId().empty());
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

    assert(catalog.selectModel(first.modelId));
    assert(catalog.selectionGeneration() == firstGeneration + 1);

    catalog.clearSelection();
    assert(catalog.selectedModelId().empty());
    assert(catalog.selectionGeneration() == firstGeneration + 2);
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
    assert(catalog.selectedBackendAvailable());
    assert(catalog.selectionGeneration() == 1);

    assert(catalog.setEnabled(entry.modelId, false));

    assert(catalog.selectedModelId().empty());
    assert(catalog.selectedModel() == nullptr);
    assert(catalog.resolveSelectedBackend() == nullptr);
    assert(!catalog.selectedBackendAvailable());
    assert(catalog.selectionGeneration() == 2);
}

} // namespace

int main() {
    testSelectionRequiresReadyBackend();
    testSelectionGenerationInvalidatesPriorResults();
    testDisablingSelectedModelClearsSelection();
    return 0;
}
