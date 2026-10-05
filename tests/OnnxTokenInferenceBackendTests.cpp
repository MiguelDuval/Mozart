#include "generation/OnnxTokenInferenceBackend.h"

#include <cassert>
#include <cstddef>
#include <string>
#include <vector>

using namespace mozart::generation;

namespace {

class FakeBridge final : public OnnxInferenceBridge {
public:
    bool available = true;
    int calls = 0;
    std::string artifactPath{};
    std::string manifestPath{};
    GenerationRequest request{};
    std::size_t maxTokens = 0;
    TokenInferenceResult result{
        TokenInferenceStatus::Ok,
        {1, 2},
        0.5,
        7,
        "fake"
    };

    [[nodiscard]] TokenInferenceResult infer(
            const std::string& artifact,
            const std::string& manifest,
            const GenerationRequest& generationRequest,
            const std::size_t limit) override {
        ++calls;
        artifactPath = artifact;
        manifestPath = manifest;
        request = generationRequest;
        maxTokens = limit;
        return result;
    }

    [[nodiscard]] bool isRuntimeAvailable() const noexcept override {
        return available;
    }
};

void testBackendForwardsInferenceToBridge() {
    FakeBridge bridge;
    OnnxTokenInferenceBackend backend(
            "onnxruntime-android:test",
            "/private/test/model.onnx",
            "/private/test/model.manifest.json",
            bridge);

    assert(backend.id() == "onnxruntime-android:test");
    assert(backend.isAvailable());

    auto request = GenerationRequest{};
    request.seed = 0x1234ABCDu;

    const auto result = backend.generateTokens(request, 321);

    assert(result.status == TokenInferenceStatus::Ok);
    assert(result.tokens == std::vector<MidiEventToken>({1, 2}));
    assert(result.confidence == 0.5);
    assert(result.generationTimeMs == 7);
    assert(result.message == "fake");
    assert(bridge.calls == 1);
    assert(bridge.artifactPath == "/private/test/model.onnx");
    assert(bridge.manifestPath == "/private/test/model.manifest.json");
    assert(bridge.request.seed == request.seed);
    assert(bridge.maxTokens == 321);
}

void testUnavailableRuntimeNeverRunsInference() {
    FakeBridge bridge;
    bridge.available = false;

    OnnxTokenInferenceBackend backend(
            "onnxruntime-android:test",
            "/private/test/model.onnx",
            "/private/test/model.manifest.json",
            bridge);

    assert(!backend.isAvailable());

    const auto result = backend.generateTokens(GenerationRequest{}, 321);

    assert(result.status == TokenInferenceStatus::Unavailable);
    assert(result.message == "ONNX Runtime backend is unavailable");
    assert(bridge.calls == 0);
}

void testMissingArtifactPathIsUnavailable() {
    FakeBridge bridge;

    OnnxTokenInferenceBackend backend(
            "onnxruntime-android:test",
            "",
            "/private/test/model.manifest.json",
            bridge);

    assert(!backend.isAvailable());

    const auto result = backend.generateTokens(GenerationRequest{}, 321);

    assert(result.status == TokenInferenceStatus::Unavailable);
    assert(result.message == "ONNX model artifact path is missing");
    assert(bridge.calls == 0);
}

} // namespace

int main() {
    testBackendForwardsInferenceToBridge();
    testUnavailableRuntimeNeverRunsInference();
    testMissingArtifactPathIsUnavailable();
    return 0;
}
