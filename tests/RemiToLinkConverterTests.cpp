#include "remi/GenerationTypes.h"
#include "remi/RemiDecoderConfig.h"
#include "remi/RemiEventAdapter.h"
#include "remi/BpeTokenizer.h"
#include "generation/RemiToLinkPatternConverter.h"

#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>
#include <filesystem>
#include <fstream>

namespace fs = std::filesystem;

using mozart::generation::RemiToLinkPatternConverter;
using mozart::remi::BpeTokenizer;
using mozart::remi::ControlChangeEvent;
using mozart::remi::NoteEvent;
using mozart::remi::PatternProposal;
using mozart::remi::ProgramChangeEvent;
using mozart::remi::RemiBarEvent;
using mozart::remi::RemiDecoderConfig;
using mozart::remi::RemiDurationEvent;
using mozart::remi::RemiEvent;
using mozart::remi::RemiEventAdapter;
using mozart::remi::RemiNoteOnEvent;
using mozart::remi::RemiPositionEvent;
using mozart::remi::RemiTempoEvent;
using mozart::remi::RemiVelocityEvent;
using mozart::remi::RemiTimeSignatureEvent;
using mozart::remi::GenerationRequest;

namespace {

std::filesystem::path writeFixtureTokenizer() {
    const auto fixturePath =
        fs::temp_directory_path() / "mozart_remi_tokenizer_fixture.json";
    std::ofstream fixture(fixturePath);
    fixture << R"json({
  "_vocab_base_byte_to_token": {
    "a": "Bar_None",
    "b": "Pitch_21",
    "c": "Pitch_60",
    "d": "Duration_0.1.8",
    "e": "Position_0",
    "f": "Position_8",
    "g": "Velocity_15",
    "h": "Tempo_15"
  },
  "_model": "{\"model\":{\"vocab\":{\"PAD_None\":0,\"BOS_None\":1,\"EOS_None\":2,\"MASK_None\":3,\"a\":4,\"b\":5,\"c\":6,\"d\":7,\"e\":8,\"f\":9,\"g\":10,\"h\":11},\"merges\":[]}}",
  "config": { "special_tokens": ["PAD_None", "BOS_None", "EOS_None", "MASK_None"] }
})json";
    fixture.close();
    return fixturePath;
}

void testBpeTokenizerLoadsFixture() {
    std::cout << "Testing BpeTokenizer loads fixture..." << std::endl;
    const auto path = writeFixtureTokenizer();
    auto tokenizer = BpeTokenizer::loadFromJson(path.string());
    std::error_code ignored;
    fs::remove(path, ignored);

    assert(tokenizer.has_value());
    assert(tokenizer->vocabSize() == 12);
    assert(tokenizer->padToken() == 0);
    assert(tokenizer->bosToken() == 1);
    assert(tokenizer->eosToken() == 2);
    assert(tokenizer->maskToken() == 3);

    std::cout << "  BpeTokenizer loads fixture: PASSED" << std::endl;
}

void testBpeTokenizerDecodeKnownIds() {
    std::cout << "Testing BpeTokenizer decode known IDs..." << std::endl;
    const auto path = writeFixtureTokenizer();
    auto tokenizer = BpeTokenizer::loadFromJson(path.string());
    std::error_code ignored;
    fs::remove(path, ignored);

    assert(tokenizer.has_value());

    auto names = tokenizer->decodeTokens({4, 5, 6, 7});
    assert(names.size() == 4);

    auto report = tokenizer->decodeTokensWithReport({999, 4});
    assert(report.droppedTokenIds == 1);
    assert(report.tokenNames.size() == 1);

    std::cout << "  BpeTokenizer decode known IDs: PASSED" << std::endl;
}

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

    PatternProposal unsupportedProgramChange;
    unsupportedProgramChange.totalTicks = 1920;
    unsupportedProgramChange.events.push_back(NoteEvent{60, 100, 0, 480, 0, 0});
    unsupportedProgramChange.events.push_back(
        mozart::remi::ProgramChangeEvent{0, 0, 10});
    assert(!converter.convert(unsupportedProgramChange).has_value());

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

void testConverterDurationNoteEvent() {
    std::cout << "Testing converter: Duration_ note -> MusicalNoteEvent..." << std::endl;
    RemiToLinkPatternConverter converter(480);
    PatternProposal proposal;
    proposal.providerId = "test";
    proposal.modelId = "test";
    proposal.seed = 42;
    proposal.totalTicks = 1920;
    proposal.events.push_back(NoteEvent{60, 100, 0, 240, 0, 0});

    const auto converted = converter.convert(proposal);
    assert(converted.has_value());
    assert(converted->noteEvents.size() == 1);
    assert(converted->noteEvents[0].startBeat == 0.0);
    assert(converted->noteEvents[0].durationBeats == 0.5);

    std::cout << "  Converter duration note: PASSED" << std::endl;
}

void testConverterRejectsProgramChange() {
    std::cout << "Testing converter: rejects ProgramChangeEvent..." << std::endl;
    RemiToLinkPatternConverter converter(480);
    PatternProposal proposal;
    proposal.providerId = "test";
    proposal.modelId = "test";
    proposal.totalTicks = 1920;
    proposal.events.push_back(NoteEvent{60, 100, 0, 480, 0, 0});
    proposal.events.push_back(ProgramChangeEvent{0, 0, 10});

    const auto converted = converter.convert(proposal);
    assert(!converted.has_value());

    std::cout << "  Converter rejects program change: PASSED" << std::endl;
}

void testConverterAtomicRejection() {
    std::cout << "Testing converter: atomic rejection of mixed valid/invalid..."
              << std::endl;
    RemiToLinkPatternConverter converter(480);
    PatternProposal proposal;
    proposal.providerId = "test";
    proposal.modelId = "test";
    proposal.totalTicks = 1920;
    proposal.events.push_back(NoteEvent{60, 100, 0, 480, 0, 0});
    proposal.events.push_back(ControlChangeEvent{240, 20, 64, 127});

    const auto converted = converter.convert(proposal);
    assert(!converted.has_value());

    std::cout << "  Converter atomic rejection: PASSED" << std::endl;
}

void testRemiAdapterDurationToken() {
    std::cout << "Testing RemiEventAdapter Duration_ token..." << std::endl;
    const auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);

    std::vector<RemiEvent> events;
    events.push_back(RemiPositionEvent{0});
    events.push_back(RemiNoteOnEvent{60, 100, 0, 0});
    events.push_back(RemiDurationEvent{0.0, 1, 8});

    GenerationRequest request;
    auto [proposal, report] =
        adapter.decodeEventsToProposal(events, request, "test", "test");

    assert(proposal.events.size() > 0);
    const auto notes = proposal.notes();
    assert(notes.size() == 1);
    assert(notes[0].duration == 60);
    assert(notes[0].pitch == 60);
    assert(notes[0].velocity == 100);
    assert(notes[0].position == 0);

    std::cout << "  RemiEventAdapter Duration_ token: PASSED" << std::endl;
}

void testRemiAdapterPositionAndVelocity() {
    std::cout << "Testing RemiEventAdapter position and velocity..." << std::endl;
    const auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);

    std::vector<RemiEvent> events;
    events.push_back(RemiPositionEvent{8});
    events.push_back(RemiVelocityEvent{127});
    events.push_back(RemiNoteOnEvent{64, 0, 0, 0});

    GenerationRequest request;
    auto [proposal, report] =
        adapter.decodeEventsToProposal(events, request, "test", "test");

    assert(proposal.events.size() > 0);
    const auto notes = proposal.notes();
    assert(notes.size() == 1);
    // Default MidiTok resolution is 8 positions per beat: Position_8 = one beat.
    assert(notes[0].position == 480);
    assert(notes[0].velocity == 127);

    std::cout << "  RemiEventAdapter position and velocity: PASSED" << std::endl;
}

void testRemiAdapterMetaEvents() {
    std::cout << "Testing RemiEventAdapter meta events..." << std::endl;
    const auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);

    std::vector<RemiEvent> events;
    events.push_back(RemiBarEvent{0});
    events.push_back(RemiTempoEvent{140.0});
    events.push_back(RemiTimeSignatureEvent{4, 4});
    events.push_back(RemiPositionEvent{0});
    events.push_back(RemiNoteOnEvent{60, 100, 0, 0});

    GenerationRequest request;
    auto [proposal, report] =
        adapter.decodeEventsToProposal(events, request, "test", "test");

    assert(proposal.events.size() >= 3);
    const auto tempo = proposal.firstTempo();
    assert(tempo.has_value());
    assert(tempo->bpm == 140.0);
    const auto ts = proposal.firstTimeSignature();
    assert(ts.has_value());
    assert(ts->numerator == 4);
    assert(ts->denominator == 4);

    std::cout << "  RemiEventAdapter meta events: PASSED" << std::endl;
}

void testRemiAdapterDurationAfterNoteOn() {
    std::cout << "Testing RemiEventAdapter Duration_ after NoteOn..." << std::endl;
    const auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);

    std::vector<RemiEvent> events;
    events.push_back(RemiPositionEvent{0});
    events.push_back(RemiNoteOnEvent{67, 90, 0, 0});
    events.push_back(RemiDurationEvent{1.0, 0, 4});

    GenerationRequest request;
    auto [proposal, report] =
        adapter.decodeEventsToProposal(events, request, "test", "test");

    assert(proposal.events.size() > 0);
    const auto notes = proposal.notes();
    assert(notes.size() == 1);
    assert(notes[0].duration == 480);
    assert(notes[0].pitch == 67);
    assert(notes[0].velocity == 90);

    std::cout << "  RemiEventAdapter Duration_ after NoteOn: PASSED" << std::endl;
}

void testRemiAdapterDurationAppliesToPrecedingNoteOnly() {
    std::cout << "Testing RemiEventAdapter Duration_ applies to the preceding note only..."
              << std::endl;
    const auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);

    std::vector<RemiEvent> events;
    events.push_back(RemiPositionEvent{0});
    events.push_back(RemiNoteOnEvent{60, 100, 0, 0});
    events.push_back(RemiDurationEvent{2.0, 0, 1});
    events.push_back(RemiPositionEvent{8});
    events.push_back(RemiNoteOnEvent{64, 80, 0, 0});

    GenerationRequest request;
    auto [proposal, report] =
        adapter.decodeEventsToProposal(events, request, "test", "test");

    assert(proposal.events.size() > 0);
    const auto notes = proposal.notes();
    assert(notes.size() == 2);
    assert(notes[0].duration == 960);
    assert(notes[1].duration == 240);

    std::cout << "  RemiEventAdapter Duration_ applies to the preceding note only: PASSED"
              << std::endl;
}

void testEndToEndTokenIdsToLink() {
    std::cout << "Testing end-to-end: token IDs -> REMI -> link proposal..."
              << std::endl;
    const auto path = writeFixtureTokenizer();
    auto tokenizer = BpeTokenizer::loadFromJson(path.string());
    std::error_code ignored;
    fs::remove(path, ignored);
    assert(tokenizer.has_value());

    auto sharedTokenizer =
        std::make_shared<BpeTokenizer>(std::move(*tokenizer));
    const auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config, sharedTokenizer);

    std::vector<std::uint32_t> tokenIds = {4, 8, 6, 7};

    GenerationRequest request;
    request.seed = 42;
    auto [proposal, report] =
        adapter.decodeTokensToProposal(tokenIds, request, "test-provider",
                                       "test-model");

    assert(proposal.events.size() > 0);
    const auto notes = proposal.notes();
    assert(notes.size() == 1);
    assert(notes[0].duration == 60);

    RemiToLinkPatternConverter converter(480);
    auto linkProposal = converter.convert(proposal);
    assert(linkProposal.has_value());
    assert(linkProposal->noteEvents.size() == 1);
    assert(linkProposal->noteEvents[0].startBeat == 0.0);
    assert(linkProposal->noteEvents[0].durationBeats == 0.125);

    std::cout << "  End-to-end token IDs to link: PASSED" << std::endl;
}

} // namespace

int main() {
    testBpeTokenizerLoadsFixture();
    testBpeTokenizerDecodeKnownIds();
    testConverterNoteEvent();
    testConverterMultipleNotes();
    testConverterControlChange();
    testConverterInvalidProposalIsAtomic();
    testConverterDifferentTicksPerBeat();
    testConverterDurationNoteEvent();
    testConverterRejectsProgramChange();
    testConverterAtomicRejection();
    testRemiAdapterDurationToken();
    testRemiAdapterPositionAndVelocity();
    testRemiAdapterMetaEvents();
    testRemiAdapterDurationAfterNoteOn();
    testRemiAdapterDurationAppliesToPrecedingNoteOnly();
    testEndToEndTokenIdsToLink();
    testEndToEndRemiToLink();
    std::cout << "ALL REMI-TO-LINK CONVERTER TESTS PASSED" << std::endl;
    return 0;
}
