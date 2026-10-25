#pragma once

// Internal implementation details shared by the provider's split translation units.
// Keep this out of the public header so Impl remains opaque to consumers.
#include "LocalNeuralPatternProvider.h"

#include <memory>
#include <random>

namespace mozart::generation {

struct LocalNeuralPatternProvider::Impl {
    std::mt19937 rng;
    std::uint64_t lastRequestId = 0;
    std::shared_ptr<BpeTokenizer> tokenizer;

    Impl() : rng(std::random_device{}()) {}
};

} // namespace mozart::generation
