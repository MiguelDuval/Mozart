#pragma once

#include "generation/GenerationRequest.h"

#include <string>

namespace mozart::generation {

[[nodiscard]] std::string serializeGenerationRequestJson(
        const GenerationRequest& request);

} // namespace mozart::generation
