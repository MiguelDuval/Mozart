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

using namespace mozart::generation;

void testLocalNeuralPatternProviderFallback() {
    std::cout << "Testing LocalNeuralPatternProvider deterministic fallback..." << std::endl;
    
    LocalNeuralPatternProvider::Config config;
    config.useDeterministicFallback = true;
    config.decoderConfig = RemiDecoderConfig::defaultConfig();
    
    LocalNeuralPatternProvider provider(config);
    
    assert(provider.providerId() == "local-neural");
    assert(provider.modelId() == "edm-finetune");
    assert(provider.isAvailable());
    assert(!provider.hasModel());
    
    GenerationRequest request;
    request.barCount = 4;
    request.targetBpm = 140.0;
    request.seed = 12345;
    
    auto proposal = provider.generate(request);
    assert(proposal.has_value());
    
    assert(proposal->providerId == "local-neural-deterministic");
    assert(proposal->modelId == "deterministic-fallback");
    assert(proposal->seed == 12345);
    assert(proposal->totalTicks > 0);
    assert(proposal->trackCount >= 1);
    
    auto tempo = proposal->firstTempo();
    assert(tempo.has_value());
    assert(tempo->bpm == 140.0);
    
    auto notes = proposal->notes();
    assert(notes.size() > 0);
    
    // Test reproducibility
    auto proposal2 = provider.generate(request);
    assert(proposal2.has_value());
    assert(proposal->events.size() == proposal2->events.size());
    assert(proposal->seed == proposal2->seed);
    
    for (size_t i = 0; i < proposal->events.size(); ++i) {
        const auto& e1 = proposal->events[i];
        const auto& e2 = proposal2->events[i];
        assert(e1.index() == e2.index());
    }
    
    std::cout << "  LocalNeuralPatternProvider fallback: PASSED" << std::endl;
}

void testLocalNeuralPatternProviderStyles() {
    std::cout << "Testing LocalNeuralPatternProvider style support..." << std::endl;
    
    LocalNeuralPatternProvider::Config config;
    config.useDeterministicFallback = true;
    LocalNeuralPatternProvider provider(config);
    
    assert(provider.supportsStyle("edm"));
    assert(provider.supportsStyle("house"));
    assert(provider.supportsStyle("techno"));
    assert(!provider.supportsStyle("classical"));
    assert(!provider.supportsStyle("jazz"));
    
    auto styles = provider.supportedStyles();
    assert(std::find(styles.begin(), styles.end(), "edm") != styles.end());
    assert(std::find(styles.begin(), styles.end(), "house") != styles.end());
    
    auto roles = provider.supportedRoles();
    assert(std::find(roles.begin(), roles.end(), "lead") != roles.end());
    assert(std::find(roles.begin(), roles.end(), "bass") != roles.end());
    assert(std::find(roles.begin(), roles.end(), "drums") != roles.end());
    
    std::cout << "  LocalNeuralPatternProvider styles: PASSED" << std::endl;
}

void testGenerationRequestConstraints() {
    std::cout << "Testing GenerationRequest constraints..." << std::endl;
    
    GenerationRequest request;
    assert(!request.hasTempoConstraint());
    
    request.targetBpm = 120.0;
    assert(request.hasTempoConstraint());
    
    request.targetBpm.reset();
    request.minBpm = 100.0;
    assert(request.hasTempoConstraint());
    
    request.minBpm.reset();
    request.maxBpm = 140.0;
    assert(request.hasTempoConstraint());
    
    request.maxBpm.reset();
    assert(!request.hasTempoConstraint());
    
    std::cout << "  GenerationRequest constraints: PASSED" << std::endl;
}

void testValidationReportToString() {
    std::cout << "Testing ValidationReport toString..." << std::endl;
    
    ValidationReport report;
    report.result = ValidationResult::Ok;
    report.message = "All good";
    assert(report.toString().find("Ok") != std::string::npos);
    
    report.result = ValidationResult::InvalidPitch;
    report.message = "Pitch 200 out of range";
    report.offendingEventIndex = 5;
    auto str = report.toString();
    assert(str.find("InvalidPitch") != std::string::npos);
    assert(str.find("Pitch 200") != std::string::npos);
    assert(str.find("5") != std::string::npos);
    
    std::cout << "  ValidationReport toString: PASSED" << std::endl;
}

void testGenerateDeterministicProducesMusicalMaterial() {
    std::cout << "Testing deterministic fallback produces musical material..." << std::endl;
    LocalNeuralPatternProvider::Config config;
    config.useDeterministicFallback = true;
    config.decoderConfig = RemiDecoderConfig::defaultConfig();

    LocalNeuralPatternProvider provider(config);
    GenerationRequest request;
    request.barCount = 2;
    request.targetBpm = 120.0;
    request.seed = 42;

    auto proposal = provider.generate(request);
    assert(proposal.has_value());
    assert(proposal->totalTicks > 0);

    auto notes = proposal->notes();
    assert(!notes.empty());

    for (const auto& n : notes) {
        assert(n.duration > 0);
        assert(n.pitch <= 127);
        assert(n.velocity <= 127);
    }
    std::cout << "  Deterministic fallback produces musical material: PASSED ("
              << notes.size() << " notes)" << std::endl;
}

void testGenerateDeterministicReproducibleWithSeed() {
    std::cout << "Testing deterministic fallback reproducibility with seed..." << std::endl;
    LocalNeuralPatternProvider::Config config;
    config.useDeterministicFallback = true;
    config.decoderConfig = RemiDecoderConfig::defaultConfig();

    LocalNeuralPatternProvider provider(config);
    GenerationRequest request;
    request.barCount = 2;
    request.targetBpm = 120.0;
    request.seed = 12345;

    auto p1 = provider.generate(request);
    auto p2 = provider.generate(request);
    assert(p1.has_value() && p2.has_value());
    assert(p1->events.size() == p2->events.size());
    assert(p1->seed == p2->seed);
    for (std::size_t i = 0; i < p1->events.size(); ++i) {
        assert(p1->events[i].index() == p2->events[i].index());
    }
    std::cout << "  Deterministic fallback reproducible with seed: PASSED" << std::endl;
}

void testValidateRejectsDurationZero() {
    std::cout << "Testing validator rejects zero-duration notes..." << std::endl;
    PatternProposalValidator validator;
    PatternProposal proposal;
    proposal.totalTicks = 1920;
    proposal.trackCount = 1;
    proposal.events.push_back(NoteEvent{60, 100, 0, 0, 0, 0});
    auto report = validator.validate(proposal);
    assert(report.result == ValidationResult::InvalidDuration);
    std::cout << "  Validator rejects zero duration: PASSED" << std::endl;
}

void testSanitizeDropsInvalidEvents() {
    std::cout << "Testing sanitizer drops invalid events..." << std::endl;
    PatternProposalValidator validator;
    PatternProposal proposal;
    proposal.totalTicks = 1920;
    proposal.trackCount = 1;
    proposal.events.push_back(NoteEvent{60, 100, 0, 480, 0, 0});
    proposal.events.push_back(NoteEvent{200, 100, 480, 480, 0, 0});
    proposal.events.push_back(NoteEvent{64, 100, 960, 480, 0, 0});
    auto [sanitized, report] = validator.sanitize(proposal);
    assert(report.isOk());
    assert(sanitized.events.size() == 2);
    assert(std::get<NoteEvent>(sanitized.events[0]).pitch == 60);
    assert(std::get<NoteEvent>(sanitized.events[1]).pitch == 64);
    std::cout << "  Sanitizer drops invalid events: PASSED" << std::endl;
}

int main() {
    try {
        testLocalNeuralPatternProviderFallback();
        testLocalNeuralPatternProviderStyles();
        testGenerationRequestConstraints();
        testValidationReportToString();
        testGenerateDeterministicProducesMusicalMaterial();
        testGenerateDeterministicReproducibleWithSeed();
        testValidateRejectsDurationZero();
        testSanitizeDropsInvalidEvents();
        std::cout << "\n=== ALL TESTS PASSED (Part 3) ===" << std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "TEST FAILED: " << e.what() << std::endl;
        return 1;
    } catch (...) {
        std::cerr << "TEST FAILED: Unknown exception" << std::endl;
        return 1;
    }
}