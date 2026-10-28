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

// Typed capability for models whose token IDs use a MidiTok REMI/BPE vocabulary.
// Implementations run only on GenerationService's worker and return one complete
// BOS ... EOS stream. These IDs must never be reinterpreted as Mozart's 512-token ABI.
class RemiBpeInferenceBackend : public TokenInferenceBackend {
public:
    ~RemiBpeInferenceBackend() override = default;
    [[nodiscard]] virtual RemiBpeTokenInferenceResult generateRemiTokens(
        const GenerationRequest& request, std::size_t maxTokens) = 0;
    [[nodiscard]] virtual std::string tokenizerArtifactPath() const = 0;

    // Fail closed if this backend is accidentally routed through the legacy provider.
    [[nodiscard]] TokenInferenceResult generateTokens(
        const GenerationRequest&, std::size_t) final {
        return {TokenInferenceStatus::Failed, {}, 0.0, 0,
                "REMI/BPE backend cannot emit the legacy Mozart 512-token ABI"};
    }
};
} // namespace mozart::generation
