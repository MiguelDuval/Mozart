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

int main() {
    try {
        testLocalNeuralPatternProviderFallback();
        testLocalNeuralPatternProviderStyles();
        testGenerationRequestConstraints();
        testValidationReportToString();
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