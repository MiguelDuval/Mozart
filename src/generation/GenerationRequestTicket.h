#pragma once

#include <cstdint>
#include <string>
#include <string_view>

namespace mozart::generation {

struct GenerationRequestTicket final {
    std::string modelId{};
    std::uint64_t selectionGeneration = 0;

    [[nodiscard]] bool matches(
            const std::string_view currentModelId,
            const std::uint64_t currentSelectionGeneration) const noexcept {
        return !modelId.empty() &&
                modelId == currentModelId &&
                selectionGeneration == currentSelectionGeneration;
    }
};

} // namespace mozart::generation
