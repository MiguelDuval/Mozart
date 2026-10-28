#pragma once
#include "generation/TokenInferenceBackend.h"
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace mozart::generation {
struct RemiBpeTokenInferenceResult final {
    TokenInferenceStatus status = TokenInferenceStatus::Failed;
    std::vector<std::uint32_t> tokenIds{};
    double confidence = 0.0;
    std::uint32_t generationTimeMs = 0;
    std::string message{};
    [[nodiscard]] bool ok() const noexcept { return status == TokenInferenceStatus::Ok; }
};

// Typed capability for true MidiTok REMI/BPE IDs. This is deliberately a
// separate output ABI from Mozart's frozen 512-token event vocabulary.
class RemiBpeInferenceBackend : public TokenInferenceBackend {
public:
    ~RemiBpeInferenceBackend() override = default;
    [[nodiscard]] virtual RemiBpeTokenInferenceResult generateRemiTokens(
        const GenerationRequest& request, std::size_t maxTokens) = 0;
    [[nodiscard]] virtual std::string tokenizerArtifactPath() const = 0;
    // Declared model output vocabulary from its manifest. Zero means unavailable/invalid.
    [[nodiscard]] virtual std::size_t expectedVocabularySize() const noexcept { return 0; }

    [[nodiscard]] TokenInferenceResult generateTokens(
        const GenerationRequest&, std::size_t) final {
        return {TokenInferenceStatus::Failed, {}, 0.0, 0,
                "REMI/BPE backend cannot emit the legacy Mozart 512-token ABI"};
    }
};

// Platform bridge for ONNX models that emit next-token logits in MidiTok's
// external REMI/BPE vocabulary. The source checkpoint is unconditioned; the
// current checkpoint therefore does not receive Mozart's conditioning request.
class RemiBpeOnnxInferenceBridge {
public:
    virtual ~RemiBpeOnnxInferenceBridge() = default;
    [[nodiscard]] virtual RemiBpeTokenInferenceResult inferRemiBpe(
        const std::string& artifactPath,
        const std::string& manifestPath,
        const std::string& tokenizerPath,
        std::size_t maxTokens) = 0;
    [[nodiscard]] virtual bool isRuntimeAvailable() const noexcept = 0;
};

class RemiBpeOnnxTokenInferenceBackend final : public RemiBpeInferenceBackend {
public:
    RemiBpeOnnxTokenInferenceBackend(
        std::string backendId,
        std::string artifactPath,
        std::string manifestPath,
        std::string tokenizerPath,
        RemiBpeOnnxInferenceBridge& bridge) noexcept;

    [[nodiscard]] RemiBpeTokenInferenceResult generateRemiTokens(
        const GenerationRequest& request, std::size_t maxTokens) override;
    [[nodiscard]] bool isAvailable() const noexcept override;
    [[nodiscard]] std::string id() const override;
    [[nodiscard]] std::string tokenizerArtifactPath() const override;

private:
    std::string backendId_;
    std::string artifactPath_;
    std::string manifestPath_;
    std::string tokenizerPath_;
    RemiBpeOnnxInferenceBridge& bridge_;
};
} // namespace mozart::generation
