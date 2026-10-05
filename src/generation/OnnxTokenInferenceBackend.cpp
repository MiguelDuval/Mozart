#include "generation/OnnxTokenInferenceBackend.h"

#include <utility>

namespace mozart::generation {

OnnxTokenInferenceBackend::OnnxTokenInferenceBackend(
        std::string backendId,
        std::string artifactPath,
        std::string manifestPath,
        OnnxInferenceBridge& bridge) noexcept
    : backendId_(std::move(backendId)),
      artifactPath_(std::move(artifactPath)),
      manifestPath_(std::move(manifestPath)),
      bridge_(bridge) {}

TokenInferenceResult OnnxTokenInferenceBackend::generateTokens(
        const GenerationRequest& request,
        const std::size_t maxTokens) {
    if (backendId_.empty()) {
        return {
                TokenInferenceStatus::Unavailable,
                {},
                0.0,
                0,
                "ONNX backend id is missing"
        };
    }

    if (artifactPath_.empty()) {
        return {
                TokenInferenceStatus::Unavailable,
                {},
                0.0,
                0,
                "ONNX model artifact path is missing"
        };
    }

    if (manifestPath_.empty()) {
        return {
                TokenInferenceStatus::Unavailable,
                {},
                0.0,
                0,
                "ONNX model manifest path is missing"
        };
    }

    if (maxTokens < 2) {
        return {
                TokenInferenceStatus::Failed,
                {},
                0.0,
                0,
                "ONNX max token count is too small"
        };
    }

    if (!bridge_.isRuntimeAvailable()) {
        return {
                TokenInferenceStatus::Unavailable,
                {},
                0.0,
                0,
                "ONNX Runtime backend is unavailable"
        };
    }

    return bridge_.infer(
            artifactPath_,
            manifestPath_,
            request,
            maxTokens);
}

bool OnnxTokenInferenceBackend::isAvailable() const noexcept {
    return !backendId_.empty() &&
            !artifactPath_.empty() &&
            !manifestPath_.empty() &&
            bridge_.isRuntimeAvailable();
}

std::string OnnxTokenInferenceBackend::id() const {
    return backendId_;
}

} // namespace mozart::generation
