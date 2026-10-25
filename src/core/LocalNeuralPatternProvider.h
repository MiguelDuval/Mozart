#pragma once

#include "GenerationTypes.h"
#include "RemiEventAdapter.h"

#include <memory>
#include <string>
#include <vector>
#include <optional>
#include <chrono>

namespace mozart::generation {

//----------------------------------------------------------------------
// LocalNeuralPatternProvider - AI provider using REMI/BPE model
//----------------------------------------------------------------------
// This provider integrates the REMI event adapter with the
// MusicGenerationProvider interface. It handles:
// - Model inference via ONNX Runtime (when model is loaded)
// - Token decoding via RemiEventAdapter with BPE tokenizer
// - Validation via PatternProposalValidator
// - Async execution and stale result protection

class LocalNeuralPatternProvider final : public MusicGenerationProvider {
public:
    struct Config {
        std::string modelPath;              // Path to ONNX model file
        std::string tokenizerPath;          // Path to tokenizer.json
        RemiDecoderConfig decoderConfig;    // Decoder configuration
        std::uint32_t maxTokens;            // Max tokens to generate
        double temperature;                 // Sampling temperature
        std::optional<std::uint32_t> topK;  // Top-k sampling
        bool useDeterministicFallback;      // Fallback to deterministic if model unavailable

        Config() noexcept = default;
        Config(const std::string& modelPath_, const std::string& tokenizerPath_,
               const RemiDecoderConfig& decoderConfig_, std::uint32_t maxTokens_ = 256,
               double temperature_ = 1.0, std::optional<std::uint32_t> topK_ = std::nullopt,
               bool useDeterministicFallback_ = true) noexcept
            : modelPath(modelPath_), tokenizerPath(tokenizerPath_), decoderConfig(decoderConfig_),
              maxTokens(maxTokens_), temperature(temperature_), topK(topK_),
              useDeterministicFallback(useDeterministicFallback_) {}
    
    explicit LocalNeuralPatternProvider(const Config& config = Config{}) noexcept;
    ~LocalNeuralPatternProvider() override;
    
    // Move only
    LocalNeuralPatternProvider(LocalNeuralPatternProvider&&) noexcept;
    LocalNeuralPatternProvider& operator=(LocalNeuralPatternProvider&&) noexcept;
    LocalNeuralPatternProvider(const LocalNeuralPatternProvider&) = delete;
    LocalNeuralPatternProvider& operator=(const LocalNeuralPatternProvider&) = delete;
    
    // Provider interface
    [[nodiscard]] std::string providerId() const noexcept override;
    [[nodiscard]] std::string modelId() const noexcept override;
    [[nodiscard]] std::string version() const noexcept override;
    [[nodiscard]] bool isAvailable() const noexcept override;
    
    [[nodiscard]] std::optional<PatternProposal> generate(const GenerationRequest& request) override;
    
    [[nodiscard]] bool supportsStyle(const std::string& style) const noexcept override;
    [[nodiscard]] std::vector<std::string> supportedStyles() const noexcept override;
    [[nodiscard]] std::vector<std::string> supportedRoles() const noexcept override;
    
    // Configuration
    void setDecoderConfig(const RemiDecoderConfig& config) noexcept;
    [[nodiscard]] const RemiDecoderConfig& decoderConfig() const noexcept { return adapter_.config(); }
    
    // Model loading (loads ONNX model and tokenizer)
    [[nodiscard]] bool loadModel(const std::string& modelPath);
    void unloadModel() noexcept;
    [[nodiscard]] bool hasModel() const noexcept { return modelLoaded_; }
    
    // Deterministic fallback (RhythmGenerator-based)
    [[nodiscard]] std::optional<PatternProposal> generateDeterministic(const GenerationRequest& request) const noexcept;
    
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
    
    // RemiEventAdapter with BPE tokenizer for token decoding
    RemiEventAdapter adapter_;
    PatternProposalValidator validator_;
    Config config_;
    bool modelLoaded_ = false;
    std::string modelId_ = "edm-finetune";
    std::string providerId_ = "local-neural";
    std::string version_ = "0.1.0";
    
    // Generation request ID for stale result protection
    mutable std::uint64_t requestCounter_ = 0;
    
    // ONNX Runtime session (placeholder for actual inference)
    // std::unique_ptr<Ort::Session> session_;
};

} // namespace mozart::generation
