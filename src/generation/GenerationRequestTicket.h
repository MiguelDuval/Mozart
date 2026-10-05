#pragma once

#include <cstdint>
#include <string>
#include <string_view>

namespace mozart::generation {

struct GenerationRequestTicket final {
    std::string modelId{};
    std::uint64_t selectionGeneration = 0;
    std::uint64_t lifecycleGeneration = 0;

    [[nodiscard]] bool matches(
            const std::string_view currentModelId,
            const std::uint64_t currentSelectionGeneration) const noexcept {
        return !modelId.empty() &&
                modelId == currentModelId &&
                selectionGeneration == currentSelectionGeneration;
    }

    [[nodiscard]] bool matchesLifecycle(
            const std::string_view currentModelId,
            const std::uint64_t currentSelectionGeneration,
            const std::uint64_t currentLifecycleGeneration) const noexcept {
        return matches(currentModelId, currentSelectionGeneration) &&
                lifecycleGeneration == currentLifecycleGeneration;
    }
};

} // namespace mozart::generation
