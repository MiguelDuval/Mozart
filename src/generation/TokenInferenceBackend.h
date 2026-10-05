#pragma once

#include "generation/GenerationRequest.h"
#include "generation/MidiEventVocabulary.h"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace mozart::generation {

enum class TokenInferenceStatus : std::uint8_t {
    Ok = 0,
    Unavailable = 1,
    Failed = 2
};

struct TokenInferenceResult final {
    TokenInferenceStatus status = TokenInferenceStatus::Failed;
    std::vector<MidiEventToken> tokens{};
    double confidence = 0.0;
    std::uint32_t generationTimeMs = 0;
    std::string message{};

    [[nodiscard]] bool ok() const noexcept {
        return status == TokenInferenceStatus::Ok;
    }
};

// Worker-thread service only. The backend must never be invoked from
// realtime audio, MIDI transport, Link timing, or scheduler callbacks.
class TokenInferenceBackend {
public:
    virtual ~TokenInferenceBackend() = default;

    [[nodiscard]] virtual TokenInferenceResult generateTokens(
            const GenerationRequest& request,
            std::size_t maxTokens) = 0;

    [[nodiscard]] virtual bool isAvailable() const noexcept = 0;

    [[nodiscard]] virtual std::string id() const = 0;
};

} // namespace mozart::generation
