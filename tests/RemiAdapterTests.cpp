#include "core/GenerationTypes.h"
#include "core/RemiEventAdapter.h"
#include "core/RemiDecoderConfig.h"
#include "core/LocalNeuralPatternProvider.h"
#include "generation/RhythmGenerator.h"

#include <cassert>
#include <filesystem>
#include <fstream>
#include <vector>
#include <string>
#include <iostream>
#include <algorithm>
#include <limits>

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

void testRemiDecoderConfigSafeJsonParsing() {
    std::cout << "Testing safe RemiDecoderConfig JSON parsing..." << std::endl;
    const auto path =
        std::filesystem::temp_directory_path() / "mozart_remi_decoder_config_safe_parse.json";
    {
        std::ofstream fixture(path);
        assert(fixture.is_open());
        fixture << R"json({
  "config": {
    "pitch_range": [60, 300],
    "beat_res": {"0_4": 0, "4_12": 4},
    "num_velocities": 32,
    "num_tempos": 256,
    "tempo_range": [240.0, 80.0]
  }
})json";
    }

    const auto config = RemiDecoderConfig::fromTokenizerJson(path.string());
    std::filesystem::remove(path);
    assert(config.pitchMin == 21);
    assert(config.pitchMax == 109);
    assert(config.numVelocities == 32); // Valid fields survive unrelated invalid fields.
    assert(config.numTempos == 32);      // 256 must not wrap to uint8_t.
    assert(config.tempoMin == 40.0 && config.tempoMax == 250.0);
    assert(config.beatRes.at("0_4") == 8 && config.beatRes.at("4_12") == 4);

    std::cout << "  Safe RemiDecoderConfig JSON parsing: PASSED" << std::endl;
}

void testRemiEventAdapterConvertEventBounds() {
    std::cout << "Testing single-event conversion bounds..." << std::endl;
    const auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);

    auto note = adapter.convertEvent(RemiNoteOnEvent{60, 100, 0, 0}, 480, 0, 64);
    assert(note.has_value());
    assert(std::holds_alternative<NoteEvent>(*note));
    assert(std::get<NoteEvent>(*note).position == 480);
    assert(std::get<NoteEvent>(*note).duration == config.ticksPerBeat / 4);

    assert(!adapter.convertEvent(RemiNoteOnEvent{10, 100, 0, 0}, 0, 0, 64).has_value());
    assert(!adapter.convertEvent(RemiNoteOnEvent{60, 100, 0, config.maxTracks}, 0, 0, 64).has_value());
    assert(!adapter.convertEvent(
        RemiNoteOnEvent{60, 100, 0, 0},
        std::numeric_limits<std::uint32_t>::max() - 10U, 0, 64).has_value());
    assert(!adapter.convertEvent(
        RemiNoteOnEvent{60, 100, std::numeric_limits<std::uint32_t>::max() - 100U, 0},
        0, 0, 64).has_value());

    assert(!adapter.convertEvent(
        RemiTempoEvent{std::numeric_limits<double>::infinity()}, 0, 0, 64).has_value());
    assert(!adapter.convertEvent(RemiTimeSignatureEvent{4, 3}, 0, 0, 64).has_value());
    assert(!adapter.convertEvent(RemiProgramEvent{0, config.maxTracks}, 0, 0, 64).has_value());
    std::cout << "  Single-event conversion bounds: PASSED" << std::endl;
}

void testRemiEventAdapterConversions() {
    std::cout << "Testing RemiEventAdapter conversions..." << std::endl;

    auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);

    assert(adapter.velocityBinToMidi(0) == 1);
    assert(adapter.velocityBinToMidi(15) == 127);
    assert(adapter.velocityBinToMidi(7) >= 60 && adapter.velocityBinToMidi(7) <= 70);

    assert(adapter.positionBinToTicks(0) == 0);
    assert(adapter.positionBinToTicks(1) == 60);
    assert(adapter.positionBinToTicks(8) == 480);

    assert(adapter.tempoBinToBpm(0) == 40.0);
    assert(adapter.tempoBinToBpm(31) == 250.0);
    assert(adapter.tempoBinToBpm(15) >= 120.0 && adapter.tempoBinToBpm(15) <= 150.0);
    assert(adapter.velocityBinToMidi(255) == 127);
    assert(adapter.tempoBinToBpm(255) == config.tempoMax);

    auto singleBinConfig = config;
    singleBinConfig.numVelocities = 1;
    singleBinConfig.numTempos = 1;
    singleBinConfig.tempoMin = 80.0;
    singleBinConfig.tempoMax = 180.0;
    RemiEventAdapter singleBinAdapter(singleBinConfig);
    assert(singleBinAdapter.velocityBinToMidi(0) == 64);
    assert(singleBinAdapter.velocityBinToMidi(1) == 64);
    assert(singleBinAdapter.tempoBinToBpm(0) == 80.0);
    assert(singleBinAdapter.tempoBinToBpm(255) == 80.0);

    std::cout << "  RemiEventAdapter conversions: PASSED" << std::endl;
}

int main() {
    try {
        testPatternProposalValidation();
        testPatternProposalValidator();
        testRemiDecoderConfig();
        testRemiDecoderConfigSafeJsonParsing();
        testRemiEventAdapterConversions();
        testRemiEventAdapterConvertEventBounds();
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