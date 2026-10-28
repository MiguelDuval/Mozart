#include "remi/GenerationTypes.h"
#include "remi/RemiDecoderConfig.h"
#include "remi/RemiEventAdapter.h"
#include "generation/RemiToLinkPatternConverter.h"

#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>

namespace {

using mozart::generation::RemiToLinkPatternConverter;
using mozart::remi::ControlChangeEvent;
using mozart::remi::NoteEvent;
using mozart::remi::PatternProposal;
using mozart::remi::RemiBarEvent;
using mozart::remi::RemiDecoderConfig;
using mozart::remi::RemiEvent;
using mozart::remi::RemiEventAdapter;
using mozart::remi::RemiNoteOnEvent;
using mozart::remi::RemiPositionEvent;
using mozart::remi::RemiTempoEvent;
using mozart::remi::RemiTimeSignatureEvent;
using mozart::remi::GenerationRequest;

void testConverterNoteEvent() {
    std::cout << "Testing converter: NoteEvent -> MusicalNoteEvent..." << std::endl;
    RemiToLinkPatternConverter converter(480);
    PatternProposal proposal;
    proposal.providerId = "test";
    proposal.modelId = "test";
    proposal.seed = 42;
    proposal.totalTicks = 1920;
    proposal.events.push_back(NoteEvent{60, 100, 0, 480, 0, 0});

    const auto converted = converter.convert(proposal);
    assert(converted.has_value());
    assert(converted->noteEvents.size() == 1);
    assert(converted->noteEvents[0].note == 60);
    assert(converted->noteEvents[0].velocity == 100);
    assert(converted->noteEvents[0].channel == 0);
    assert(converted->noteEvents[0].startBeat == 0.0);
    assert(converted->noteEvents[0].durationBeats == 1.0);
    assert(converted->metadata.seed == 42);
    assert(converted->metadata.lengthBeats == 4.0);
}

void testConverterMultipleNotes() {
    std::cout << "Testing converter: multiple notes..." << std::endl;
    RemiToLinkPatternConverter converter(480);
    PatternProposal proposal;
    proposal.providerId = "test";
    proposal.modelId = "test";
    proposal.totalTicks = 1920;
    proposal.events.push_back(NoteEvent{60, 100, 0, 480, 0, 0});
    proposal.events.push_back(NoteEvent{64, 80, 480, 240, 0, 0});
    proposal.events.push_back(NoteEvent{67, 90, 960, 480, 0, 0});

    const auto converted = converter.convert(proposal);
    assert(converted.has_value());
    assert(converted->noteEvents.size() == 3);
    assert(converted->noteEvents[0].startBeat == 0.0);
    assert(converted->noteEvents[0].durationBeats == 1.0);
    assert(converted->noteEvents[1].startBeat == 1.0);
    assert(converted->noteEvents[1].durationBeats == 0.5);
    assert(converted->noteEvents[2].startBeat == 2.0);
    assert(converted->noteEvents[2].durationBeats == 1.0);
}

void testConverterControlChange() {
    std::cout << "Testing converter: ControlChangeEvent -> PatternControlEvent..." << std::endl;
    RemiToLinkPatternConverter converter(480);
    PatternProposal proposal;
    proposal.providerId = "test";
    proposal.modelId = "test";
    proposal.totalTicks = 1920;
    proposal.events.push_back(ControlChangeEvent{960, 1, 64, 127});

    const auto converted = converter.convert(proposal);
    assert(converted.has_value());
    assert(converted->controlEvents.size() == 1);
    assert(converted->controlEvents[0].startBeat == 2.0);
    assert(converted->controlEvents[0].channel == 1);
    assert(converted->controlEvents[0].controller == 64);
    assert(converted->controlEvents[0].value == 127);
}

void testConverterInvalidProposalIsAtomic() {
    std::cout << "Testing converter: rejects invalid proposals atomically..." << std::endl;
    RemiToLinkPatternConverter converter(480);

    PatternProposal empty;
    assert(!converter.convert(empty).has_value());

    PatternProposal zeroTicks;
    zeroTicks.totalTicks = 0;
    zeroTicks.events.push_back(NoteEvent{60, 100, 0, 480, 0, 0});
    assert(!converter.convert(zeroTicks).has_value());

    PatternProposal invalidNote;
    invalidNote.totalTicks = 1920;
    invalidNote.events.push_back(NoteEvent{200, 100, 0, 480, 0, 0});
    assert(!converter.convert(invalidNote).has_value());

    PatternProposal mixedValidAndInvalid;
    mixedValidAndInvalid.totalTicks = 1920;
    mixedValidAndInvalid.events.push_back(NoteEvent{60, 100, 0, 480, 0, 0});
    mixedValidAndInvalid.events.push_back(ControlChangeEvent{240, 20, 64, 127});
    assert(!converter.convert(mixedValidAndInvalid).has_value());

    RemiToLinkPatternConverter zeroResolution(0);
    PatternProposal otherwiseValid;
    otherwiseValid.totalTicks = 480;
    otherwiseValid.events.push_back(NoteEvent{60, 100, 0, 480, 0, 0});
    assert(!zeroResolution.convert(otherwiseValid).has_value());
}

void testConverterDifferentTicksPerBeat() {
    std::cout << "Testing converter: different ticks per beat..." << std::endl;
    RemiToLinkPatternConverter converter(960);
    PatternProposal proposal;
    proposal.providerId = "test";
    proposal.modelId = "test";
    proposal.totalTicks = 960;
    proposal.events.push_back(NoteEvent{60, 100, 480, 480, 0, 0});

    const auto converted = converter.convert(proposal);
    assert(converted.has_value());
    assert(converted->noteEvents[0].startBeat == 0.5);
    assert(converted->noteEvents[0].durationBeats == 0.5);
}

void testEndToEndRemiToLink() {
    std::cout << "Testing end-to-end: REMI adapter -> Link proposal..." << std::endl;
    const auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);

    std::vector<RemiEvent> events{
        RemiBarEvent{0},
        RemiTempoEvent{120.0},
        RemiTimeSignatureEvent{4, 4},
        RemiPositionEvent{0},
        RemiNoteOnEvent{60, 100, 0, 0},
        RemiPositionEvent{8},
        RemiNoteOnEvent{64, 80, 8, 0}
    };
    GenerationRequest request;
    request.barCount = 2;
    request.seed = 42;

    auto [remiProposal, decodeReport] =
        adapter.decodeEventsToProposal(events, request, "test-provider", "test-model");
    (void) decodeReport;
    assert(!remiProposal.events.empty());

    mozart::remi::PatternProposalValidator remiValidator;
    const auto validation = remiValidator.validate(remiProposal);
    assert(validation.isOk());

    RemiToLinkPatternConverter converter(480);
    const auto converted = converter.convert(remiProposal);
    assert(converted.has_value());
    assert(converted->isWellFormed());
    assert(converted->noteEvents.size() == 2);
    assert(converted->metadata.seed == 42);
    assert(converted->metadata.generatorId == "test-provider");
}

} // namespace

int main() {
    testConverterNoteEvent();
    testConverterMultipleNotes();
    testConverterControlChange();
    testConverterInvalidProposalIsAtomic();
    testConverterDifferentTicksPerBeat();
    testEndToEndRemiToLink();
    std::cout << "ALL REMI-TO-LINK CONVERTER TESTS PASSED" << std::endl;
    return 0;
}
