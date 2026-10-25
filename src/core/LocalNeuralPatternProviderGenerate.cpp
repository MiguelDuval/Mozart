#include "LocalNeuralPatternProvider.h"
#include "GenerationTypes.h"
#include "RemiEventAdapter.h"

#include <algorithm>
#include <chrono>
#include <filesystem>

namespace mozart::generation {

std::optional<PatternProposal> LocalNeuralPatternProvider::generate(const GenerationRequest& request) {
    const std::uint64_t requestId = ++requestCounter_;
    impl_->lastRequestId = requestId;
    
    if (!modelLoaded_) {
        if (config_.useDeterministicFallback) {
            return generateDeterministic(request);
        }
        return std::nullopt;
    }
    
    // Stale result protection: if a new request came in during generation, discard this result
    if (requestId != requestCounter_) {
        return std::nullopt;
    }
    
    // TODO: Actual model inference via ONNX Runtime
    // 1. Prepare input tensor (token sequence with BOS token)
    // 2. Run autoregressive generation loop:
    //    - Run session_->Run() with current sequence
    //    - Sample next token from logits (temperature, top-k)
    //    - Append to sequence
    //    - Stop on EOS token or maxTokens
    // 3. Decode token IDs via adapter_.decodeTokensToProposal()
    // 4. Validate via validator_.sanitize()
    
    // For now, use deterministic fallback
    return generateDeterministic(request);
}

bool LocalNeuralPatternProvider::supportsStyle(const std::string& style) const noexcept {
    static const std::vector<std::string> supported = {
        "edm", "electronic", "house", "techno", "trance", "dubstep",
        "drum and bass", "ambient", "synthwave"
    };
    return std::find(supported.begin(), supported.end(), style) != supported.end();
}

std::vector<std::string> LocalNeuralPatternProvider::supportedStyles() const noexcept {
    return {"edm", "electronic", "house", "techno", "trance", "dubstep", "drum and bass", "ambient", "synthwave"};
}

std::vector<std::string> LocalNeuralPatternProvider::supportedRoles() const noexcept {
    return {"lead", "bass", "drums", "pad", "arp", "fx"};
}

void LocalNeuralPatternProvider::setDecoderConfig(const RemiDecoderConfig& config) noexcept {
    // Preserve tokenizer when updating config
    adapter_ = RemiEventAdapter(config, impl_->tokenizer);
}

bool LocalNeuralPatternProvider::loadModel(const std::string& modelPath) {
    // Load tokenizer first if not already loaded
    if (!impl_->tokenizer && !config_.tokenizerPath.empty()) {
        auto tokenizer = BpeTokenizer::loadFromJson(config_.tokenizerPath);
        if (tokenizer.has_value()) {
            impl_->tokenizer = std::make_shared<BpeTokenizer>(std::move(*tokenizer));
            adapter_ = RemiEventAdapter(config_.decoderConfig, impl_->tokenizer);
        }
    }
    
    // TODO: Load ONNX model
    // try {
    //     Ort::SessionOptions sessionOptions;
    //     sessionOptions.SetIntraOpNumThreads(1);
    //     sessionOptions.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
    //     
    //     Ort::Environment env(ORT_LOGGING_LEVEL_WARNING, "Mozart");
    //     impl_->session = std::make_unique<Ort::Session>(env, modelPath.c_str(), sessionOptions);
    //     
    //     // Verify input/output shapes match expected (vocab_size=12000, block_size=1024)
    //     
    //     modelLoaded_ = true;
    //     return true;
    // } catch (const Ort::Exception& e) {
    //     modelLoaded_ = false;
    //     return false;
    // }
    
    // Placeholder: model loading not yet implemented
    modelLoaded_ = false;
    return false;
}

void LocalNeuralPatternProvider::unloadModel() noexcept {
    // impl_->session.reset();
    modelLoaded_ = false;
}

} // namespace mozart::generation