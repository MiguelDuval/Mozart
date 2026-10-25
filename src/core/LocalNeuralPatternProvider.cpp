#include "LocalNeuralPatternProvider.h"
#include "GenerationTypes.h"
#include "RemiEventAdapter.h"

#include <algorithm>
#include <chrono>
#include <random>
#include <memory>

namespace mozart::generation {

struct LocalNeuralPatternProvider::Impl {
    std::mt19937 rng;
    std::uint64_t lastRequestId = 0;
    std::shared_ptr<BpeTokenizer> tokenizer;
    
    Impl() : rng(std::random_device{}()) {}
};

LocalNeuralPatternProvider::LocalNeuralPatternProvider(const Config& config) noexcept
    : impl_(std::make_unique<Impl>())
    , adapter_(config.decoderConfig)
    , validator_()
    , config_(config) {
    
    // Load tokenizer if path provided
    if (!config.tokenizerPath.empty()) {
        auto tokenizer = BpeTokenizer::loadFromJson(config.tokenizerPath);
        if (tokenizer.has_value()) {
            impl_->tokenizer = std::make_shared<BpeTokenizer>(std::move(*tokenizer));
            adapter_ = RemiEventAdapter(config.decoderConfig, impl_->tokenizer);
        }
    }
    
    if (!config.modelPath.empty()) {
        loadModel(config.modelPath);
    }
}

LocalNeuralPatternProvider::~LocalNeuralPatternProvider() = default;

LocalNeuralPatternProvider::LocalNeuralPatternProvider(LocalNeuralPatternProvider&& other) noexcept
    : impl_(std::move(other.impl_))
    , adapter_(std::move(other.adapter_))
    , validator_(std::move(other.validator_))
    , config_(std::move(other.config_))
    , modelLoaded_(other.modelLoaded_)
    , modelId_(std::move(other.modelId_))
    , providerId_(std::move(other.providerId_))
    , version_(std::move(other.version_))
    , requestCounter_(other.requestCounter_) {
}

LocalNeuralPatternProvider& LocalNeuralPatternProvider::operator=(LocalNeuralPatternProvider&& other) noexcept {
    if (this != &other) {
        impl_ = std::move(other.impl_);
        adapter_ = std::move(other.adapter_);
        validator_ = std::move(other.validator_);
        config_ = std::move(other.config_);
        modelLoaded_ = other.modelLoaded_;
        modelId_ = std::move(other.modelId_);
        providerId_ = std::move(other.providerId_);
        version_ = std::move(other.version_);
        requestCounter_ = other.requestCounter_;
    }
    return *this;
}

std::string LocalNeuralPatternProvider::providerId() const noexcept {
    return providerId_;
}

std::string LocalNeuralPatternProvider::modelId() const noexcept {
    return modelId_;
}

std::string LocalNeuralPatternProvider::version() const noexcept {
    return version_;
}

bool LocalNeuralPatternProvider::isAvailable() const noexcept {
    return modelLoaded_ || config_.useDeterministicFallback;
}

} // namespace mozart::generation