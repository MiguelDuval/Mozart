#include "generation/ModelCatalog.h"
#include "generation/TokenInferenceBackend.h"

#include <cassert>
#include <string>
#include <vector>

using namespace mozart::generation;

namespace {

class TestBackend final : public TokenInferenceBackend {
public:
    [[nodiscard]] TokenInferenceResult generateTokens(
            const GenerationRequest&,
            std::size_t) override {
        return {};
    }

    [[nodiscard]] bool isAvailable() const noexcept override {
        return true;
    }

    [[nodiscard]] std::string id() const override {
        return "test-backend";
    }
};

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

    assert(catalog.setEnabled(entry.modelId, false));

    assert(catalog.selectedModelId().empty());
    assert(catalog.selectedModel() == nullptr);
    assert(catalog.resolveSelectedBackend() == nullptr);
    assert(!catalog.selectedBackendAvailable());
}

} // namespace

int main() {
    testDisablingSelectedModelClearsSelection();
    return 0;
}
