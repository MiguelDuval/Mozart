#include "core/GenerationTypes.h"
#include "core/RemiEventAdapter.h"
#include "core/RemiDecoderConfig.h"
#include "core/LocalNeuralPatternProvider.h"
#include "generation/RhythmGenerator.h"

#include <cassert>
#include <vector>
#include <string>
#include <iostream>
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <memory>

using namespace mozart::generation;

void testPatternProposalValidation() {
    std::cout << "Testing PatternProposal validation..." << std::endl;
    
    PatternProposal proposal;
    proposal.providerId = "test";
    proposal.modelId = "test-model";
    proposal.totalTicks = 1920;
    proposal.trackCount = 1;
    
    assert(!proposal.isValid());
    assert(proposal.validationError().has_value());
    
    proposal.events.push_back(NoteEvent{60, 100, 0, 480, 0, 0});
    assert(proposal.isValid());
    assert(!proposal.validationError().has_value());
    
    proposal.events.push_back(NoteEvent{64, 100, 2000, 480, 0, 0});
    assert(!proposal.isValid());
    assert(proposal.validationError().has_value());
    
    std::cout << "  PatternProposal validation: PASSED" << std::endl;
}

void testPatternProposalValidator() {
    std::cout << "Testing PatternProposalValidator..." << std::endl;
    
    PatternProposalValidator::Limits limits;
    limits.maxEvents = 10;
    limits.maxTicks = 480 * 4;
    limits.maxTracks = 2;
    limits.maxChannels = 16;
    
    PatternProposalValidator validator(limits);
    
    PatternProposal proposal;
    proposal.totalTicks = 1920;
    proposal.trackCount = 1;
    proposal.events.push_back(NoteEvent{60, 100, 0, 480, 0, 0});
    proposal.events.push_back(NoteEvent{64, 100, 480, 480, 0, 0});
    
    auto report = validator.validate(proposal);
    assert(report.isOk());
    
    PatternProposal tooMany = proposal;
    for (int i = 0; i < 15; ++i) {
        tooMany.events.push_back(NoteEvent{static_cast<std::uint8_t>(60 + i), 100, 
                                           static_cast<std::uint32_t>(i * 100), 480, 0, 0});
    }
    report = validator.validate(tooMany);
    assert(report.result == ValidationResult::TooManyEvents);
    
    PatternProposal badPitch = proposal;
    badPitch.events.push_back(NoteEvent{200, 100, 0, 480, 0, 0});
    report = validator.validate(badPitch);
    assert(report.result == ValidationResult::InvalidPitch);
    
    PatternProposal badVel = proposal;
    badVel.events.push_back(NoteEvent{60, 200, 0, 480, 0, 0});
    report = validator.validate(badVel);
    assert(report.result == ValidationResult::InvalidVelocity);
    
    PatternProposal badChan = proposal;
    badChan.events.push_back(NoteEvent{60, 100, 0, 480, 16, 0});
    report = validator.validate(badChan);
    assert(report.result == ValidationResult::InvalidChannel);
    
    auto [sanitized, sanitizeReport] = validator.sanitize(badPitch);
    assert(sanitizeReport.isOk());
    assert(sanitized.events.size() == 2);
    
    std::cout << "  PatternProposalValidator: PASSED" << std::endl;
}

void testRemiDecoderConfig() {
    std::cout << "Testing RemiDecoderConfig..." << std::endl;
    
    auto config = RemiDecoderConfig::defaultConfig();
    
    assert(config.vocabSize == 12000);
    assert(config.pitchMin == 21);
    assert(config.pitchMax == 109);
    assert(config.numVelocities == 16);
    assert(config.ticksPerBeat == 480);
    assert(config.ticksPerBar == 1920);
    assert(config.padToken == 0);
    assert(config.bosToken == 1);
    assert(config.eosToken == 2);
    assert(config.maskToken == 3);
    assert(config.maxEvents == 1024);
    assert(config.maxBars == 32);
    assert(config.maxTracks == 8);
    assert(config.beatRes["0_4"] == 8);
    assert(config.beatRes["4_12"] == 4);
    
    std::cout << "  RemiDecoderConfig: PASSED" << std::endl;
}

void testRemiEventAdapterConversions() {
    std::cout << "Testing REMI token bin conversions end-to-end..." << std::endl;

    const auto fixturePath =
        std::filesystem::temp_directory_path() / "mozart_remi_conversion_tokenizer_test.json";
    {
        std::ofstream fixture(fixturePath);
        assert(fixture.is_open());
        fixture << R"json({
  "_model": "{\"model\":{\"vocab\":{\"Bar_None\":0,\"Position_0\":1,\"Tempo_0\":2,\"Velocity_0\":3,\"Pitch_60\":4,\"Duration_1.0.8\":5,\"Position_1\":6,\"Tempo_15\":7,\"Velocity_7\":8,\"Pitch_61\":9,\"Position_8\":10,\"Tempo_31\":11,\"Velocity_15\":12,\"Pitch_62\":13},\"merges\":[]}}",
  "config": {"special_tokens": ["PAD_None", "BOS_None", "EOS_None", "MASK_None"]}
})json";
    }

    auto tokenizer = BpeTokenizer::loadFromJson(fixturePath.string());
    std::filesystem::remove(fixturePath);
    assert(tokenizer.has_value());

    auto sharedTokenizer = std::make_shared<BpeTokenizer>(std::move(*tokenizer));
    RemiEventAdapter adapter(RemiDecoderConfig::defaultConfig(), sharedTokenizer);

    // Exercise conversion through the public token-decoding path rather than
    // invoking private bin-conversion helpers directly.
    const std::vector<std::uint32_t> tokenIds{
        0, 1, 2, 3, 4, 5,
        6, 7, 8, 9, 5,
        10, 11, 12, 13, 5
    };
    auto [proposal, report] = adapter.decodeTokensToProposal(tokenIds);

    assert(report.isOk());
    const auto notes = proposal.notes();
    assert(notes.size() == 3);
    assert(notes[0].pitch == 60 && notes[0].position == 0 && notes[0].duration == 480);
    assert(notes[0].velocity == 1);
    assert(notes[1].pitch == 61 && notes[1].position == 60 && notes[1].duration == 480);
    assert(notes[1].velocity >= 60 && notes[1].velocity <= 70);
    assert(notes[2].pitch == 62 && notes[2].position == 480 && notes[2].duration == 480);
    assert(notes[2].velocity == 127);

    std::vector<TempoEvent> tempos;
    for (const auto& event : proposal.events) {
        if (const auto* tempo = std::get_if<TempoEvent>(&event)) {
            tempos.push_back(*tempo);
        }
    }
    assert(tempos.size() == 3);
    assert(tempos[0].bpm == 40.0);
    assert(tempos[1].bpm >= 120.0 && tempos[1].bpm <= 150.0);
    assert(tempos[2].bpm == 250.0);

    std::cout << "  REMI token bin conversions end-to-end: PASSED" << std::endl;
}

int main() {
    try {
        testPatternProposalValidation();
        testPatternProposalValidator();
        testRemiDecoderConfig();
        testRemiEventAdapterConversions();
        std::cout << "\n=== ALL TESTS PASSED (Part 1) ===" << std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "TEST FAILED: " << e.what() << std::endl;
        return 1;
    } catch (...) {
        std::cerr << "TEST FAILED: Unknown exception" << std::endl;
        return 1;
    }
}