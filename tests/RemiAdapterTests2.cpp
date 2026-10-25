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

void testRemiEventAdapterDecoding() {
    std::cout << "Testing RemiEventAdapter event decoding..." << std::endl;
    
    auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);
    
    std::vector<RemiEvent> events;
    events.push_back(RemiBarEvent{0});
    events.push_back(RemiTempoEvent{128.0});
    events.push_back(RemiTimeSignatureEvent{4, 4});
    events.push_back(RemiProgramEvent{0, 0});
    events.push_back(RemiVelocityEvent{10});
    events.push_back(RemiPositionEvent{0});
    events.push_back(RemiNoteOnEvent{60, 0, 0, 0});
    events.push_back(RemiPositionEvent{8});
    events.push_back(RemiNoteOnEvent{64, 0, 8, 0});
    events.push_back(RemiPositionEvent{16});
    events.push_back(RemiNoteOnEvent{67, 0, 16, 0});
    events.push_back(RemiBarEvent{1});
    events.push_back(RemiPositionEvent{0});
    events.push_back(RemiNoteOnEvent{72, 0, 0, 0});
    
    GenerationRequest request;
    request.barCount = 2;
    request.seed = 42;
    
    auto [proposal, report] = adapter.decodeEventsToProposal(events, request, "test-provider", "test-model");
    
    assert(report.isOk() || report.result == RemiDecodeResult::Truncated);
    assert(proposal.events.size() > 0);
    assert(proposal.totalTicks > 0);
    assert(proposal.trackCount >= 1);
    assert(proposal.providerId == "test-provider");
    assert(proposal.modelId == "test-model");
    assert(proposal.seed == 42);
    
    auto tempo = proposal.firstTempo();
    assert(tempo.has_value());
    assert(tempo->bpm == 128.0);
    
    auto ts = proposal.firstTimeSignature();
    assert(ts.has_value());
    assert(ts->numerator == 4);
    assert(ts->denominator == 4);
    
    auto notes = proposal.notes();
    assert(notes.size() == 4);
    
    std::cout << "  RemiEventAdapter decoding: PASSED" << std::endl;
}

void testRemiEventAdapterEmpty() {
    std::cout << "Testing RemiEventAdapter empty sequence..." << std::endl;
    
    auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);
    
    std::vector<RemiEvent> emptyEvents;
    GenerationRequest request;
    
    auto [proposal, report] = adapter.decodeEventsToProposal(emptyEvents, request);
    
    assert(report.result == RemiDecodeResult::EmptySequence);
    assert(!proposal.isValid());
    
    std::cout << "  RemiEventAdapter empty: PASSED" << std::endl;
}

void testRemiEventAdapterTruncation() {
    std::cout << "Testing RemiEventAdapter truncation..." << std::endl;
    
    auto config = RemiDecoderConfig::defaultConfig();
    config.maxEvents = 5;
    config.maxBars = 2;
    RemiEventAdapter adapter(config);
    
    std::vector<RemiEvent> events;
    events.push_back(RemiBarEvent{0});
    
    for (int i = 0; i < 20; ++i) {
        events.push_back(RemiNoteOnEvent{static_cast<std::uint8_t>(60 + i % 12), 100, 
                                         static_cast<std::uint32_t>(i * 60), 0});
    }
    
    GenerationRequest request;
    request.maxEvents = 3;
    
    auto [proposal, report] = adapter.decodeEventsToProposal(events, request);
    
    assert(proposal.events.size() <= 5);
    assert(proposal.truncated || report.result == RemiDecodeResult::ExceededMaxEvents || 
           report.result == RemiDecodeResult::Truncated);
    
    std::cout << "  RemiEventAdapter truncation: PASSED" << std::endl;
}

void testRemiVocabulary() {
    std::cout << "Testing RemiVocabulary..." << std::endl;
    
    auto config = RemiDecoderConfig::defaultConfig();
    auto vocab = RemiVocabulary::createFromConfig(config);
    
    assert(vocab.size() > 0);
    
    auto pad = vocab.tokenInfo(0);
    assert(pad.has_value());
    assert(pad->name == "PAD_None");
    
    auto bos = vocab.tokenInfo(1);
    assert(bos.has_value());
    assert(bos->name == "BOS_None");
    
    auto id = vocab.tokenId("BOS_None");
    assert(id.has_value());
    assert(*id == 1);
    
    auto noteOn = vocab.tokenInfo(4);
    assert(noteOn.has_value());
    assert(noteOn->type == RemiEventType::NoteOn);
    
    std::cout << "  RemiVocabulary: PASSED" << std::endl;
}

int main() {
    try {
        testRemiEventAdapterDecoding();
        testRemiEventAdapterEmpty();
        testRemiEventAdapterTruncation();
        testRemiVocabulary();
        std::cout << "\n=== ALL TESTS PASSED (Part 2) ===" << std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "TEST FAILED: " << e.what() << std::endl;
        return 1;
    } catch (...) {
        std::cerr << "TEST FAILED: Unknown exception" << std::endl;
        return 1;
    }
}