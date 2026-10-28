#include "generation/RemiBpeInferenceBackend.h"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

using namespace mozart::generation;

namespace {
class FakeRemiOnnxBridge final : public RemiBpeOnnxInferenceBridge {
public:
    bool available = true;
    int calls = 0;
    std::string artifact;
    std::string manifest;
    std::string tokenizer;
    std::size_t maxTokens = 0;
    RemiBpeTokenInferenceResult result{
        TokenInferenceStatus::Ok, {1, 511, 5119, 11743, 2}, 0.73, 25, {}
    };

    RemiBpeTokenInferenceResult inferRemiBpe(
            const std::string& a, const std::string& m,
            const std::string& t, const std::size_t maximum) override {
        ++calls; artifact=a; manifest=m; tokenizer=t; maxTokens=maximum;
        return result;
    }
    bool isRuntimeAvailable() const noexcept override { return available; }
};

void testReturnsTypedExternalTokenIdsAndPaths() {
    FakeRemiOnnxBridge bridge;
    RemiBpeOnnxTokenInferenceBackend backend(
        "remi-onnx:test", "/private/model.onnx",
        "/private/model.manifest.json", "/private/tokenizer.json", bridge);
    const auto result = backend.generateRemiTokens(GenerationRequest{}, 400);
    assert(result.ok());
    assert(result.tokenIds == std::vector<std::uint32_t>({1,511,5119,11743,2}));
    assert(result.confidence == 0.73);
    assert(result.generationTimeMs == 25);
    assert(bridge.calls == 1);
    assert(bridge.artifact == "/private/model.onnx");
    assert(bridge.manifest == "/private/model.manifest.json");
    assert(bridge.tokenizer == "/private/tokenizer.json");
    assert(bridge.maxTokens == 400);
    // Most important ABI guard: this backend refuses the legacy 512-token API.
    const auto legacy = backend.generateTokens(GenerationRequest{}, 400);
    assert(!legacy.ok());
    assert(legacy.message.find("512-token ABI") != std::string::npos);
}

void testExpectedVocabularySizeMustMatchManifestContract() {
    const auto path = std::filesystem::temp_directory_path() /
        "mozart-remi-bpe-manifest-contract-test.json";
    {
        std::ofstream output(path);
        assert(output.is_open());
        output << R"json({
          "model_format": "onnx",
          "vocabulary_id": "miditok-remi-bpe-v1",
          "vocabulary_size": 12000,
          "runtime": {
            "token_mode": "remi_bpe",
            "external_vocabulary_size": 12000
          }
        })json";
    }

    FakeRemiOnnxBridge bridge;
    RemiBpeOnnxTokenInferenceBackend backend(
        "remi-onnx:test", "/private/model.onnx",
        path.string(), "/private/tokenizer.json", bridge);
    assert(backend.expectedVocabularySize() == 12000);

    {
        std::ofstream output(path, std::ios::trunc);
        assert(output.is_open());
        output << R"json({
          "model_format": "onnx",
          "vocabulary_id": "miditok-remi-bpe-v1",
          "vocabulary_size": 12000,
          "runtime": {
            "token_mode": "remi_bpe",
            "external_vocabulary_size": 512
          }
        })json";
    }
    assert(backend.expectedVocabularySize() == 0);

    std::error_code ignored;
    std::filesystem::remove(path, ignored);
}

void testUnavailableBridgeDoesNotRunInference() {
    FakeRemiOnnxBridge bridge;
    bridge.available = false;
    RemiBpeOnnxTokenInferenceBackend backend(
        "remi-onnx:test", "/private/model.onnx",
        "/private/model.manifest.json", "/private/tokenizer.json", bridge);
    assert(!backend.isAvailable());
    const auto result = backend.generateRemiTokens(GenerationRequest{}, 400);
    assert(result.status == TokenInferenceStatus::Unavailable);
    assert(bridge.calls == 0);
}

void testMissingPathsFailClosed() {
    FakeRemiOnnxBridge bridge;
    RemiBpeOnnxTokenInferenceBackend backend(
        "remi-onnx:test", "/private/model.onnx",
        "/private/model.manifest.json", "", bridge);
    const auto result = backend.generateRemiTokens(GenerationRequest{}, 400);
    assert(result.status == TokenInferenceStatus::Unavailable);
    assert(bridge.calls == 0);
}
} // namespace

int main() {
    testReturnsTypedExternalTokenIdsAndPaths();
    testExpectedVocabularySizeMustMatchManifestContract();
    testUnavailableBridgeDoesNotRunInference();
    testMissingPathsFailClosed();
    return 0;
}
