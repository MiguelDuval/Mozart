#pragma once

#include "generation/LocalPatternProvider.h"
#include "generation/TokenInferenceBackend.h"

namespace mozart::generation {

class LocalNeuralPatternProvider final : public LocalPatternProvider {
public:
    explicit LocalNeuralPatternProvider(TokenInferenceBackend& backend) noexcept
        : backend_(backend) {}

    [[nodiscard]] GenerationResult generate(
            const GenerationRequest& request) override;

    [[nodiscard]] bool isAvailable() const noexcept override {
        return backend_.isAvailable();
    }

private:
    TokenInferenceBackend& backend_;
};

} // namespace mozart::generation
