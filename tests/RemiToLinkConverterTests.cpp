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

#ifndef MOZART_TEST_SOURCE_DIR
#define MOZART_TEST_SOURCE_DIR "."
#endif

std::filesystem::path fixtureTokenizerPath() {
    return fs::path(MOZART_TEST_SOURCE_DIR) / "fixtures" / "remi_tokenizer_fixture.json";
}

void testBpeTokenizerLoadsFixture() {
    std::cout << "Testing BpeTokenizer loads fixture..." << std::endl;
    const auto path = fixtureTokenizerPath();
    auto tokenizer = BpeTokenizer::loadFromJson(path.string());

    assert(tokenizer.has_value());
    assert(tokenizer->vocabSize() == 23);
    assert(tokenizer->hasLearnedBpeVocabulary());
    assert(tokenizer->padToken() == 0);
    assert(tokenizer->bosToken() == 1);
    assert(tokenizer->eosToken() == 2);
    assert(tokenizer->maskToken() == 3);

    std::cout << "  BpeTokenizer loads fixture: PASSED" << std::endl;
}

void testBaseOnlyMidiTokTokenizerIsNotLearnedBpe() {
    const auto path = fs::path(MOZART_TEST_SOURCE_DIR) /
        "fixtures" / "remi_base_vocab_only_fixture.json";
    const auto tokenizer = BpeTokenizer::loadFromJson(path.string());
    assert(tokenizer.has_value());
    assert(tokenizer->vocabSize() == 6);
    assert(!tokenizer->hasLearnedBpeVocabulary());
}

void testBpeTokenizerDecodeKnownIds() {
    std::cout << "Testing BpeTokenizer decode known IDs..." << std::endl;
    const auto path = fixtureTokenizerPath();
    auto tokenizer = BpeTokenizer::loadFromJson(path.string());

    assert(tokenizer.has_value());

    auto names = tokenizer->decodeTokens({4, 5, 6, 7});
    assert(names.size() == 4);
    assert(names[0] == "Bar_None");
    assert(names[1] == "Pitch_21");
    assert(names[2] == "Pitch_60");
    assert(names[3] == "Duration_0.1.8");

    // The learned BPE id may encode multiple base semantic tokens.
    const auto merged = tokenizer->decodeTokens({14});
    assert(merged.size() == 2);
    assert(merged[0] == "Bar_None");
    assert(merged[1] == "Pitch_21");
    assert(tokenizer->decodeTokens({15}) == std::vector<std::string>{"Bar_None"});
    assert(tokenizer->decodeTokens({16}) == std::vector<std::string>{"Bar_None"});
    assert(tokenizer->decodeTokens({17}) == std::vector<std::string>{"Pitch_21"});
    assert(tokenizer->decodeTokens({18}) == std::vector<std::string>{"Chord_min"});
    assert(tokenizer->decodeTokens({19}) == std::vector<std::string>{"Program_0"});
    assert(tokenizer->decodeTokens({20}) == std::vector<std::string>{"PitchDrum_35"});
    assert(tokenizer->decodeTokens({21}) == std::vector<std::string>{"TimeSig_4/4"});
    assert(tokenizer->decodeTokens({22}) == std::vector<std::string>{"KeySig_0:0"});
    assert(!tokenizer->decodeToken(14).has_value());

    auto report = tokenizer->decodeTokensWithReport({999, 4});
    assert(report.droppedTokenIds == 1);
    assert(report.tokenNames.size() == 1);

    std::cout << "  BpeTokenizer decode known IDs: PASSED" << std::endl;
}

void testRemiDecoderConfigLoadsTokenizerArtifactFields() {
    std::cout << "Testing RemiDecoderConfig loads MidiTok fields..." << std::endl;
    const auto config = RemiDecoderConfig::fromTokenizerJson(fixtureTokenizerPath().string());
    assert(config.vocabSize == 23);
    assert(config.pitchMin == 21);
    assert(config.pitchMax == 109);
    assert(config.numVelocities == 32);
    assert(config.useVelocities);
    assert(config.positionResolution == 8);
    assert(config.defaultNoteDurationBeats == 0.5);
    assert(config.numTempos == 32);
    assert(config.tempoMin == 40.0);
    assert(config.tempoMax == 250.0);
    assert(config.padToken == 0);
    assert(config.bosToken == 1);
    assert(config.eosToken == 2);
    assert(config.maskToken == 3);
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
    const auto path = fixtureTokenizerPath();
    auto tokenizer = BpeTokenizer::loadFromJson(path.string());
    assert(tokenizer.has_value());

    auto sharedTokenizer =
        std::make_shared<BpeTokenizer>(std::move(*tokenizer));
    const auto config = RemiDecoderConfig::fromTokenizerJson(path.string());
    RemiEventAdapter adapter(config, sharedTokenizer);

    std::vector<std::uint32_t> tokenIds = {19, 8, 18, 6, 10, 7};

    GenerationRequest request;
    request.seed = 42;
    auto [proposal, report] =
        adapter.decodeTokensToProposal(tokenIds, request, "test-provider",
                                       "test-model");

    assert(proposal.events.size() > 0);
    const auto notes = proposal.notes();
    assert(notes.size() == 1);
    assert(notes[0].duration == 60);
    assert(notes[0].velocity == 127);
    assert(notes[0].position == 0);

    RemiToLinkPatternConverter converter(480);
    auto linkProposal = converter.convert(proposal);
    assert(linkProposal.has_value());
    assert(linkProposal->noteEvents.size() == 1);
    assert(linkProposal->noteEvents[0].startBeat == 0.0);
    assert(linkProposal->noteEvents[0].durationBeats == 0.125);
    assert(linkProposal->noteEvents[0].velocity == 127);

    std::cout << "  End-to-end token IDs to link: PASSED" << std::endl;
}

void testModelTokenStreamRequiresCompleteNoteRecords() {
    const auto path = fixtureTokenizerPath();
    auto tokenizer = BpeTokenizer::loadFromJson(path.string());
    assert(tokenizer.has_value());
    auto sharedTokenizer = std::make_shared<BpeTokenizer>(std::move(*tokenizer));
    const auto config = RemiDecoderConfig::fromTokenizerJson(path.string());
    RemiEventAdapter adapter(config, sharedTokenizer);

    const auto [missingVelocity, missingVelocityReport] =
        adapter.decodeTokensToProposal({8, 6, 7}, {}, "fixture", "fixture");
    assert(!missingVelocityReport.isOk());
    assert(missingVelocity.events.empty());

    const auto [missingDuration, missingDurationReport] =
        adapter.decodeTokensToProposal({8, 6, 10}, {}, "fixture", "fixture");
    assert(!missingDurationReport.isOk());
    assert(missingDuration.events.empty());

    const auto [interrupted, interruptedReport] =
        adapter.decodeTokensToProposal({8, 6, 11, 10, 7}, {}, "fixture", "fixture");
    assert(!interruptedReport.isOk());
    assert(interrupted.events.empty());
}

void testUnsupportedMidiTokProgramRejectsAtomically() {
    const auto path = fixtureTokenizerPath();
    auto tokenizer = BpeTokenizer::loadFromJson(path.string());
    assert(tokenizer.has_value());
    auto sharedTokenizer = std::make_shared<BpeTokenizer>(std::move(*tokenizer));
    const auto config = RemiDecoderConfig::fromTokenizerJson(path.string());
    RemiEventAdapter adapter(config, sharedTokenizer);

    // Program_10 is in the fixture vocabulary but cannot be represented by the
    // note-only runtime. A valid note before it must not escape as partial output.
    const auto [proposal, report] = adapter.decodeTokensToProposal(
        {8, 6, 10, 7, 13}, {}, "fixture", "fixture");
    assert(!report.isOk());
    assert(proposal.events.empty());
}

void testPitchDrumTokenRejectsAtomicallyForPianoCheckpoint() {
    const auto path = fixtureTokenizerPath();
    auto tokenizer = BpeTokenizer::loadFromJson(path.string());
    assert(tokenizer.has_value());
    auto sharedTokenizer = std::make_shared<BpeTokenizer>(std::move(*tokenizer));
    const auto config = RemiDecoderConfig::fromTokenizerJson(path.string());
    RemiEventAdapter adapter(config, sharedTokenizer);

    // ID 20 is PitchDrum_35 in the MidiTok-shaped fixture. It must never be
    // reinterpreted as a pitched piano note by this piano-only backend.
    const auto [proposal, report] = adapter.decodeTokensToProposal(
        {1, 20, 2}, {}, "fixture", "fixture");
    assert(!report.isOk());
    assert(proposal.events.empty());
}

void testUnsupportedRemiTokenRejectsAtomically() {
    const auto path = fixtureTokenizerPath();
    auto tokenizer = BpeTokenizer::loadFromJson(path.string());
    assert(tokenizer.has_value());
    auto sharedTokenizer = std::make_shared<BpeTokenizer>(std::move(*tokenizer));
    const auto config = RemiDecoderConfig::fromTokenizerJson(path.string());
    RemiEventAdapter adapter(config, sharedTokenizer);

    // KeySig_0:0 is decodable as a semantic token but this target tokenizer
    // configuration does not enable key-signature events. It must not be dropped.
    const auto [proposal, report] = adapter.decodeTokensToProposal(
        {8, 6, 10, 7, 22}, {}, "fixture", "fixture");
    assert(!report.isOk());
    assert(proposal.events.empty());
}

} // namespace

int main() {
    testBpeTokenizerLoadsFixture();
    testBaseOnlyMidiTokTokenizerIsNotLearnedBpe();
    testBpeTokenizerDecodeKnownIds();
    testRemiDecoderConfigLoadsTokenizerArtifactFields();
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
    testModelTokenStreamRequiresCompleteNoteRecords();
    testUnsupportedMidiTokProgramRejectsAtomically();
    testUnsupportedRemiTokenRejectsAtomically();
    testPitchDrumTokenRejectsAtomicallyForPianoCheckpoint();
    testEndToEndRemiToLink();
    std::cout << "ALL REMI-TO-LINK CONVERTER TESTS PASSED" << std::endl;
    return 0;
}
