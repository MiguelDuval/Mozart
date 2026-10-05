#pragma once

#include "generation/GenerationRequest.h"
#include "generation/PatternProposal.h"
#include "generation/GenerationRequestTicket.h"

#include <cstdint>
#include <string>

namespace mozart::generation {

enum class GenerationStatus : std::uint8_t {
    Ok = 0,
    InvalidRequest = 1,
    Unavailable = 2,
    Failed = 3
};

struct GenerationResult final {
    GenerationStatus status = GenerationStatus::Failed;
    PatternProposal proposal{};
    std::string message{};
    GenerationRequestTicket ticket{};

    [[nodiscard]] bool ok() const noexcept {
        return status == GenerationStatus::Ok && proposal.isWellFormed();
    }
};

// Worker-thread service only. Never invoke from a realtime audio callback,
// MIDI transport callback, or scheduler timing loop.
class LocalPatternProvider {
public:
    virtual ~LocalPatternProvider() = default;

    [[nodiscard]] virtual GenerationResult generate(
            const GenerationRequest& request) = 0;

    [[nodiscard]] virtual bool isAvailable() const noexcept = 0;
};

} // namespace mozart::generation
