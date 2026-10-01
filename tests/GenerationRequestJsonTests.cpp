#include "generation/GenerationRequest.h"

#include <cassert>
#include <string>

namespace mozart::platform::android {

std::string jsonForRequest(
        const mozart::generation::GenerationRequest& request);

} // namespace mozart::platform::android

namespace {

void testGenerationRequestSerializesConditioningContract() {
    mozart::generation::GenerationRequest request;
    request.style = mozart::generation::GenerationStyle::Custom;
    request.substyle = mozart::generation::GenerationSubstyle::Custom;
    request.mood = mozart::generation::GenerationMood::Atmospheric;
    request.rhythm = mozart::generation::GenerationRhythm::Broken;
    request.role = mozart::generation::GenerationRole::Texture;
    request.density = 0.125;
    request.energy = 0.25;
    request.syncopation = 0.5;
    request.swing = 0.75;
    request.variation = 1.0;

    const auto json =
            mozart::platform::android::jsonForRequest(request);

    assert(json.find(R"("style":5)") != std::string::npos);
    assert(json.find(R"("substyle":6)") != std::string::npos);
    assert(json.find(R"("mood":6)") != std::string::npos);
    assert(json.find(R"("rhythm":5)") != std::string::npos);
    assert(json.find(R"("role":6)") != std::string::npos);
    assert(json.find(R"("density":0.125)") != std::string::npos);
    assert(json.find(R"("energy":0.25)") != std::string::npos);
    assert(json.find(R"("syncopation":0.5)") != std::string::npos);
    assert(json.find(R"("swing":0.75)") != std::string::npos);
    assert(json.find(R"("variation":1)") != std::string::npos);

    const auto stylePos = json.find(R"("style":5)");
    const auto substylePos = json.find(R"("substyle":6)");
    const auto moodPos = json.find(R"("mood":6)");
    const auto rhythmPos = json.find(R"("rhythm":5)");
    const auto rolePos = json.find(R"("role":6)");
    const auto densityPos = json.find(R"("density":0.125)");
    const auto energyPos = json.find(R"("energy":0.25)");
    const auto syncopationPos = json.find(R"("syncopation":0.5)");
    const auto swingPos = json.find(R"("swing":0.75)");
    const auto variationPos = json.find(R"("variation":1)");

    assert(stylePos < substylePos);
    assert(substylePos < moodPos);
    assert(moodPos < rhythmPos);
    assert(rhythmPos < rolePos);
    assert(rolePos < densityPos);
    assert(densityPos < energyPos);
    assert(energyPos < syncopationPos);
    assert(syncopationPos < swingPos);
    assert(swingPos < variationPos);
}

} // namespace

int main() {
    testGenerationRequestSerializesConditioningContract();
    return 0;
}
