#include "generation/GenerationRequestJson.h"

#include <sstream>

namespace mozart::generation {

std::string serializeGenerationRequestJson(
        const GenerationRequest& request) {
    std::ostringstream json;
    json << R"({"style":)" << static_cast<int>(request.style)
         << R"(,"substyle":)" << static_cast<int>(request.substyle)
         << R"(,"mood":)" << static_cast<int>(request.mood)
         << R"(,"rhythm":)" << static_cast<int>(request.rhythm)
         << R"(,"role":)" << static_cast<int>(request.role)
         << R"(,"root_pitch_class":)"
         << static_cast<int>(request.keyScale.rootPitchClass())
         << R"(,"scale":)"
         << static_cast<int>(request.keyScale.scale())
         << R"(,"tempo_bpm":)" << request.tempoBpm
         << R"(,"bars":)" << static_cast<int>(request.bars)
         << R"(,"polyphony":)" << static_cast<int>(request.polyphony)
         << R"(,"min_note":)" << static_cast<int>(request.minNote)
         << R"(,"max_note":)" << static_cast<int>(request.maxNote)
         << R"(,"density":)" << request.density
         << R"(,"probability":)" << request.probability
         << R"(,"ratchet":)" << static_cast<int>(request.ratchet)
         << R"(,"energy":)" << request.energy
         << R"(,"syncopation":)" << request.syncopation
         << R"(,"swing":)" << request.swing
         << R"(,"variation":)" << request.variation
         << R"(,"seed":)" << request.seed
         << "}";
    return json.str();
}

} // namespace mozart::generation
