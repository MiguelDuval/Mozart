#pragma once

#include "generation/LocalPatternProvider.h"

namespace mozart::generation {

class DeterministicPatternProvider final : public LocalPatternProvider {
public:
    [[nodiscard]] GenerationResult generate(
            const GenerationRequest& request) override;

    [[nodiscard]] bool isAvailable() const noexcept override {
        return true;
    }
};

} // namespace mozart::generation
