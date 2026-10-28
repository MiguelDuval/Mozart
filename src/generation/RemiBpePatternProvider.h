#pragma once
#include "generation/LocalPatternProvider.h"
#include "generation/RemiBpeInferenceBackend.h"
#include "remi/BpeTokenizer.h"
#include "remi/RemiDecoderConfig.h"
#include <cstddef>
#include <memory>
#include <optional>
#include <string>

namespace mozart::generation {
// Converts raw MidiTok REMI/BPE IDs into Mozart's common PatternProposal.
// Call only from the non-realtime generation worker.
class RemiBpePatternProvider final {
public:
    static constexpr std::size_t kMaxGeneratedTokens = 16384;
    explicit RemiBpePatternProvider(RemiBpeInferenceBackend& backend);
    [[nodiscard]] GenerationResult generate(const GenerationRequest& request);
    [[nodiscard]] bool tokenizerReady() const noexcept {
        return tokenizer_ != nullptr && config_.has_value() && initializationError_.empty();
    }
    [[nodiscard]] const std::string& initializationError() const noexcept {
        return initializationError_;
    }
private:
    [[nodiscard]] GenerationResult failed(GenerationStatus status, std::string message) const;
    RemiBpeInferenceBackend& backend_;
    std::optional<remi::RemiDecoderConfig> config_;
    std::shared_ptr<remi::BpeTokenizer> tokenizer_;
    std::string initializationError_;
};
} // namespace mozart::generation
