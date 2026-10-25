#include "core/GenerationTypes.h"
#include "core/RemiEventAdapter.h"
#include "core/RemiDecoderConfig.h"
#include "core/BpeTokenizer.h"
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
#include <utility>
#include <limits>

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
    assert(proposal.truncated);
    assert(report.result == RemiDecodeResult::ExceededMaxEvents);
    assert(report.droppedTokens > 0);
    assert(!report.message.empty());
    
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

void testRemiEventAdapterDurationTokenParsing() {
    std::cout << "Testing REMI Duration_ token parsing end-to-end..." << std::endl;
    const auto fixturePath =
        std::filesystem::temp_directory_path() / "mozart_remi_duration_tokenizer_test.json";
    {
        std::ofstream fixture(fixturePath);
        assert(fixture.is_open());
        fixture << R"json({
  "_vocab_base_byte_to_token": {"\u0100":"PAD_None","\u0101":"BOS_None","\u0102":"EOS_None","\u0103":"MASK_None","\u0104":"Bar_None","\u0105":"Position_8","\u0106":"Pitch_60","\u0107":"Velocity_15","\u0108":"Duration_1.0.8","\u0109":"Tempo_15"},
  "_model": "{\"model\":{\"vocab\":{\"\\u0100\":0,\"\\u0101\":1,\"\\u0102\":2,\"\\u0103\":3,\"\\u0104\":4,\"\\u0105\":5,\"\\u0106\":6,\"\\u0107\":7,\"\\u0108\":8,\"\\u0109\":9,\"\\u0105\\u0109\":10,\"\\u0106\\u0107\\u0108\":11},\"merges\":[]}}",
  "config": {"special_tokens": ["PAD_None", "BOS_None", "EOS_None", "MASK_None"]}
})json";
    }

    auto tokenizer = BpeTokenizer::loadFromJson(fixturePath.string());
    std::filesystem::remove(fixturePath);
    assert(tokenizer.has_value());

    auto sharedTokenizer = std::make_shared<BpeTokenizer>(std::move(*tokenizer));
    auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config, sharedTokenizer);
    GenerationRequest request;
    request.barCount = 1;

    const std::vector<std::uint32_t> tokenIds{999, 1, 4, 10, 11, 2}; // Invalid ID plus BOS, merged events, EOS.
    auto [proposal, report] =
        adapter.decodeTokensToProposal(tokenIds, request, "test-provider", "test-model");

    assert(report.isOk());
    assert(report.droppedTokens == 1); // Only invalid BPE ID 999 is dropped; BOS/EOS are control tokens.
    assert(!report.warnings.empty());
    assert(report.warnings.front().find("BPE token ID 999") != std::string::npos);
    assert(!sharedTokenizer->decodeToken(10).has_value()); // One BPE ID contains two base tokens.

    const auto directDecode = sharedTokenizer->decodeTokensWithReport({999, 10});
    assert(directDecode.droppedTokenIds == 1);
    assert(directDecode.tokenNames.size() == 2); // Position_8 and Tempo_15 from one merged ID.
    assert(directDecode.warnings.size() == 1);
    const auto notes = proposal.notes();
    assert(notes.size() == 1);
    assert(notes[0].pitch == 60);
    assert(notes[0].position == 480); // Position_8 is one beat at 480 PPQ, converted once.
    assert(notes[0].velocity == 127); // Velocity_15 is the highest configured velocity bin.
    assert(notes[0].duration == 480); // Duration_1.0.8 = one beat at 480 PPQ.
    const auto tempo = proposal.firstTempo();
    assert(tempo.has_value());
    assert(tempo->bpm >= 120.0 && tempo->bpm <= 150.0); // Tempo_15 is decoded as a tempo bin.
    std::cout << "  REMI Duration_ token parsing end-to-end: PASSED" << std::endl;
}

void testRemiBarTokenAdvancesAcrossMultipleBars() {
    std::cout << "Testing repeated Bar_None advances the decoded bar..." << std::endl;
    const auto fixturePath =
        std::filesystem::temp_directory_path() / "mozart_remi_implicit_bar_test.json";
    {
        std::ofstream fixture(fixturePath);
        assert(fixture.is_open());
        fixture << R"json({
  "_vocab_base_byte_to_token": {"a":"Bar_None","b":"Position_0","c":"Pitch_60","d":"Velocity_15","e":"Duration_1.0.8","f":"Pitch_64","g":"Duration_2.0.8"},
  "_model": "{\"model\":{\"vocab\":{\"a\":0,\"b\":1,\"c\":2,\"d\":3,\"e\":4,\"f\":5,\"g\":6,\"cde\":7,\"fdg\":8},\"merges\":[]}}",
  "config": {"special_tokens": ["PAD_None", "BOS_None", "EOS_None", "MASK_None"]}
})json";
    }

    auto tokenizer = BpeTokenizer::loadFromJson(fixturePath.string());
    std::filesystem::remove(fixturePath);
    assert(tokenizer.has_value());

    auto sharedTokenizer = std::make_shared<BpeTokenizer>(std::move(*tokenizer));
    RemiEventAdapter adapter(RemiDecoderConfig::defaultConfig(), sharedTokenizer);
    GenerationRequest request;
    const std::vector<std::uint32_t> tokenIds{0, 1, 7, 0, 1, 8}; // Two merged note-event groups.
    auto [proposal, report] =
        adapter.decodeTokensToProposal(tokenIds, request, "test-provider", "test-model");

    assert(report.isOk());
    assert(report.droppedTokens == 0);
    const auto notes = proposal.notes();
    assert(notes.size() == 2);
    assert(notes[0].pitch == 60);
    assert(notes[0].position == 0);
    assert(notes[0].duration == 480);
    assert(notes[1].pitch == 64);
    assert(notes[1].position == RemiDecoderConfig::defaultConfig().ticksPerBar);
    assert(notes[1].duration == 960);
    std::cout << "  Repeated Bar_None advances the decoded bar: PASSED" << std::endl;
}

void testRemiEventAdapterInvalidDurationTokenFallsBackSafely() {
    std::cout << "Testing malformed Duration_ token is rejected safely..." << std::endl;
    const auto fixturePath =
        std::filesystem::temp_directory_path() / "mozart_remi_invalid_duration_tokenizer_test.json";
    {
        std::ofstream fixture(fixturePath);
        assert(fixture.is_open());
        fixture << R"json({
  "_vocab_base_byte_to_token": {"a":"Bar_None","b":"Position_0","c":"Pitch_60","d":"Velocity_15","e":"Duration_1.0.0","f":"PitchDrum_300","g":"Pitch_60junk","h":"Position_32","i":"Position_2147483647","j":"Duration_0.0.8"},
  "_model": "{\"model\":{\"vocab\":{\"a\":0,\"b\":1,\"c\":2,\"d\":3,\"e\":4,\"f\":5,\"g\":6,\"h\":7,\"i\":8,\"j\":9},\"merges\":[]}}",
  "config": {"special_tokens": ["PAD_None", "BOS_None", "EOS_None", "MASK_None"]}
})json";
    }

    auto tokenizer = BpeTokenizer::loadFromJson(fixturePath.string());
    std::filesystem::remove(fixturePath);
    assert(tokenizer.has_value());

    auto sharedTokenizer = std::make_shared<BpeTokenizer>(std::move(*tokenizer));
    RemiEventAdapter adapter(RemiDecoderConfig::defaultConfig(), sharedTokenizer);
    GenerationRequest request;
    const std::vector<std::uint32_t> tokenIds{0, 1, 2, 3, 4, 5, 6, 7, 8, 9};
    auto [proposal, report] =
        adapter.decodeTokensToProposal(tokenIds, request, "test-provider", "test-model");

    assert(report.isOk());
    assert(report.droppedTokens >= 6); // Zero/malformed durations, invalid pitches, and out-of-bar positions.
    const auto notes = proposal.notes();
    assert(notes.size() == 1);
    assert(notes[0].duration == RemiDecoderConfig::defaultConfig().ticksPerBeat / 4);
    std::cout << "  Malformed Duration_ token is rejected safely: PASSED" << std::endl;
}

void testRemiEventAdapterDurationPreservation() {
    std::cout << "Testing Duration_ token preserves note length..." << std::endl;
    auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);

    std::vector<RemiEvent> events;
    events.push_back(RemiBarEvent{0});
    events.push_back(RemiPositionEvent{0});
    events.push_back(RemiNoteOnEvent{60, 100, 0, 0});     // нота начинается на тике 0
    events.push_back(RemiNoteOffEvent{0, 480, 0});         // маркер Duration_ (pitch==0), 480 тиков

    GenerationRequest request;
    auto [proposal, report] = adapter.decodeEventsToProposal(events, request, "test-provider", "test-model");

    assert(report.isOk());
    auto notes = proposal.notes();
    assert(notes.size() == 1);
    assert(notes[0].pitch == 60);
    assert(notes[0].velocity == 100);
    assert(notes[0].position == 0);
    assert(notes[0].duration == 480);   // длина из Duration_, а не значение по умолчанию
    std::cout << "  Duration_ token preserves note length: PASSED" << std::endl;
}

void testRemiEventAdapterTotalTicksSaturateInsteadOfWrapping() {
    std::cout << "Testing proposal length saturates safely near UINT32_MAX..." << std::endl;
    const auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);

    std::vector<RemiEvent> events;
    events.push_back(RemiBarEvent{0});
    events.push_back(RemiNoteOnEvent{
        60, 100, std::numeric_limits<std::uint32_t>::max() - 300U, 0});

    GenerationRequest request;
    auto [proposal, report] = adapter.decodeEventsToProposal(events, request);
    assert(report.isOk());
    const auto notes = proposal.notes();
    assert(notes.size() == 1);
    assert(notes[0].position == std::numeric_limits<std::uint32_t>::max() - 300U);
    assert(notes[0].duration == config.ticksPerBeat / 4);
    assert(proposal.totalTicks == std::numeric_limits<std::uint32_t>::max());
    assert(proposal.totalTicks >= notes[0].position);
    std::cout << "  Proposal length saturates without integer wrap: PASSED" << std::endl;
}

void testRemiEventAdapterRejectsNoteEndTickOverflow() {
    std::cout << "Testing note end tick overflow is rejected..." << std::endl;
    auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);

    std::vector<RemiEvent> events;
    events.push_back(RemiBarEvent{0});
    events.push_back(RemiNoteOnEvent{
        60, 100, std::numeric_limits<std::uint32_t>::max() - 100U, 0});

    GenerationRequest request;
    auto [proposal, report] = adapter.decodeEventsToProposal(events, request);
    assert(report.result == RemiDecodeResult::EmptySequence);
    assert(report.droppedTokens == 1);
    assert(!report.warnings.empty());
    assert(proposal.notes().empty());
    std::cout << "  Note end tick overflow is rejected: PASSED" << std::endl;
}

void testRemiEventAdapterDurationBeforeNoteOn() {
    std::cout << "Testing Duration_ before NoteOn applies to next note..." << std::endl;
    auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);

    std::vector<RemiEvent> events;
    events.push_back(RemiBarEvent{0});
    events.push_back(RemiNoteOffEvent{0, 960, 0});        // маркер длительности без предшествующей ноты -> pending
    events.push_back(RemiPositionEvent{0});
    events.push_back(RemiNoteOnEvent{60, 100, 0, 0});     // получает отложенную длительность 960

    GenerationRequest request;
    auto [proposal, report] = adapter.decodeEventsToProposal(events, request);
    assert(report.isOk());
    auto notes = proposal.notes();
    assert(notes.size() == 1);
    assert(notes[0].pitch == 60);
    assert(notes[0].position == 0);
    assert(notes[0].duration == 960);
    std::cout << "  Duration_ before NoteOn applies to next note: PASSED" << std::endl;
}

void testRemiEventAdapterDurationBeforeNextNoteDoesNotRewritePreviousNote() {
    std::cout << "Testing a pre-note Duration_ applies to the next note..." << std::endl;
    auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);

    std::vector<RemiEvent> events;
    events.push_back(RemiBarEvent{0});
    events.push_back(RemiPositionEvent{0});
    events.push_back(RemiNoteOnEvent{60, 100, 0, 0});  // Existing note at tick 0.
    events.push_back(RemiPositionEvent{8});             // Advance to tick 480.
    events.push_back(RemiNoteOffEvent{0, 960, 0});       // Duration belongs to the upcoming note.
    events.push_back(RemiNoteOnEvent{64, 100, 0, 0});

    GenerationRequest request;
    auto [proposal, report] = adapter.decodeEventsToProposal(events, request);
    assert(report.isOk());
    const auto notes = proposal.notes();
    assert(notes.size() == 2);
    assert(notes[0].pitch == 60 && notes[0].position == 0);
    assert(notes[0].duration == config.ticksPerBeat / 4); // Preserve the default duration.
    assert(notes[1].pitch == 64 && notes[1].position == 480);
    assert(notes[1].duration == 960);
    std::cout << "  Pre-note Duration_ applies to the next note: PASSED" << std::endl;
}

void testRemiEventAdapterPolyphonyRepeatedPitch() {
    std::cout << "Testing polyphony and repeated pitch durations..." << std::endl;
    auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);

    std::vector<RemiEvent> events;
    events.push_back(RemiBarEvent{0});
    events.push_back(RemiPositionEvent{0});
    events.push_back(RemiNoteOnEvent{60, 100, 0, 0});     // нота A, тик 0
    events.push_back(RemiNoteOffEvent{0, 480, 0});        // длительность A = 480
    events.push_back(RemiNoteOnEvent{60, 100, 480, 0});   // нота B, та же высота, тик 480
    events.push_back(RemiNoteOffEvent{0, 960, 0});        // длительность B = 960

    GenerationRequest request;
    auto [proposal, report] = adapter.decodeEventsToProposal(events, request);
    assert(report.isOk());
    auto notes = proposal.notes();
    assert(notes.size() == 2);
    assert(notes[0].pitch == 60 && notes[0].position == 0 && notes[0].duration == 480);
    assert(notes[1].pitch == 60 && notes[1].position == 480 && notes[1].duration == 960);
    std::cout << "  Polyphony and repeated pitch durations: PASSED" << std::endl;
}

void testRemiEventAdapterNoteOffClosesNote() {
    std::cout << "Testing genuine note-off closes a note..." << std::endl;
    auto config = RemiDecoderConfig::defaultConfig();
    RemiEventAdapter adapter(config);

    std::vector<RemiEvent> events;
    events.push_back(RemiBarEvent{0});
    events.push_back(RemiPositionEvent{0});
    events.push_back(RemiNoteOnEvent{60, 100, 0, 0});
    events.push_back(RemiNoteOffEvent{60, 1440, 0});      // note-off: конец на тике 1440

    GenerationRequest request;
    auto [proposal, report] = adapter.decodeEventsToProposal(events, request);
    assert(report.isOk());
    auto notes = proposal.notes();
    assert(notes.size() == 1);
    assert(notes[0].pitch == 60);
    assert(notes[0].position == 0);
    assert(notes[0].duration == 1440);   // 1440 - 0 = 1440
    std::cout << "  Genuine note-off closes a note: PASSED" << std::endl;
}

void testBpeTokenizerLoadsRealTokenizer() {
    std::cout << "Testing BPE tokenizer loads real tokenizer.json..." << std::endl;
    auto tokenizer = BpeTokenizer::loadFromJson(
        "experiments/aura-midi/models/shikhr-music-maker-official/tokenizer.json");
    assert(tokenizer.has_value());
    assert(!tokenizer->empty());
    assert(tokenizer->vocabSize() > 0);
    assert(tokenizer->padToken() == 0);
    assert(tokenizer->bosToken() == 1);
    assert(tokenizer->eosToken() == 2);
    assert(tokenizer->maskToken() == 3);
    std::cout << "  BPE tokenizer loads real tokenizer: PASSED (vocab=" << tokenizer->vocabSize() << ")" << std::endl;
}

void testBpeTokenizerDecodeKnownIds() {
    std::cout << "Testing BPE tokenizer decodes known IDs to musical token names..." << std::endl;
    auto tokenizer = BpeTokenizer::loadFromJson(
        "experiments/aura-midi/models/shikhr-music-maker-official/tokenizer.json");
    assert(tokenizer.has_value());
    auto pad = tokenizer->decodeToken(0);
    assert(pad.has_value());
    assert(*pad == "PAD_None");
    auto bos = tokenizer->decodeToken(1);
    assert(bos.has_value());
    assert(*bos == "BOS_None");
    auto bar = tokenizer->decodeToken(4);
    assert(bar.has_value());
    assert(*bar == "Bar_None");
    auto pitch = tokenizer->decodeToken(5);
    assert(pitch.has_value());
    assert(*pitch == "Pitch_21");
    auto invalid = tokenizer->decodeToken(999999);
    assert(!invalid.has_value());
    std::cout << "  BPE tokenizer decodes known IDs: PASSED" << std::endl;
}

void testBpeTokenizerDecodeTokensFlattens() {
    std::cout << "Testing BPE tokenizer decodeTokens flattens results..." << std::endl;
    auto tokenizer = BpeTokenizer::loadFromJson(
        "experiments/aura-midi/models/shikhr-music-maker-official/tokenizer.json");
    assert(tokenizer.has_value());
    std::vector<std::uint32_t> ids = {0, 1, 2, 4, 5};
    auto names = tokenizer->decodeTokens(ids);
    assert(names.size() == 5);
    assert(names[0] == "PAD_None");
    assert(names[1] == "BOS_None");
    assert(names[2] == "EOS_None");
    assert(names[3] == "Bar_None");
    assert(names[4] == "Pitch_21");
    std::vector<std::uint32_t> mixedIds = {0, 999999, 1};
    auto mixedNames = tokenizer->decodeTokens(mixedIds);
    assert(mixedNames.size() == 2);
    assert(mixedNames[0] == "PAD_None");
    assert(mixedNames[1] == "BOS_None");
    std::cout << "  BPE tokenizer decodeTokens flattens: PASSED" << std::endl;
}

void testSpecialTokensSilentlySkipped() {
    std::cout << "Testing special tokens are silently skipped..." << std::endl;
    auto config = RemiDecoderConfig::defaultConfig();
    auto tokenizer = BpeTokenizer::loadFromJson(
        "experiments/aura-midi/models/shikhr-music-maker-official/tokenizer.json");
    assert(tokenizer.has_value());
    auto sharedTokenizer = std::make_shared<BpeTokenizer>(std::move(*tokenizer));
    RemiEventAdapter adapter(config, sharedTokenizer);
    // PAD, BOS, Bar_None, Pitch_60, EOS, MASK
    std::vector<std::uint32_t> tokenIds = {0, 1, 4, 65, 2, 3};
    GenerationRequest request;
    request.barCount = 1;
    auto [proposal, report] = adapter.decodeTokensToProposal(tokenIds, request, "test", "test-model");
    bool hasSpecialWarning = false;
    for (const auto& w : report.warnings) {
        if (w.find("PAD") != std::string::npos || w.find("BOS") != std::string::npos ||
            w.find("EOS") != std::string::npos || w.find("MASK") != std::string::npos) {
            hasSpecialWarning = true;
        }
    }
    assert(!hasSpecialWarning);
    auto notes = proposal.notes();
    assert(notes.size() == 1);
    assert(notes[0].pitch == 60);
    std::cout << "  Special tokens silently skipped: PASSED" << std::endl;
}

void testBarNoneAdvancesThroughFullPipeline() {
    std::cout << "Testing Bar_None advances bar counter through full pipeline..." << std::endl;
    auto config = RemiDecoderConfig::defaultConfig();
    auto tokenizer = BpeTokenizer::loadFromJson(
        "experiments/aura-midi/models/shikhr-music-maker-official/tokenizer.json");
    assert(tokenizer.has_value());
    auto sharedTokenizer = std::make_shared<BpeTokenizer>(std::move(*tokenizer));
    RemiEventAdapter adapter(config, sharedTokenizer);
    std::vector<std::uint32_t> tokenIds = {4, 4};
    GenerationRequest request;
    request.barCount = 4;
    auto [proposal, report] = adapter.decodeTokensToProposal(tokenIds, request, "test", "test-model");
    assert(report.isOk());
    assert(report.droppedTokens == 0);
    std::cout << "  Bar_None advances through full pipeline: PASSED" << std::endl;
}

void testDurationTokenThroughFullPipeline() {
    std::cout << "Testing Duration_ token through full pipeline..." << std::endl;
    auto config = RemiDecoderConfig::defaultConfig();
    auto tokenizer = BpeTokenizer::loadFromJson(
        "experiments/aura-midi/models/shikhr-music-maker-official/tokenizer.json");
    assert(tokenizer.has_value());
    auto sharedTokenizer = std::make_shared<BpeTokenizer>(std::move(*tokenizer));
    RemiEventAdapter adapter(config, sharedTokenizer);
    std::uint32_t durationId = 109;
    auto decoded = sharedTokenizer->decodeToken(durationId);
    assert(decoded.has_value());
    assert(*decoded == "Duration_0.1.8");
    std::vector<std::uint32_t> tokenIds = {4, 218, 65, durationId};
    GenerationRequest request;
    request.barCount = 1;
    auto [proposal, report] = adapter.decodeTokensToProposal(tokenIds, request, "test", "test-model");
    assert(report.isOk());
    auto notes = proposal.notes();
    assert(notes.size() == 1);
    assert(notes[0].pitch == 60);
    assert(notes[0].duration == 60);
    std::cout << "  Duration_ token through full pipeline: PASSED (duration=" << notes[0].duration << " ticks)" << std::endl;
}

void testInvalidTokenIdsTrackedAsDropped() {
    std::cout << "Testing invalid token IDs are tracked as dropped..." << std::endl;
    auto config = RemiDecoderConfig::defaultConfig();
    auto tokenizer = BpeTokenizer::loadFromJson(
        "experiments/aura-midi/models/shikhr-music-maker-official/tokenizer.json");
    assert(tokenizer.has_value());
    auto sharedTokenizer = std::make_shared<BpeTokenizer>(std::move(*tokenizer));
    RemiEventAdapter adapter(config, sharedTokenizer);
    std::vector<std::uint32_t> tokenIds = {0, 999999, 1, 888888, 2};
    GenerationRequest request;
    request.barCount = 1;
    auto [proposal, report] = adapter.decodeTokensToProposal(tokenIds, request, "test", "test-model");
    assert(report.droppedTokens == 2);
    assert(proposal.notes().size() == 0);
    std::cout << "  Invalid token IDs tracked as dropped: PASSED (dropped=" << report.droppedTokens << ")" << std::endl;
}

int main() {
    try {
        testRemiEventAdapterDecoding();
        testRemiEventAdapterEmpty();
        testRemiEventAdapterTruncation();
        testRemiVocabulary();
        testRemiEventAdapterDurationTokenParsing();
        testRemiBarTokenAdvancesAcrossMultipleBars();
        testRemiEventAdapterRejectsNoteEndTickOverflow();
        testRemiEventAdapterTotalTicksSaturateInsteadOfWrapping();
        testRemiEventAdapterInvalidDurationTokenFallsBackSafely();
        testRemiEventAdapterDurationPreservation();
        testRemiEventAdapterDurationBeforeNoteOn();
        testRemiEventAdapterDurationBeforeNextNoteDoesNotRewritePreviousNote();
        testRemiEventAdapterPolyphonyRepeatedPitch();
        testRemiEventAdapterNoteOffClosesNote();
        testBpeTokenizerLoadsRealTokenizer();
        testBpeTokenizerDecodeKnownIds();
        testBpeTokenizerDecodeTokensFlattens();
        testSpecialTokensSilentlySkipped();
        testBarNoneAdvancesThroughFullPipeline();
        testDurationTokenThroughFullPipeline();
        testInvalidTokenIdsTrackedAsDropped();
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