#pragma once

#include "generation/TokenInferenceBackend.h"

#include <cstddef>
#include <string>

namespace mozart::generation {

// Platform bridge for an ONNX runtime implementation. The bridge owns all
// runtime-specific details; the portable backend only owns Mozart's contract.
class OnnxInferenceBridge {
public:
    virtual ~OnnxInferenceBridge() = default;

    [[nodiscard]] virtual TokenInferenceResult infer(
            const std::string& artifactPath,
            const std::string& manifestPath,
            const GenerationRequest& request,
            std::size_t maxTokens) = 0;

    [[nodiscard]] virtual bool isRuntimeAvailable() const noexcept = 0;
};

class OnnxTokenInferenceBackend final : public TokenInferenceBackend {
public:
    OnnxTokenInferenceBackend(
            std::string backendId,
            std::string artifactPath,
            std::string manifestPath,
            OnnxInferenceBridge& bridge) noexcept;

    [[nodiscard]] TokenInferenceResult generateTokens(
            const GenerationRequest& request,
            std::size_t maxTokens) override;

    [[nodiscard]] bool isAvailable() const noexcept override;
    [[nodiscard]] std::string id() const override;

private:
    std::string backendId_;
    std::string artifactPath_;
    std::string manifestPath_;
    OnnxInferenceBridge& bridge_;
};

} // namespace mozart::generation
