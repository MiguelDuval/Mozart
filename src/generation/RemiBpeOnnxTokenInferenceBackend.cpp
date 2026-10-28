#include "generation/RemiBpeInferenceBackend.h"
#include "json.hpp"
#include <fstream>
#include <utility>

namespace mozart::generation {
RemiBpeOnnxTokenInferenceBackend::RemiBpeOnnxTokenInferenceBackend(
        std::string backendId,
        std::string artifactPath,
        std::string manifestPath,
        std::string tokenizerPath,
        RemiBpeOnnxInferenceBridge& bridge) noexcept
    : backendId_(std::move(backendId)),
      artifactPath_(std::move(artifactPath)),
      manifestPath_(std::move(manifestPath)),
      tokenizerPath_(std::move(tokenizerPath)),
      bridge_(bridge) {}

RemiBpeTokenInferenceResult RemiBpeOnnxTokenInferenceBackend::generateRemiTokens(
        const GenerationRequest& request, const std::size_t maxTokens) {
    (void) request; // This checkpoint's manifest explicitly says it is unconditioned.
    if (backendId_.empty() || artifactPath_.empty() ||
        manifestPath_.empty() || tokenizerPath_.empty()) {
        return {TokenInferenceStatus::Unavailable, {}, 0.0, 0,
                "REMI/BPE ONNX backend paths or ID are missing"};
    }
    if (maxTokens < 2) {
        return {TokenInferenceStatus::Failed, {}, 0.0, 0,
                "REMI/BPE max token count is too small"};
    }
    if (!bridge_.isRuntimeAvailable()) {
        return {TokenInferenceStatus::Unavailable, {}, 0.0, 0,
                "REMI/BPE ONNX Runtime backend is unavailable"};
    }
    return bridge_.inferRemiBpe(
        artifactPath_, manifestPath_, tokenizerPath_, maxTokens);
}

bool RemiBpeOnnxTokenInferenceBackend::isAvailable() const noexcept {
    return !backendId_.empty() && !artifactPath_.empty() &&
           !manifestPath_.empty() && !tokenizerPath_.empty() &&
           bridge_.isRuntimeAvailable();
}
std::string RemiBpeOnnxTokenInferenceBackend::id() const { return backendId_; }
std::string RemiBpeOnnxTokenInferenceBackend::tokenizerArtifactPath() const {
    return tokenizerPath_;
}

std::size_t RemiBpeOnnxTokenInferenceBackend::expectedVocabularySize() const noexcept {
    try {
        std::ifstream input(manifestPath_);
        if (!input.is_open()) return 0;
        nlohmann::json manifest;
        input >> manifest;
        const auto vocabularySize = manifest.at("vocabulary_size").get<std::size_t>();
        const auto& runtime = manifest.at("runtime");
        if (manifest.value("model_format", std::string{}) != "onnx" ||
            manifest.value("vocabulary_id", std::string{}) != "miditok-remi-bpe-v1" ||
            runtime.value("token_mode", std::string{}) != "remi_bpe" ||
            runtime.at("external_vocabulary_size").get<std::size_t>() != vocabularySize ||
            vocabularySize == 0) {
            return 0;
        }
        return vocabularySize;
    } catch (...) {
        return 0;
    }
}
} // namespace mozart::generation
