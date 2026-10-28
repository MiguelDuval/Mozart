#include "remi/GenerationTypes.h"
#include "remi/RemiDecoderConfig.h"
#include "remi/RemiEventAdapter.h"
#include "remi/PatternProposalValidator.h"
#include "generation/RemiToLinkPatternConverter.h"
#include "generation/PatternProposal.h"

#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>

using namespace mozart::remi;
using namespace mozart::generation;

void testConverterNoteEvent() {
    std::cout << "Testing converter: NoteEvent → MusicalNoteEvent..." << std::endl;
    RemiToLinkPatternConverter converter(480);
    remi::PatternProposal remiProposal;
    remiProposal.providerId = "test";
    remiProposal.modelId = "test";
    remiProposal.seed = 42;
    remiProposal.totalTicks = 1920;
    remiProposal.trackCount = 1;
    remi::NoteEvent note{60, 100, 0, 480, 0, 0};
    remiProposal.events.push_back(note);
    auto linkProposal = converter.convert(remiProposal);
    assert(linkProposal.has_value());
    assert(linkProposal->noteEvents.size() == 1);
    assert(linkProposal->noteEvents[0].note == 60);
    assert(linkProposal->noteEvents[0].velocity == 100);
    assert(linkProposal->noteEvents[0].channel == 0);
    assert(linkProposal->noteEvents[0].startBeat == 0.0);
    assert(linkProposal->noteEvents[0].durationBeats == 1.0);
    assert(linkProposal->metadata.seed == 42);
    assert(linkProposal->metadata.lengthBeats == 4.0);
    std::cout << "  Converter NoteEvent: PASSED" << std::endl;
}

void testConverterMultipleNotes() {
    std::cout << "Testing converter: multiple notes..." << std::endl;
    RemiToLinkPatternConverter converter(480);
    remi::PatternProposal remiProposal;
    remiProposal.providerId = "test";
    remiProposal.modelId = "test";
    remiProposal.totalTicks = 1920;
    remiProposal.trackCount = 1;
    remi::NoteEvent n1{60, 100, 0, 480, 0, 0};
    remi::NoteEvent n2{64, 80, 480, 240, 0, 0};
    remi::NoteEvent n3{67, 90, 960, 480, 0, 0};
    remiProposal.events.push_back(n1);
    remiProposal.events.push_back(n2);
    remiProposal.events.push_back(n3);
void testConverterControlChange() {
    std::cout << "Testing converter: ControlChangeEvent → PatternControlEvent..." << std::endl;
    RemiToLinkPatternConverter converter(480);
    remi::PatternProposal remiProposal;
    remiProposal.providerId = "test";
    remiProposal.modelId = "test";
    remiProposal.totalTicks = 1920;
    remiProposal.trackCount = 1;
    remi::ControlChangeEvent cc{960, 1, 64, 127};
    remiProposal.events.push_back(cc);
    auto linkProposal = converter.convert(remiProposal);
    assert(linkProposal.has_value());
    assert(linkProposal->controlEvents.size() == 1);
    assert(linkProposal->controlEvents[0].startBeat == 2.0);
    assert(linkProposal->controlEvents[0].channel == 1);
    assert(linkProposal->controlEvents[0].controller == 64);
    assert(linkProposal->controlEvents[0].value == 127);
    std::cout << "  Converter ControlChange: PASSED" << std::endl;
}

void testConverterInvalidProposal() {
    std::cout << "Testing converter: rejects invalid proposals..." << std::endl;
    RemiToLinkPatternConverter converter(480);
    remi::PatternProposal empty;
    assert(!converter.convert(empty).has_value());
    remi::PatternProposal zeroTicks;
    zeroTicks.providerId = "test";
    zeroTicks.modelId = "test";
    zeroTicks.totalTicks = 0;
    zeroTicks.trackCount = 1;
    zeroTicks.events.push_back(remi::NoteEvent{60, 100, 0, 480, 0, 0});
    assert(!converter.convert(zeroTicks).has_value());
    std::cout << "  Converter invalid proposal: PASSED" << std::endl;
}
void testEndToEndRemiToLink() {
    std::cout << "Testing end-to-end: REMI adapter → converter → link proposal..." << std::endl;
    RemiDecoderConfig config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);
    std::vector<RemiEvent> events;
    events.push_back(RemiBarEvent{0});
    events.push_back(RemiTempoEvent{120.0});
    events.push_back(RemiTimeSignatureEvent{4, 4});
    events.push_back(RemiPositionEvent{0});
    events.push_back(RemiNoteOnEvent{60, 100, 0, 0});
    events.push_back(RemiPositionEvent{8});
    events.push_back(RemiNoteOnEvent{64, 80, 8, 0});
    GenerationRequest request;
    request.barCount = 2;
    request.seed = 42;
    auto [remiProposal, remiReport] = adapter.decodeEventsToProposal(events, request, "test-provider", "test-model");
    assert(remiProposal.events.size() > 0);
    PatternProposalValidator validator;
    auto validationReport = validator.validate(remiProposal);
    assert(validationReport.isOk());
    RemiToLinkPatternConverter converter(480);
    auto linkProposal = converter.convert(remiProposal);
    assert(linkProposal.has_value());
    assert(linkProposal->isWellFormed());
    assert(linkProposal->noteEvents.size() == 2);
    assert(linkProposal->metadata.seed == 42);
    assert(linkProposal->metadata.generatorId == "test-provider");
    std::cout << "  End-to-end REMI→Link: PASSED (" << linkProposal->noteEvents.size()
              << " notes, " << linkProposal->controlEvents.size() << " controls)" << std::endl;
}

int main() {
    try {
        testConverterNoteEvent();
        testConverterMultipleNotes();
        testConverterControlChange();
        testConverterInvalidProposal();
        testConverterDifferntTicksPerBeat();
        testEndToEndRemiToLink();
        std::cout << "\n=== ALL REMI-TO-LINK CONVERTER TESTS PASSED ===" << std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "TEST FAILED: " << e.what() << std::endl;
        return 1;
    } catch (...) {
        std::cerr << "TEST FAILED: Unknown exception" << std::endl;
        return 1;
    }
}


void testConverterDifferntTicksPerBeat() {
    std::cout << "Testing converter: different ticks per beat..." << std::endl;
    RemiToLinkPatternConverter converter(960);
    remi::PatternProposal remiProposal;
    remiProposal.providerId = "test";
    remiProposal.modelId = "test";
    remiProposal.totalTicks = 960;
    remiProposal.trackCount = 1;
    remi::NoteEvent note{60, 100, 480, 480, 0, 0};
    remiProposal.events.push_back(note);
    auto linkProposal = converter.convert(remiProposal);
    assert(linkProposal.has_value());
    assert(linkProposal->noteEvents[0].startBeat == 0.5);
    assert(linkProposal->noteEvents[0].durationBeats == 0.5);
    std::cout << "  Converter different ticks per beat: PASSED" << std::endl;
}

    auto linkProposal = converter.convert(remiProposal);
    assert(linkProposal.has_value());
    assert(linkProposal->noteEvents.size() == 3);
    assert(linkProposal->noteEvents[0].startBeat == 0.0);
    assert(linkProposal->noteEvents[0].durationBeats == 1.0);
    assert(linkProposal->noteEvents[1].startBeat == 1.0);
    assert(linkProposal->noteEvents[1].durationBeats == 0.5);
    assert(linkProposal->noteEvents[2].startBeat == 2.0);
    assert(linkProposal->noteEvents[2].durationBeats == 1.0);
    std::cout << "  Converter multiple notes: PASSED" << std::endl;
}
