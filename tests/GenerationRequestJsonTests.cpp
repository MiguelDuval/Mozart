#include "generation/GenerationRequest.h"
#include "generation/GenerationRequestFactory.h"
#include "generation/PatternDensity.h"
#include "generation/PatternSwing.h"
#include "generation/GenerationRequestJson.h"

#include <cassert>
#include <string>

namespace {

void testFactoryControlsReachConditioningJson() {
    const auto request =
            mozart::generation::GenerationRequestFactory::fromPerformanceContext(
                    mozart::musical::KeyScale{
                            7,
                            mozart::musical::Scale::Dorian},
                    133.0,
                    mozart::generation::GenerationRole::Arpeggio,
                    mozart::generation::PatternDensity::Normal,
                    mozart::generation::PatternSwing::Light,
                    64,
                    32,
                    0xCAFEBABEu);

    assert(request.style == mozart::generation::GenerationStyle::Techno);
    assert(request.substyle == mozart::generation::GenerationSubstyle::Techno);
    assert(request.mood == mozart::generation::GenerationMood::Driving);
    assert(request.rhythm == mozart::generation::GenerationRhythm::Straight);
    assert(request.role == mozart::generation::GenerationRole::Arpeggio);

    const auto json =
            mozart::generation::serializeGenerationRequestJson(request);

    assert(json.find(R"("style":1)") != std::string::npos);
    assert(json.find(R"("substyle":1)") != std::string::npos);
    assert(json.find(R"("mood":1)") != std::string::npos);
    assert(json.find(R"("rhythm":0)") != std::string::npos);
    assert(json.find(R"("role":1)") != std::string::npos);
    assert(json.find(R"("density":0.75)") != std::string::npos);
    assert(json.find(R"("swing":0.5)") != std::string::npos);
    assert(json.find(R"("energy":0.503937)") != std::string::npos);
    assert(json.find(R"("syncopation":0.26378)") != std::string::npos);
    assert(json.find(R"("variation":0.376378)") != std::string::npos);
    assert(json.find(R"("tempo_bpm":133)") != std::string::npos);
    assert(json.find(R"("root_pitch_class":7)") != std::string::npos);
    assert(json.find(R"("scale":2)") != std::string::npos);
    assert(json.find(R"("seed":3405691582)") != std::string::npos);
}

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
            mozart::generation::serializeGenerationRequestJson(request);

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
    testFactoryControlsReachConditioningJson();
    testGenerationRequestSerializesConditioningContract();
    return 0;
}
