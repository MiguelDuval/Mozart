#include "core/MidiEndpoint.h"
#include "core/MidiTypes.h"
#include "core/TransportMath.h"
#include "generation/ArpeggioGenerator.h"
#include "generation/ChordProgressionGenerator.h"
#include "generation/BassGenerator.h"
#include "generation/RhythmGenerator.h"
#include "generation/NoteRepeat.h"
#include "generation/GenerationRequest.h"
#include "generation/StyleVocabulary.h"
#include "generation/PatternProposal.h"
#include "generation/LocalPatternProvider.h"
#include "generation/TokenInferenceBackend.h"
#include "generation/LocalNeuralPatternProvider.h"
#include "generation/DeterministicPatternProvider.h"
#include "generation/MidiEventVocabulary.h"
#include "generation/MidiEventTokenizer.h"
#include "generation/MidiEventDetokenizer.h"
#include "musical/AudioKeyDetector.h"
#include "musical/AudioKeyStabilityFilter.h"
#include "musical/AudioChromaEstimator.h"
#include "musical/Chord.h"
#include "musical/VoiceLeading.h"
#include "scheduler/PerformanceScene.h"
#include "scheduler/MacroControl.h"
#include "midi/MidiTransport.h"
#include "midi/MidiReceiveQueue.h"
#include "midi/ControllerMapping.h"
#include "musical/KeyScale.h"
#include "musical/KeyContext.h"
#ifdef MOZART_ENABLE_LINK
#include "runtime/MozartRuntime.h"
#endif
#ifdef MOZART_ENABLE_LINK
#include "clock/LinkClock.h"
#endif

#include <algorithm>
#include <cassert>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <condition_variable>
#include <mutex>
#include <thread>
#include <string>
#include <vector>

int main() {
    {
        mozart::generation::GenerationRequest request;
        request.role = mozart::generation::GenerationRole::Bass;
        request.bars = 2;
        request.density = 0.5;
        request.seed = 12345;

        mozart::generation::DeterministicPatternProvider provider;
        assert(provider.isAvailable());

        const auto result = provider.generate(request);
        assert(result.ok());
        assert(result.proposal.metadata.generatorId == "deterministic-local-v1");
        assert(result.proposal.metadata.seed == request.seed);
        assert(!result.proposal.noteEvents.empty());
        for (const auto& event : result.proposal.noteEvents) {
            assert(event.startBeat >= 0.0);
            assert(event.startBeat < 8.0);
            assert(event.note >= 36);
            assert(event.note < 60);
        }

        request.role = mozart::generation::GenerationRole::Arpeggio;
        const auto arpResult = provider.generate(request);
        assert(arpResult.ok());
        assert(!arpResult.proposal.noteEvents.empty());

        request.tempoBpm = 10.0;
        const auto invalid = provider.generate(request);
        assert(invalid.status == mozart::generation::GenerationStatus::InvalidRequest);
        assert(!invalid.ok());

        request.tempoBpm = 128.0;
        request.role = mozart::generation::GenerationRole::Lead;
        const auto unsupported = provider.generate(request);
        assert(unsupported.status == mozart::generation::GenerationStatus::Unavailable);
        assert(!unsupported.ok());

        request.role = mozart::generation::GenerationRole::Bass;
        request.minNote = 60;
        request.maxNote = 60;
        const auto rangeFailure = provider.generate(request);
        assert(rangeFailure.status == mozart::generation::GenerationStatus::Failed);
        assert(!rangeFailure.ok());
    }

    {
        using mozart::generation::GenerationStyle;
        using mozart::generation::GenerationRequest;
        using mozart::generation::StyleVocabulary;

        assert(StyleVocabulary::fromSlug("electronic") == GenerationStyle::Electronic);
        assert(StyleVocabulary::fromSlug("techno") == GenerationStyle::Techno);
        assert(StyleVocabulary::fromSlug("dark_techno") == GenerationStyle::DarkTechno);
        assert(StyleVocabulary::fromSlug("hard_techno") == GenerationStyle::HardTechno);
        assert(StyleVocabulary::fromSlug("trap") == GenerationStyle::Trap);
        assert(StyleVocabulary::fromSlug("unknown") == GenerationStyle::Custom);
        assert(StyleVocabulary::isValidSlug("custom"));
        assert(!StyleVocabulary::isValidSlug("unknown"));

        using mozart::generation::GenerationMood;
        using mozart::generation::GenerationRhythm;
        using mozart::generation::GenerationRole;
        using mozart::generation::GenerationSubstyle;
        assert(
                StyleVocabulary::substyleFromSlug("dark_trap") ==
                GenerationSubstyle::DarkTrap);
        assert(
                StyleVocabulary::isValidSubstyleSlug("dark_trap"));
        assert(
                !StyleVocabulary::isValidSubstyleSlug("unknown_substyle"));
        assert(
                StyleVocabulary::moodFromSlug("hypnotic") ==
                GenerationMood::Hypnotic);
        assert(
                StyleVocabulary::isValidMoodSlug("atmospheric"));
        assert(!StyleVocabulary::isValidMoodSlug("unknown_mood"));
        assert(
                StyleVocabulary::rhythmFromSlug("half_time") ==
                GenerationRhythm::HalfTime);
        assert(
                StyleVocabulary::isValidRhythmSlug("double_time"));
        assert(!StyleVocabulary::isValidRhythmSlug("unknown_rhythm"));
        assert(StyleVocabulary::roleSlug(GenerationRole::Bass) == "bass");
        assert(
                StyleVocabulary::roleFromSlug("texture") ==
                GenerationRole::Texture);
        assert(!StyleVocabulary::isValidRoleSlug("unknown_role"));

        const auto dark = StyleVocabulary::profile(GenerationStyle::DarkTechno);
        assert(dark.slug == "dark_techno");
        assert(dark.displayName == "Dark Techno");
        assert(std::abs(dark.defaultEnergy - 0.78) < 1.0e-12);
        assert(std::abs(dark.defaultDensity - 0.82) < 1.0e-12);
        assert(dark.defaultSyncopation >= 0.0);
        assert(dark.defaultSyncopation <= 1.0);

        const auto hard = StyleVocabulary::profile(GenerationStyle::HardTechno);
        assert(hard.defaultEnergy > dark.defaultEnergy);
        assert(hard.defaultDensity > dark.defaultDensity);

        GenerationRequest request;
        request.style = GenerationStyle::Trap;
        request.energy = 0.0;
        request.density = 0.0;
        request.syncopation = 0.0;
        request.swing = 0.0;
        request.variation = 0.0;
        StyleVocabulary::applyDefaults(request);
        assert(request.isValid());
        assert(std::abs(request.energy - 0.72) < 1.0e-12);
        assert(std::abs(request.density - 0.64) < 1.0e-12);
        assert(std::abs(request.syncopation - 0.58) < 1.0e-12);
        assert(std::abs(request.swing - 0.10) < 1.0e-12);
        assert(std::abs(request.variation - 0.66) < 1.0e-12);
    }

    {
        using mozart::generation::MidiEventToken;
        using mozart::generation::MidiEventTokenizer;
        using namespace mozart::generation::midi_event_vocabulary;

        mozart::generation::PatternProposal proposal;
        proposal.metadata.confidence = 1.0;
        proposal.noteEvents.push_back(
                mozart::musical::MusicalNoteEvent{0.0, 0.5, 36, 0, 0});
        proposal.noteEvents.push_back(
                mozart::musical::MusicalNoteEvent{1.0, 4.0, 64, 127, 1});
        proposal.controlEvents.push_back(
                mozart::generation::PatternControlEvent{0.0, 0, 74, 0});

        const auto first = MidiEventTokenizer::encode(proposal);
        const auto second = MidiEventTokenizer::encode(proposal);
        assert(first.has_value());
        assert(second.has_value());
        assert(*first == *second);
        assert(first->size() > 2);
        assert(first->front() == kBos);
        assert(first->back() == kEos);

        bool hasNote36 = false;
        bool hasNote64 = false;
        bool hasController74 = false;
        for (const MidiEventToken token : *first) {
            assert(isValidToken(token));
            hasNote36 = hasNote36 || token == noteToken(36);
            hasNote64 = hasNote64 || token == noteToken(64);
            hasController74 = hasController74 || token == controllerToken(74);
        }
        assert(hasNote36);
        assert(hasNote64);
        assert(hasController74);

        auto invalidDuration = proposal;
        invalidDuration.noteEvents[1].durationBeats = 8.1;
        assert(!MidiEventTokenizer::encode(invalidDuration).has_value());

        MidiEventTokenizer::Options tinyBudget;
        tinyBudget.maxTokens = 3;
        assert(!MidiEventTokenizer::encode(proposal, tinyBudget).has_value());

        assert(kVocabularySize == 512);
        assert(isValidToken(static_cast<MidiEventToken>(kVocabularySize - 1)));
        assert(!isValidToken(static_cast<MidiEventToken>(kVocabularySize)));
    }

    {
        using mozart::generation::MidiEventDetokenizer;
        using mozart::generation::MidiEventToken;
        using namespace mozart::generation::midi_event_vocabulary;

        mozart::generation::PatternProposal source;
        source.metadata.confidence = 1.0;
        source.noteEvents = {
                {0.0, 0.5, 36, 100, 0},
                {1.0, 0.25, 64, 127, 1}
        };
        source.controlEvents = {
                {1.0, 0, 74, 64}
        };

        const auto encoded =
                mozart::generation::MidiEventTokenizer::encode(source);
        assert(encoded.has_value());

        const auto decoded = MidiEventDetokenizer::decode(*encoded);
        assert(decoded.has_value());
        assert(decoded->isWellFormed());
        assert(decoded->noteEvents.size() == source.noteEvents.size());
        assert(decoded->controlEvents.size() == source.controlEvents.size());
        assert(decoded->noteEvents[0].note == 36);
        assert(decoded->noteEvents[1].note == 64);
        assert(decoded->controlEvents[0].controller == 74);
        assert(decoded->noteEvents[0].startBeat == 0.0);
        assert(decoded->noteEvents[1].startBeat == 1.0);
        assert(decoded->controlEvents[0].startBeat == 1.0);

        std::vector<MidiEventToken> noChannel{
                kBos,
                noteToken(60),
                velocityToken(16),
                durationToken(4),
                kEos
        };
        assert(!MidiEventDetokenizer::decode(noChannel).has_value());

        std::vector<MidiEventToken> truncatedNote{
                kBos,
                channelToken(0),
                noteToken(60),
                velocityToken(16),
                kEos
        };
        assert(!MidiEventDetokenizer::decode(truncatedNote).has_value());

        std::vector<MidiEventToken> invalidShift{
                kBos,
                channelToken(0),
                timeShiftToken(64),
                timeShiftToken(64),
                timeShiftToken(64),
                kEos
        };
        MidiEventDetokenizer::Options bounded;
        bounded.maxTimeShiftSteps = 100;
        assert(!MidiEventDetokenizer::decode(invalidShift, bounded).has_value());

        std::vector<MidiEventToken> invalidPadding{
                kBos,
                kPad,
                kEos
        };
        assert(!MidiEventDetokenizer::decode(invalidPadding).has_value());
    }

    {
        mozart::generation::GenerationRequest request;
        assert(request.isValid());

        request.tempoBpm = 320.0;
        assert(!request.isValid());
        request.tempoBpm = 128.0;
        request.minNote = 100;
        request.maxNote = 90;
        assert(!request.isValid());

        request.minNote = 36;
        request.maxNote = 96;
        request.chordProgression = {
                mozart::musical::Chord(
                        0, mozart::musical::ChordQuality::Major),
                mozart::musical::Chord(
                        12, mozart::musical::ChordQuality::Minor)
        };
        assert(!request.isValid());
        request.chordProgression.clear();
        request.style =
                static_cast<mozart::generation::GenerationStyle>(255);
        assert(!request.isValid());
        request.style = mozart::generation::GenerationStyle::Techno;

        request.role =
                static_cast<mozart::generation::GenerationRole>(255);
        assert(!request.isValid());
        request.role = mozart::generation::GenerationRole::Bass;

        request.keyScale =
                mozart::musical::KeyScale{
                        6,
                        static_cast<mozart::musical::Scale>(255)};
        assert(!request.isValid());
        request.keyScale =
                mozart::musical::KeyScale{
                        6, mozart::musical::Scale::NaturalMinor};

        request.maxNote = 255;
        assert(!request.isValid());
        request.maxNote = 96;

        mozart::generation::PatternProposal proposal;
        proposal.metadata.seed = request.seed;
        proposal.metadata.confidence = 0.75;
        proposal.noteEvents.push_back(
                mozart::musical::MusicalNoteEvent{0.0, 0.5, 48, 100, 0});
        proposal.controlEvents.push_back(
                mozart::generation::PatternControlEvent{0.5, 0, 1, 64});
        assert(proposal.isWellFormed());

        proposal.noteEvents[0].durationBeats = -0.1;
        assert(!proposal.isWellFormed());

        class StubProvider final : public mozart::generation::LocalPatternProvider {
        public:
            [[nodiscard]] mozart::generation::GenerationResult generate(
                    const mozart::generation::GenerationRequest& input) override {
                if (!input.isValid()) {
                    return {
                            mozart::generation::GenerationStatus::InvalidRequest,
                            {},
                            "invalid request"
                    };
                }

                mozart::generation::PatternProposal generated;
                generated.metadata.seed = input.seed;
                generated.metadata.confidence = 1.0;
                return {
                        mozart::generation::GenerationStatus::Ok,
                        generated,
                        {}
                };
            }

            [[nodiscard]] bool isAvailable() const noexcept override {
                return true;
            }
        };

        request.minNote = 36;
        request.maxNote = 96;
        StubProvider provider;
        const auto result = provider.generate(request);
        assert(result.ok());
        assert(result.proposal.metadata.seed == request.seed);
        assert(provider.isAvailable());
    }

    {
        using mozart::generation::LocalNeuralPatternProvider;
        using mozart::generation::MidiEventTokenizer;
        using mozart::generation::TokenInferenceBackend;
        using mozart::generation::TokenInferenceResult;
        using mozart::generation::TokenInferenceStatus;

        class StubTokenBackend final : public TokenInferenceBackend {
        public:
            [[nodiscard]] TokenInferenceResult generateTokens(
                    const mozart::generation::GenerationRequest& request,
                    const std::size_t maxTokens) override {
                if (maxTokens < 8) {
                    return {
                            TokenInferenceStatus::Failed,
                            {},
                            0.0,
                            0,
                            "token budget too small"
                    };
                }

                mozart::generation::PatternProposal source;
                source.metadata.confidence = 1.0;
                source.noteEvents = {
                        {0.0, 0.5, 49, 100, 0},
                        {1.0, 0.5, 59, 127, 0}
                };

                const auto encoded = MidiEventTokenizer::encode(source);
                if (!encoded.has_value() || encoded->size() > maxTokens) {
                    return {
                            TokenInferenceStatus::Failed,
                            {},
                            0.0,
                            0,
                            "failed to encode stub token stream"
                    };
                }

                return {
                        TokenInferenceStatus::Ok,
                        *encoded,
                        0.82,
                        7,
                        {}
                };
            }

            [[nodiscard]] bool isAvailable() const noexcept override {
                return true;
            }

            [[nodiscard]] std::string id() const override {
                return "stub-token-backend";
            }
        };

        StubTokenBackend backend;

        mozart::generation::PatternProposal directSource;
        directSource.metadata.confidence = 1.0;
        directSource.noteEvents = {
                {0.0, 0.5, 49, 100, 0},
                {1.0, 0.5, 59, 127, 0}
        };
        const auto directEncoded =
                MidiEventTokenizer::encode(directSource);
        assert(directEncoded.has_value());
        assert(directEncoded->size() == 10);
        const auto directDecoded =
                mozart::generation::MidiEventDetokenizer::decode(*directEncoded);
        assert(directDecoded.has_value());
        assert(directDecoded->noteEvents.size() == 2);
        assert(directDecoded->noteEvents[0].note == 49);
        assert(directDecoded->noteEvents[1].note == 59);

        mozart::generation::GenerationRequest directRequest;
        directRequest.bars = 1;
        directRequest.polyphony = 2;
        directRequest.minNote = 49;
        directRequest.maxNote = 59;
        directRequest.density = 1.0;
        const auto directValidation =
                mozart::generation::PatternProposalValidator::validate(
                        directRequest,
                        *directDecoded);
        assert(directValidation.ok());
        assert(directValidation.proposal.noteEvents.size() == 2);

        LocalNeuralPatternProvider provider(backend);

        mozart::generation::GenerationRequest request;
        request.bars = 1;
        request.polyphony = 2;
        request.minNote = 49;
        request.maxNote = 59;
        request.density = 1.0;

        const auto result = provider.generate(request);
        assert(result.ok());
        assert(result.proposal.metadata.generatorId == "stub-token-backend");
        assert(std::abs(result.proposal.metadata.confidence - 0.82) < 1.0e-12);
        assert(result.proposal.metadata.generationTimeMs == 7);
        assert(result.proposal.noteEvents.size() == 2);

        class UnavailableBackend final : public TokenInferenceBackend {
        public:
            [[nodiscard]] TokenInferenceResult generateTokens(
                    const mozart::generation::GenerationRequest&,
                    const std::size_t) override {
                return {
                        TokenInferenceStatus::Unavailable,
                        {},
                        0.0,
                        0,
                        "test backend unavailable"
                };
            }

            [[nodiscard]] bool isAvailable() const noexcept override {
                return false;
            }

            [[nodiscard]] std::string id() const override {
                return "unavailable";
            }
        };

        UnavailableBackend unavailableBackend;
        LocalNeuralPatternProvider unavailableProvider(unavailableBackend);
        assert(!unavailableProvider.isAvailable());
        const auto unavailable = unavailableProvider.generate(request);
        assert(
                unavailable.status ==
                mozart::generation::GenerationStatus::Unavailable);
        assert(!unavailable.ok());
    }


    {
        using mozart::generation::ModelCatalog;
        using mozart::generation::ModelCatalogEntry;
        using mozart::generation::ModelDistributionClass;
        using mozart::generation::TokenInferenceBackend;
        using mozart::generation::TokenInferenceResult;
        using mozart::generation::TokenInferenceStatus;

        class CatalogBackend final : public TokenInferenceBackend {
        public:
            [[nodiscard]] TokenInferenceResult generateTokens(
                    const mozart::generation::GenerationRequest&,
                    const std::size_t) override {
                return {
                        TokenInferenceStatus::Unavailable,
                        {},
                        0.0,
                        0,
                        "catalog test"
                };
            }

            [[nodiscard]] bool isAvailable() const noexcept override {
                return true;
            }

            [[nodiscard]] std::string id() const override {
                return "catalog-test-backend";
            }
        };

        CatalogBackend backend;
        ModelCatalog catalog;
        assert(catalog.registerBackend(backend));
        assert(!catalog.registerBackend(backend));

        assert(catalog.registerModel({
                "private-test-model",
                "Private Test Model",
                "catalog-test-backend",
                "/data/user/0/mozart/models/private-test.tflite",
                "/data/user/0/mozart/models/private-test.manifest",
                ModelDistributionClass::PrivateExperimental,
                true
        }));
        assert(!catalog.registerModel({
                "private-test-model",
                "Duplicate",
                "catalog-test-backend",
                {},
                {},
                ModelDistributionClass::PrivateExperimental,
                true
        }));

        const auto* model = catalog.findModel("private-test-model");
        assert(model != nullptr);
        assert(model->displayName == "Private Test Model");
        assert(model->distributionClass == ModelDistributionClass::PrivateExperimental);
        assert(catalog.isPrivateExperimental("private-test-model"));
        assert(!catalog.isPrivateExperimental("missing-model"));
        assert(catalog.resolveBackend("private-test-model") == &backend);
        assert(catalog.resolveBackend("missing-model") == nullptr);
        assert(catalog.resolveBackend("private-test-model") == &backend);
        assert(catalog.modelAt(0) == model);
        assert(catalog.modelAt(1) == nullptr);
        assert(!catalog.selectModel("missing-model"));
        assert(catalog.selectModel("private-test-model"));
        assert(catalog.selectedModelId() == "private-test-model");
        assert(catalog.selectedModel() != nullptr);
        assert(catalog.selectedModel()->modelId == "private-test-model");
        assert(catalog.resolveSelectedBackend() == &backend);
        assert(catalog.modelCount() == 1);
        assert(catalog.backendCount() == 1);
        assert(catalog.setEnabled("private-test-model", false));
        assert(catalog.resolveBackend("private-test-model") == nullptr);
        assert(!catalog.setEnabled("missing-model", true));
        assert(catalog.setEnabled("private-test-model", true));
        assert(catalog.resolveBackend("private-test-model") == &backend);
        catalog.clearSelection();
        assert(catalog.selectedModelId().empty());
        assert(catalog.selectedModel() == nullptr);

        model = nullptr;
        catalog.clear();
        assert(catalog.modelCount() == 0);
        assert(catalog.backendCount() == 0);
    }

    {
        using mozart::generation::GenerationRequest;
        using mozart::generation::PatternProposal;
        using mozart::generation::PatternProposalValidator;
        using mozart::generation::PatternValidationStatus;

        GenerationRequest request;
        request.bars = 1;
        request.polyphony = 2;
        request.minNote = 48;
        request.maxNote = 60;
        request.density = 1.0;

        PatternProposal proposal;
        proposal.metadata.seed = request.seed;
        proposal.metadata.confidence = 0.9;
        proposal.noteEvents = {
                {0.0, 2.0, 49, 100, 0},
                {0.0, 2.0, 49, 100, 0},
                {0.0, 2.0, 51, 0, 0},
                {0.0, 2.0, 54, 90, 0}
        };
        proposal.controlEvents = {
                {1.0, 0, 74, 64},
                {1.0, 0, 74, 64}
        };

        const auto first = PatternProposalValidator::validate(request, proposal);
        assert(first.ok());
        assert(first.status == PatternValidationStatus::Ok);
        assert(first.proposal.noteEvents.size() == 2);
        assert(first.proposal.noteEvents[0].note == 49);
        assert(first.proposal.noteEvents[1].note == 50);
        assert(first.proposal.noteEvents[1].velocity == 1);
        assert(first.proposal.controlEvents.size() == 1);

        auto permuted = proposal;
        std::reverse(permuted.noteEvents.begin(), permuted.noteEvents.end());
        const auto second = PatternProposalValidator::validate(request, permuted);
        assert(second.ok());
        assert(second.proposal == first.proposal);

        auto densityRequest = request;
        densityRequest.polyphony = 1;
        densityRequest.density = 0.25;

        PatternProposal dense;
        dense.metadata.seed = densityRequest.seed;
        dense.metadata.confidence = 1.0;
        dense.noteEvents = {
                {0.0, 0.20, 49, 100, 0},
                {0.25, 0.20, 50, 100, 0},
                {0.50, 0.20, 52, 100, 0},
                {0.75, 0.20, 54, 100, 0},
                {1.00, 0.20, 56, 100, 0},
                {1.25, 0.20, 57, 100, 0}
        };

        const auto densityResult =
                PatternProposalValidator::validate(densityRequest, dense);
        assert(densityResult.ok());
        assert(densityResult.proposal.noteEvents.size() == 4);
        assert(densityResult.proposal.noteEvents.back().startBeat == 0.75);

        auto polyphonicDensityRequest = request;
        polyphonicDensityRequest.bars = 1;
        polyphonicDensityRequest.polyphony = 4;
        polyphonicDensityRequest.density = 0.5;

        PatternProposal polyphonicDense;
        polyphonicDense.metadata.seed = polyphonicDensityRequest.seed;
        polyphonicDense.metadata.confidence = 1.0;
        polyphonicDense.noteEvents.clear();
        const std::uint8_t notes[] = {
                49, 50, 52, 54, 56, 57, 59, 61,
                62, 64, 66, 68
        };
        for (std::size_t i = 0; i < 12; ++i) {
            polyphonicDense.noteEvents.push_back(
                    mozart::musical::MusicalNoteEvent{
                            static_cast<double>(i) * 0.25,
                            0.10,
                            notes[i],
                            100,
                            0});
        }

        const auto polyphonicDensityResult =
                PatternProposalValidator::validate(
                        polyphonicDensityRequest,
                        polyphonicDense);
        assert(polyphonicDensityResult.ok());
        assert(polyphonicDensityResult.proposal.noteEvents.size() == 12);

        auto outside = proposal;
        outside.noteEvents = {{3.9, 0.2, 54, 100, 0}};
        const auto outsideResult =
                PatternProposalValidator::validate(request, outside);
        assert(outsideResult.status == PatternValidationStatus::InvalidProposal);
        assert(!outsideResult.ok());

        auto impossible = request;
        impossible.minNote = 60;
        impossible.maxNote = 60;
        PatternProposal unrepresentable;
        unrepresentable.metadata.confidence = 1.0;
        unrepresentable.noteEvents = {{0.0, 0.5, 60, 100, 0}};
        const auto impossibleResult =
                PatternProposalValidator::validate(impossible, unrepresentable);
        assert(
                impossibleResult.status ==
                PatternValidationStatus::NoUsableEvents);
        assert(!impossibleResult.ok());
    }

    {
        const auto message = mozart::midi::noteOn(0, 60, 100, 1234, 7);
        assert(message.has_value());
        assert(message->status == 0x90);
        assert(message->data1 == 60);
        assert(message->data2 == 100);
        assert(message->size == 3);
        assert(message->timestampNanos == 1234);
        assert(message->portId == 7);
        assert(message->isValid());
    }

    {
        assert(!mozart::midi::noteOn(16, 60, 100).has_value());
        assert(!mozart::midi::noteOn(0, 128, 100).has_value());
        assert(!mozart::midi::controlChange(0, 0, 128).has_value());
    }

    {
        const auto beat = mozart::timing::beatAtTime(0.0, 0.0, 120.0, 1.0);
        assert(std::abs(beat - 2.0) < 1.0e-12);
        assert(std::abs(mozart::timing::quantizeBeat(3.2, 4.0) - 4.0) < 1.0e-12);
        assert(std::abs(mozart::timing::nextQuantizedBeat(3.2, 4.0) - 4.0) < 1.0e-12);
        assert(std::abs(mozart::timing::nextQuantizedBeat(4.0, 4.0) - 8.0) < 1.0e-12);
        assert(std::abs(mozart::timing::nextQuantizedBeat(7.999, 4.0) - 8.0) < 1.0e-12);
    }

    {
        const auto pattern = mozart::generation::RhythmGenerator::euclidean(16, 4);
        assert(pattern.size() == 16);
        assert(pattern[0] && pattern[4] && pattern[8] && pattern[12]);
    }

    {
        const auto a = mozart::generation::RhythmGenerator::seededVelocityPattern(32, 42);
        const auto b = mozart::generation::RhythmGenerator::seededVelocityPattern(32, 42);
        assert(a == b);
        assert(a.size() == 32);
    }

    {
        const mozart::musical::KeyScale fSharpMinor(
                6, mozart::musical::Scale::NaturalMinor);

        assert(fSharpMinor.isValid());
        assert(fSharpMinor.containsMidiNote(42));
        assert(fSharpMinor.containsMidiNote(45));
        assert(fSharpMinor.containsMidiNote(49));
        assert(!fSharpMinor.containsMidiNote(43));

        const auto a =
                mozart::generation::BassGenerator::generateBar(
                        fSharpMinor, 2, 1234);
        const auto b =
                mozart::generation::BassGenerator::generateBar(
                        fSharpMinor, 2, 1234);

        assert(a == b);
        assert(a.size() == 8);

        const auto arpA =
                mozart::generation::ArpeggioGenerator::generateBar(
                        fSharpMinor, 4, 1234);
        const auto arpB =
                mozart::generation::ArpeggioGenerator::generateBar(
                        fSharpMinor, 4, 1234);

        assert(arpA == arpB);
        assert(arpA.size() == 8);

        const auto sparseBass =
                mozart::generation::BassGenerator::generateBar(
                        fSharpMinor,
                        2,
                        1234,
                        0,
                        mozart::generation::PatternDensity::Sparse);
        const auto normalBass =
                mozart::generation::BassGenerator::generateBar(
                        fSharpMinor,
                        2,
                        1234,
                        0,
                        mozart::generation::PatternDensity::Normal);
        const auto sparseAgain =
                mozart::generation::BassGenerator::generateBar(
                        fSharpMinor,
                        2,
                        1234,
                        0,
                        mozart::generation::PatternDensity::Sparse);

        assert(sparseBass == sparseAgain);
        assert(!sparseBass.empty());
        assert(sparseBass.size() <= normalBass.size());
        assert(normalBass.size() <= a.size());

        const auto sparseArp =
                mozart::generation::ArpeggioGenerator::generateBar(
                        fSharpMinor,
                        4,
                        1234,
                        0,
                        mozart::generation::PatternDensity::Sparse);
        assert(!sparseArp.empty());
        assert(sparseArp.size() <= arpA.size());

        assert(
                mozart::generation::accentBoost(
                        mozart::generation::PatternAccent::Off) == 0);
        assert(
                mozart::generation::accentBoost(
                        mozart::generation::PatternAccent::Mild) == 10);
        assert(
                mozart::generation::accentBoost(
                        mozart::generation::PatternAccent::Strong) == 20);
        assert(
                std::abs(
                        mozart::generation::swingOffsetBeats(
                                mozart::generation::PatternSwing::Off)) < 1.0e-12);
        assert(
                std::abs(
                        mozart::generation::swingOffsetBeats(
                                mozart::generation::PatternSwing::Light) -
                        1.0 / 12.0) < 1.0e-12);
        assert(
                std::abs(
                        mozart::generation::swingOffsetBeats(
                                mozart::generation::PatternSwing::Full) -
                        1.0 / 6.0) < 1.0e-12);

        const auto flatAccent =
                mozart::generation::BassGenerator::generateBar(
                        fSharpMinor,
                        2,
                        1234,
                        0,
                        mozart::generation::PatternDensity::Full,
                        mozart::generation::PatternAccent::Off);
        const auto strongAccent =
                mozart::generation::BassGenerator::generateBar(
                        fSharpMinor,
                        2,
                        1234,
                        0,
                        mozart::generation::PatternDensity::Full,
                        mozart::generation::PatternAccent::Strong);
        assert(flatAccent.size() == strongAccent.size());
        assert(strongAccent[0].velocity >= std::min(127u, static_cast<unsigned int>(flatAccent[0].velocity) + 20u));
        assert(strongAccent[4].velocity >= std::min(127u, static_cast<unsigned int>(flatAccent[4].velocity) + 20u));
        assert(strongAccent[1].velocity == flatAccent[1].velocity);
        assert(strongAccent[5].velocity == flatAccent[5].velocity);

        for (const auto& event : arpA) {
            assert(event.startBeat >= 0.0);
            assert(event.startBeat < 4.0);
            assert(event.durationBeats > 0.0);
            assert(event.note >= 60);
            assert(event.note < 96);
            assert(fSharpMinor.containsMidiNote(event.note));
            assert(event.velocity >= 76);
            assert(event.velocity <= 115);
            assert(event.channel == 0);
        }

        for (const auto& event : a) {
            assert(event.startBeat >= 0.0);
            assert(event.startBeat < 4.0);
            assert(event.durationBeats > 0.0);
            assert(event.note >= 36);
            assert(event.note < 60);
            assert(fSharpMinor.containsMidiNote(event.note));
            assert(event.velocity >= 88);
            assert(event.velocity <= 119);
            assert(event.channel == 0);
        }
    }


    {
        using mozart::musical::AudioKeyDetector;
        const AudioKeyDetector::Chroma cMajor{
            1.0, 0.3, 0.7, 0.4, 0.7, 0.4,
            0.4, 0.9, 0.1, 0.4, 0.1, 0.2
        };
        const auto cMajorResult = AudioKeyDetector::estimate(cMajor);
        assert(cMajorResult.valid);
        assert(cMajorResult.keyScale.rootPitchClass() == 0);
        assert(cMajorResult.keyScale.scale() == mozart::musical::Scale::Major);
        assert(cMajorResult.confidence > 0.0);
        assert(cMajorResult.score > cMajorResult.runnerUpScore);

        const AudioKeyDetector::Chroma aMinor{
            0.7, 0.2, 0.7, 0.4, 0.9, 0.3,
            0.3, 0.4, 1.0, 0.4, 0.2, 0.1
        };
        const auto aMinorResult = AudioKeyDetector::estimate(aMinor);
        assert(aMinorResult.valid);
        assert(aMinorResult.keyScale.rootPitchClass() == 9);
        assert(aMinorResult.keyScale.scale() == mozart::musical::Scale::NaturalMinor);
        assert(aMinorResult.confidence > 0.0);
        assert(aMinorResult.score > aMinorResult.runnerUpScore);

        const AudioKeyDetector::Chroma silence{};
        assert(!AudioKeyDetector::estimate(silence).valid);

        const AudioKeyDetector::Chroma invalid{
            1.0, 0.0, 0.0, -1.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        };
        assert(!AudioKeyDetector::estimate(invalid).valid);
    }

    {
        using mozart::musical::AudioKeyDetector;
        using mozart::musical::AudioKeyStabilityFilter;

        const AudioKeyDetector::Chroma cMajor{
            1.0, 0.3, 0.7, 0.4, 0.7, 0.4,
            0.4, 0.9, 0.1, 0.4, 0.1, 0.2
        };
        const auto cMajorResult = AudioKeyDetector::estimate(cMajor);
        assert(cMajorResult.valid);
        assert(cMajorResult.keyScale.rootPitchClass() == 0);
        assert(cMajorResult.keyScale.scale() == mozart::musical::Scale::Major);
        assert(cMajorResult.confidence > 0.0);
        assert(cMajorResult.score > cMajorResult.runnerUpScore);

        AudioKeyStabilityFilter filter(0.10, 3);
        assert(!filter.snapshot().hasStableKey);
        filter.update(cMajorResult);
        assert(!filter.snapshot().hasStableKey);
        filter.update(cMajorResult);
        assert(!filter.snapshot().hasStableKey);
        filter.update(cMajorResult);
        const auto stable = filter.snapshot();
        assert(stable.hasStableKey);
        assert(stable.keyScale.rootPitchClass() == 0);
        assert(stable.keyScale.scale() == mozart::musical::Scale::Major);
        assert(stable.confidence >= cMajorResult.confidence);

        const AudioKeyDetector::Chroma aMinor{
            0.7, 0.2, 0.7, 0.4, 0.9, 0.3,
            0.3, 0.4, 1.0, 0.4, 0.2, 0.1
        };
        const auto aMinorResult = AudioKeyDetector::estimate(aMinor);
        assert(aMinorResult.valid);
        assert(aMinorResult.keyScale.rootPitchClass() == 9);
        assert(aMinorResult.keyScale.scale() == mozart::musical::Scale::NaturalMinor);
        assert(aMinorResult.confidence > 0.0);
        assert(aMinorResult.score > aMinorResult.runnerUpScore);

        filter.reset();
        filter.update(aMinorResult);
        assert(!filter.snapshot().hasStableKey);
        filter.update(aMinorResult);
        filter.update(aMinorResult);
        assert(filter.snapshot().hasStableKey);
        assert(filter.snapshot().keyScale.rootPitchClass() == 9);

        const AudioKeyDetector::Chroma silence{};
        const auto silenceResult = AudioKeyDetector::estimate(silence);
        assert(!silenceResult.valid);
        filter.update(silenceResult);
        assert(filter.snapshot().consecutiveObservations == 0);
        assert(filter.snapshot().hasStableKey);
        
        filter.reset();
        assert(!filter.snapshot().hasStableKey);

        const AudioKeyDetector::Chroma invalid{
            1.0, 0.0, 0.0, -1.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        };
        assert(!AudioKeyDetector::estimate(invalid).valid);
    }

    {
        mozart::midi::MidiReceiveQueue queue(4);
        mozart::midi::MidiInputParser parser;

        const std::uint8_t notes[]{0x90, 60, 100, 61, 0};
        parser.feed(notes, sizeof(notes), 123456ULL, 7, queue);
        assert(queue.size() == 2);

        mozart::midi::MidiShortMessage first{};
        mozart::midi::MidiShortMessage second{};
        assert(queue.tryPop(first));
        assert(queue.tryPop(second));
        assert(first.status == 0x90);
        assert(first.data1 == 60);
        assert(first.data2 == 100);
        assert(first.timestampNanos == 123456ULL);
        assert(first.portId == 7);
        assert(second.status == 0x90);
        assert(second.data1 == 61);
        assert(second.data2 == 0);

        // Running status may span Android callback boundaries.
        parser.reset();
        mozart::midi::MidiReceiveQueue runningQueue;
        const std::uint8_t partA[]{0x90, 64};
        const std::uint8_t partB[]{110, 65, 111};
        parser.feed(partA, sizeof(partA), 200ULL, 9, runningQueue);
        assert(runningQueue.size() == 0);
        parser.feed(partB, sizeof(partB), 201ULL, 9, runningQueue);
        assert(runningQueue.size() == 2);
        assert(runningQueue.tryPop(first));
        assert(first.status == 0x90 && first.data1 == 64 && first.data2 == 110);
        assert(first.timestampNanos == 201ULL);
        assert(runningQueue.tryPop(second));
        assert(second.status == 0x90 && second.data1 == 65 && second.data2 == 111);

        // Realtime bytes are transparent to channel-voice parsing.
        parser.reset();
        mozart::midi::MidiReceiveQueue realtimeQueue;
        const std::uint8_t realtime[]{0x90, 67, 120, 0xF8, 0x80, 67, 0};
        parser.feed(realtime, sizeof(realtime), 300ULL, 10, realtimeQueue);
        assert(realtimeQueue.size() == 2);

        // The queue stays bounded and keeps the newest event when full.
        mozart::midi::MidiReceiveQueue boundedQueue(2);
        const auto makeNote = [](std::uint8_t note, std::uint64_t time) {
            return mozart::midi::noteOn(0, note, 100, time, 11).value();
        };
        assert(boundedQueue.push(makeNote(60, 1)));
        assert(boundedQueue.push(makeNote(61, 2)));
        assert(boundedQueue.push(makeNote(62, 3)));
        assert(boundedQueue.size() == 2);
        assert(boundedQueue.droppedCount() == 1);
        assert(boundedQueue.tryPop(first));
        assert(first.data1 == 61 && first.timestampNanos == 2);
        assert(boundedQueue.tryPop(second));
        assert(second.data1 == 62 && second.timestampNanos == 3);

        const auto boundedSnapshot = boundedQueue.snapshot();
        assert(boundedSnapshot.pending == 0);
        assert(boundedSnapshot.accepted == 3);
        assert(boundedSnapshot.dropped == 1);
        assert(boundedSnapshot.hasLast);
        assert(boundedSnapshot.last.data1 == 62);

        boundedQueue.reset();
        const auto resetSnapshot = boundedQueue.snapshot();
        assert(resetSnapshot.pending == 0);
        assert(resetSnapshot.accepted == 0);
        assert(resetSnapshot.dropped == 0);
        assert(!resetSnapshot.hasLast);
    }

    {
        using mozart::midi::MidiEndpointDescriptor;
        using mozart::midi::MidiEndpointSelector;
        using mozart::midi::PortDirection;
        using mozart::midi::TransportKind;

        const std::vector<MidiEndpointDescriptor> candidates{
            MidiEndpointDescriptor{
                10, 0, PortDirection::Output, TransportKind::Usb,
                "Arturia MicroFreak output", "Arturia", "MicroFreak"
            },
            MidiEndpointDescriptor{
                11, 0, PortDirection::Input, TransportKind::Usb,
                "Generic USB MIDI", "Other", "Controller"
            },
            MidiEndpointDescriptor{
                12, 1, PortDirection::Input, TransportKind::Bluetooth,
                "Arturia MicroFreak", "Arturia", "MicroFreak"
            },
            MidiEndpointDescriptor{
                14, 2, PortDirection::Input, TransportKind::Usb,
                "Arturia MicroFreak", "Arturia", "MicroFreak"
            },
            MidiEndpointDescriptor{
                13, 1, PortDirection::Input, TransportKind::Usb,
                "Arturia MicroFreak", "Arturia", "MicroFreak"
            }
        };

        const auto selection =
                MidiEndpointSelector::selectPreferredOutput(
                        candidates, "Arturia", "MicroFreak");

        assert(selection.selected());
        assert(*selection.candidateIndex == 3);
        assert(candidates[*selection.candidateIndex].deviceId == 14);
        assert(candidates[*selection.candidateIndex].portNumber == 2);
        assert(candidates[*selection.candidateIndex].canReceiveFromMozart());

        const std::vector<MidiEndpointDescriptor> unrelated{
            MidiEndpointDescriptor{
                21, 0, PortDirection::Input, TransportKind::Usb,
                "Generic USB MIDI", "Other", "Controller"
            },
            MidiEndpointDescriptor{
                22, 0, PortDirection::Input, TransportKind::Usb,
                "Arturia KeyLab", "Arturia", "KeyLab"
            }
        };

        const auto noMatch =
                MidiEndpointSelector::selectPreferredOutput(
                        unrelated, "Arturia", "MicroFreak");
        assert(!noMatch.selected());
    }

    {
        class MockMidiOutput final : public mozart::midi::MidiOutputTransport {
        public:
            mozart::midi::MidiSendResult send(
                    const mozart::midi::MidiShortMessage& message) noexcept override {
                last = message;
                ++sendCount;
                return {
                    mozart::midi::MidiTransportStatus::Ok,
                    message.size
                };
            }

            void close() noexcept override {}

            mozart::midi::MidiShortMessage last{};
            std::size_t sendCount = 0;
        };

        MockMidiOutput output;
        const auto message =
                mozart::midi::noteOn(0, 64, 111, 987654321ULL, 42);

        assert(message.has_value());
        const auto result = output.send(*message);
        assert(result.ok());
        assert(result.bytesSent == 3);
        assert(output.sendCount == 1);
        assert(output.last.status == 0x90);
        assert(output.last.data1 == 64);
        assert(output.last.data2 == 111);
        assert(output.last.timestampNanos == 987654321ULL);
        assert(output.last.portId == 42);
    }


    {
        using mozart::musical::Chord;
        using mozart::musical::ChordQuality;

        const Chord fMajor7(5, ChordQuality::Major7);
        assert(fMajor7.isValid());
        assert(fMajor7.noteCount() == 4);
        assert(fMajor7.pitchClassAt(0) == 5);
        assert(fMajor7.pitchClassAt(1) == 9);
        assert(fMajor7.pitchClassAt(2) == 0);
        assert(fMajor7.pitchClassAt(3) == 4);
        assert(fMajor7.containsPitchClass(0));
        assert(fMajor7.containsMidiNote(65));
        assert(!fMajor7.containsPitchClass(2));

        const Chord bDim7(11, ChordQuality::Diminished7);
        assert(bDim7.noteCount() == 4);
        assert(bDim7.containsPitchClass(2));
        assert(bDim7.containsPitchClass(5));
        assert(bDim7.containsPitchClass(8));

        assert(fMajor7.midiNote(0, 3) == 53);
        assert(fMajor7.midiNote(1, 3) == 57);
        assert(fMajor7.midiNote(2, 3) == 60);
        assert(fMajor7.midiNote(4, 3) == 65);
    }



    {
        using mozart::generation::ChordProgressionGenerator;
        using mozart::musical::ChordQuality;
        using mozart::musical::KeyScale;
        using mozart::musical::Scale;

        const KeyScale fSharpMinor(6, Scale::NaturalMinor);
        const auto a =
                ChordProgressionGenerator::generate(
                        fSharpMinor, 8, 1234);
        const auto b =
                ChordProgressionGenerator::generate(
                        fSharpMinor, 8, 1234);

        assert(a.size() == 8);
        assert(a == b);

        for (const auto& chord : a) {
            assert(chord.isValid());
            assert(chord.noteCount() == 3);
            for (std::size_t i = 0; i < chord.noteCount(); ++i) {
                assert(fSharpMinor.containsMidiNote(chord.pitchClassAt(i) + 60));
            }
        }

        assert(
                a[0].quality() == ChordQuality::Minor ||
                a[0].quality() == ChordQuality::Major);

        const auto major =
                ChordProgressionGenerator::generate(
                        KeyScale{0, Scale::Major}, 4, 1234);
        assert(major.size() == 4);
        for (const auto& chord : major) {
            assert(chord.isValid());
            for (std::size_t i = 0; i < chord.noteCount(); ++i) {
                assert((KeyScale{0, Scale::Major}.containsMidiNote(
                        chord.pitchClassAt(i) + 60)));
            }
        }

        const auto empty =
                ChordProgressionGenerator::generate(
                        KeyScale{0, Scale::Major}, 0, 1234);
        assert(empty.empty());
    }



    {
        using mozart::musical::Chord;
        using mozart::musical::ChordQuality;
        using mozart::musical::VoiceLeading;
        using mozart::musical::VoiceLeadingOptions;

        const std::vector<Chord> progression{
            Chord{0, ChordQuality::Major},
            Chord{9, ChordQuality::Minor},
            Chord{5, ChordQuality::Major},
            Chord{7, ChordQuality::Major}
        };

        const VoiceLeadingOptions options{
            .baseOctave = 3,
            .minNote = 48,
            .maxNote = 84
        };

        const auto first = VoiceLeading::generate(progression, options);
        const auto second = VoiceLeading::generate(progression, options);

        assert(first == second);
        assert(first.size() == progression.size());

        for (std::size_t chordIndex = 0;
                chordIndex < first.size();
                ++chordIndex) {
            const auto& voicing = first[chordIndex];
            assert(voicing.size() == progression[chordIndex].noteCount());
            assert(!voicing.empty());
            for (std::size_t voice = 0; voice < voicing.size(); ++voice) {
                assert(voicing[voice] >= options.minNote);
                assert(voicing[voice] <= options.maxNote);
                assert(
                        progression[chordIndex].containsMidiNote(
                                voicing[voice]));
                if (voice > 0) {
                    assert(voicing[voice] > voicing[voice - 1]);
                }
            }
        }

        // C major -> A minor should use an inversion that keeps the upper
        // voices close instead of forcing the root-position octave jump.
        assert(first[0].size() == 3);
        assert(first[1].size() == 3);
        assert(
                std::abs(
                        static_cast<int>(first[1][0]) -
                        static_cast<int>(first[0][0])) <= 5);
        assert(
                std::abs(
                        static_cast<int>(first[1][1]) -
                        static_cast<int>(first[0][1])) <= 7);
        assert(
                std::abs(
                        static_cast<int>(first[1][2]) -
                        static_cast<int>(first[0][2])) <= 7);

        assert(VoiceLeading::generate({}, options).empty());

        const VoiceLeadingOptions invalidRange{
            .baseOctave = 3,
            .minNote = 90,
            .maxNote = 80
        };
        assert(VoiceLeading::generate(progression, invalidRange).empty());
    }


    {
        using mozart::scheduler::PerformanceScene;
        using mozart::scheduler::AccompanimentRole;
        using mozart::generation::PatternAccent;
        using mozart::generation::PatternDensity;
        using mozart::generation::PatternSwing;

        const auto scene0 = PerformanceScene::preset(0);
        const auto scene1 = PerformanceScene::preset(1);
        const auto scene2 = PerformanceScene::preset(2);
        const auto scene3 = PerformanceScene::preset(3);
        const auto wrapped = PerformanceScene::preset(7);

        assert(scene0.index == 0);
        assert(scene0.role == AccompanimentRole::Bass);
        assert(scene0.density == PatternDensity::Full);
        assert(scene0.accent == PatternAccent::Off);
        assert(scene0.swing == PatternSwing::Off);

        assert(scene1.index == 1);
        assert(scene1.role == AccompanimentRole::Arpeggio);
        assert(scene1.density == PatternDensity::Normal);
        assert(scene1.accent == PatternAccent::Mild);

        assert(scene2.index == 2);
        assert(scene2.role == AccompanimentRole::Bass);
        assert(scene2.density == PatternDensity::Sparse);
        assert(scene2.accent == PatternAccent::Strong);
        assert(scene2.swing == PatternSwing::Light);

        assert(scene3.index == 3);
        assert(scene3.role == AccompanimentRole::Arpeggio);
        assert(scene3.density == PatternDensity::Full);
        assert(scene3.accent == PatternAccent::Strong);
        assert(scene3.swing == PatternSwing::Full);

        assert(wrapped.index == 3);
        assert(PerformanceScene::kSceneCount == 4);
        assert(scene0.seed != scene1.seed);
        assert(scene1.seed != scene2.seed);
        assert(scene2.seed != scene3.seed);
    }

    {
        using mozart::generation::NoteRepeat;
        using mozart::generation::NoteRepeatRate;
        using mozart::musical::MusicalNoteEvent;

        const std::vector<MusicalNoteEvent> source{
            MusicalNoteEvent{0.0, 0.4, 60, 100, 2},
            MusicalNoteEvent{0.5, 0.3, 64, 90, 2}
        };

        const auto off = NoteRepeat::apply(source, NoteRepeatRate::Off);
        assert(off == source);

        const auto doubled = NoteRepeat::apply(source, NoteRepeatRate::Double);
        assert(doubled.size() == 4);
        assert(doubled[0].note == 60 && doubled[1].note == 60);
        assert(doubled[2].note == 64 && doubled[3].note == 64);
        assert(doubled[0].channel == 2 && doubled[3].channel == 2);
        assert(std::abs(doubled[1].startBeat - 0.2) < 1.0e-12);
        assert(std::abs(doubled[3].startBeat - 0.65) < 1.0e-12);
        assert(doubled[0].durationBeats <= 0.2);
        assert(doubled[2].durationBeats <= 0.15);

        const auto quadrupled =
                NoteRepeat::apply(source, NoteRepeatRate::Quadruple);
        assert(quadrupled.size() == 8);
        assert(quadrupled[7].startBeat < 0.8);
    }

    {
        using mozart::scheduler::MacroControl;
        using mozart::scheduler::MacroControls;

        const auto lowEnergy = MacroControls::map(MacroControl::Energy, 0);
        assert(lowEnergy.density == mozart::generation::PatternDensity::Sparse);
        assert(lowEnergy.accent == mozart::generation::PatternAccent::Off);

        const auto midEnergy = MacroControls::map(MacroControl::Energy, 64);
        assert(midEnergy.density == mozart::generation::PatternDensity::Full);
        assert(midEnergy.accent == mozart::generation::PatternAccent::Mild);

        const auto highEnergy = MacroControls::map(MacroControl::Energy, 127);
        assert(highEnergy.density == mozart::generation::PatternDensity::Full);
        assert(highEnergy.accent == mozart::generation::PatternAccent::Strong);

        const auto lowMotion = MacroControls::map(MacroControl::Motion, 0);
        assert(lowMotion.swing == mozart::generation::PatternSwing::Off);
        assert(lowMotion.noteRepeat == mozart::generation::NoteRepeatRate::Off);

        const auto midMotion = MacroControls::map(MacroControl::Motion, 64);
        assert(midMotion.swing == mozart::generation::PatternSwing::Full);
        assert(midMotion.noteRepeat == mozart::generation::NoteRepeatRate::Triple);

        const auto highMotion = MacroControls::map(MacroControl::Motion, 127);
        assert(highMotion.swing == mozart::generation::PatternSwing::Full);
        assert(highMotion.noteRepeat == mozart::generation::NoteRepeatRate::Quadruple);
    }

    {
        using mozart::midi::ControllerAction;
        using mozart::midi::ControllerBinding;
        using mozart::midi::ControllerMapping;

        ControllerMapping mapping;
        const auto scene = mapping.resolve(
                mozart::midi::controlChange(0, 20, 127).value());
        assert(scene.action == ControllerAction::Scene);
        assert(scene.value == 127);

        const auto repeat = mapping.resolve(
                mozart::midi::controlChange(0, 24, 64).value());
        assert(repeat.action == ControllerAction::NoteRepeat);
        assert(repeat.value == 64);

        const auto mutation = mapping.resolve(
                mozart::midi::controlChange(0, 25, 100).value());
        assert(mutation.action == ControllerAction::Mutation);

        const auto energy = mapping.resolve(
                mozart::midi::controlChange(0, 26, 127).value());
        assert(energy.action == ControllerAction::MacroEnergy);

        const auto motion = mapping.resolve(
                mozart::midi::controlChange(0, 27, 64).value());
        assert(motion.action == ControllerAction::MacroMotion);

        const auto wrongChannel = mapping.resolve(
                mozart::midi::controlChange(1, 20, 100).value());
        assert(wrongChannel.action == ControllerAction::None);

        const auto wrongType = mapping.resolve(
                mozart::midi::noteOn(0, 20, 100).value());
        assert(wrongType.action == ControllerAction::None);

        mapping.setBindings({
            ControllerBinding{0, 70, ControllerAction::Accent}
        });
        assert(
                mapping.resolve(
                        mozart::midi::controlChange(0, 70, 55).value()).action ==
                ControllerAction::Accent);
        assert(
                mapping.resolve(
                        mozart::midi::controlChange(0, 20, 55).value()).action ==
                ControllerAction::None);

        mapping.resetToDefaults();
        assert(
                mapping.resolve(
                        mozart::midi::controlChange(0, 20, 55).value()).action ==
                ControllerAction::Scene);
    }

    {
        using mozart::musical::AudioChromaEstimator;

        constexpr std::uint32_t sampleRate = 48000;
        constexpr std::size_t sampleCount = 4096;
        std::vector<std::int16_t> samples(sampleCount);

        constexpr double frequency = 440.0;
        for (std::size_t i = 0; i < sampleCount; ++i) {
            const double phase =
                    2.0 * 3.14159265358979323846 *
                    frequency * static_cast<double>(i) /
                    static_cast<double>(sampleRate);
            samples[i] = static_cast<std::int16_t>(
                    std::sin(phase) * 30000.0);
        }

        const auto chroma = AudioChromaEstimator::estimate(
                samples.data(),
                samples.size(),
                sampleRate);

        std::size_t strongestPitchClass = 0;
        for (std::size_t i = 1; i < chroma.size(); ++i) {
            if (chroma[i] > chroma[strongestPitchClass]) {
                strongestPitchClass = i;
            }
        }

        assert(strongestPitchClass == 9); // A
        assert(chroma[9] > 0.5);
    }


    {
        using mozart::musical::AudioKeyDetector;
        using mozart::musical::KeyContext;
        using mozart::musical::KeyContextSource;

        const mozart::musical::KeyScale manualFallback(
                6, mozart::musical::Scale::NaturalMinor);
        const AudioKeyDetector::Chroma cMajor{
            1.0, 0.3, 0.7, 0.4, 0.7, 0.4,
            0.4, 0.9, 0.1, 0.4, 0.1, 0.2
        };
        const auto cMajorResult = AudioKeyDetector::estimate(cMajor);
        assert(cMajorResult.valid);
        assert(cMajorResult.keyScale.rootPitchClass() == 0);
        assert(cMajorResult.keyScale.scale() == mozart::musical::Scale::Major);

        KeyContext context(manualFallback, 0.10, 3);
        const auto manual = context.snapshot();
        assert(manual.source == KeyContextSource::Manual);
        assert(manual.resolvedKeyScale.rootPitchClass() == 6);
        assert(manual.resolvedKeyScale.scale() == mozart::musical::Scale::NaturalMinor);

        context.setSource(KeyContextSource::Audio);
        auto audioPending = context.snapshot();
        assert(audioPending.source == KeyContextSource::Audio);
        assert(!audioPending.audio.hasStableKey);
        assert(audioPending.resolvedKeyScale.rootPitchClass() == 6);
        assert(audioPending.resolvedKeyScale.scale() == mozart::musical::Scale::NaturalMinor);

        context.updateAudioDetection(cMajorResult);
        context.updateAudioDetection(cMajorResult);
        assert(context.snapshot().resolvedKeyScale.rootPitchClass() == 6);
        context.updateAudioDetection(cMajorResult);
        const auto audioStable = context.snapshot();
        assert(audioStable.audio.hasStableKey);
        assert(audioStable.resolvedKeyScale.rootPitchClass() == 0);
        assert(audioStable.resolvedKeyScale.scale() == mozart::musical::Scale::Major);

        context.setManualKeyScale(manualFallback);
        assert(context.source() == KeyContextSource::Audio);
        assert(context.resolvedKeyScale().rootPitchClass() == 0);

        // Direct manual selection is the performer override in the runtime;
        // the domain object itself keeps source selection explicit.
        context.setSource(KeyContextSource::Manual);
        assert(context.resolvedKeyScale().rootPitchClass() == 6);
        assert(context.resolvedKeyScale().scale() == mozart::musical::Scale::NaturalMinor);

        context.setSource(KeyContextSource::Audio);
        context.resetAudio();
        const auto reset = context.snapshot();
        assert(reset.source == KeyContextSource::Audio);
        assert(!reset.audio.hasStableKey);
        assert(reset.resolvedKeyScale.rootPitchClass() == 6);
        assert(reset.resolvedKeyScale.scale() == mozart::musical::Scale::NaturalMinor);
    }

    {
        class FakeTokenBackend final : public mozart::generation::TokenInferenceBackend {
        public:
            mozart::generation::TokenInferenceResult result;

            mozart::generation::TokenInferenceResult generateTokens(
                    const mozart::generation::GenerationRequest&,
                    const std::size_t maxTokens) override {
                if (result.tokens.size() > maxTokens) {
                    return {
                            mozart::generation::TokenInferenceStatus::Failed,
                            {},
                            0.0,
                            0,
                            "fake backend token budget exceeded"
                    };
                }
                return result;
            }

            bool isAvailable() const noexcept override {
                return available;
            }

            std::string id() const override {
                return "fake-test-backend";
            }

            bool available = true;
        };

        mozart::generation::GenerationRequest request;
        request.bars = 1;
        request.density = 1.0;
        request.keyScale = mozart::musical::KeyScale{
                0, mozart::musical::Scale::Major};
        request.minNote = 48;
        request.maxNote = 72;

        mozart::generation::PatternProposal source;
        source.noteEvents.push_back(
                mozart::musical::MusicalNoteEvent{0.0, 0.5, 60, 100, 0});

        const auto encoded = mozart::generation::MidiEventTokenizer::encode(source);
        assert(encoded.has_value());

        FakeTokenBackend backend;
        backend.result = {
                mozart::generation::TokenInferenceStatus::Ok,
                *encoded,
                0.75,
                12,
                "ok"
        };

        mozart::generation::LocalNeuralPatternProvider provider(backend);
        const auto generated = provider.generate(request);
        assert(generated.status == mozart::generation::GenerationStatus::Ok);
        assert(generated.ok());
        assert(generated.proposal.metadata.generatorId == "fake-test-backend");
        assert(generated.proposal.metadata.seed == request.seed);
        assert(std::abs(generated.proposal.metadata.confidence - 0.75) < 1.0e-12);
        assert(generated.proposal.metadata.generationTimeMs == 12);
        assert(generated.proposal.noteEvents.size() == 1);
        assert(generated.proposal.noteEvents[0].note == 60);

        backend.available = false;
        const auto unavailable = provider.generate(request);
        assert(unavailable.status == mozart::generation::GenerationStatus::Unavailable);
        assert(!unavailable.ok());

        backend.available = true;
        backend.result = {
                mozart::generation::TokenInferenceStatus::Ok,
                {
                        mozart::generation::midi_event_vocabulary::kBos,
                        mozart::generation::midi_event_vocabulary::channelToken(0),
                        mozart::generation::midi_event_vocabulary::noteToken(60),
                        mozart::generation::midi_event_vocabulary::velocityToken(10),
                        mozart::generation::midi_event_vocabulary::kEos
                },
                0.5,
                1,
                "malformed"
        };
        const auto malformed = provider.generate(request);
        assert(malformed.status == mozart::generation::GenerationStatus::Failed);
        assert(!malformed.ok());

        backend.result = {
                mozart::generation::TokenInferenceStatus::Ok,
                *encoded,
                1.25,
                1,
                "invalid confidence"
        };
        const auto invalidConfidence = provider.generate(request);
        assert(invalidConfidence.status == mozart::generation::GenerationStatus::Failed);
        assert(!invalidConfidence.ok());

        backend.result = {
                mozart::generation::TokenInferenceStatus::Failed,
                {},
                0.0,
                0,
                "inference failed"
        };
        const auto failed = provider.generate(request);
        assert(failed.status == mozart::generation::GenerationStatus::Failed);
        assert(!failed.ok());
    }

#ifdef MOZART_ENABLE_LINK
    {
        class ControllerRuntimeOutput final
                : public mozart::midi::MidiOutputTransport {
        public:
            mozart::midi::MidiSendResult send(
                    const mozart::midi::MidiShortMessage& message) noexcept override {
                last = message;
                return {
                    mozart::midi::MidiTransportStatus::Ok,
                    message.size
                };
            }

            void close() noexcept override {}

            mozart::midi::MidiShortMessage last{};
        };

        ControllerRuntimeOutput output;
        mozart::runtime::MozartRuntime runtime(output);

        runtime.handleMidiController(
                mozart::midi::controlChange(0, 20, 127).value());
        assert(runtime.performanceScene() == 3);

        runtime.handleMidiController(
                mozart::midi::controlChange(0, 21, 0).value());
        assert(
                runtime.patternDensity() ==
                mozart::generation::PatternDensity::Sparse);

        runtime.handleMidiController(
                mozart::midi::controlChange(0, 22, 127).value());
        assert(
                runtime.patternAccent() ==
                mozart::generation::PatternAccent::Strong);

        runtime.handleMidiController(
                mozart::midi::controlChange(0, 23, 0).value());
        assert(
                runtime.patternSwing() ==
                mozart::generation::PatternSwing::Off);

        runtime.handleMidiController(
                mozart::midi::controlChange(0, 24, 127).value());
        assert(
                runtime.noteRepeat() ==
                mozart::generation::NoteRepeatRate::Quadruple);

        runtime.handleMidiController(
                mozart::midi::controlChange(0, 26, 127).value());
        assert(runtime.macroEnergy() == 127);
        assert(runtime.patternDensity() == mozart::generation::PatternDensity::Full);
        assert(runtime.patternAccent() == mozart::generation::PatternAccent::Strong);

        runtime.handleMidiController(
                mozart::midi::controlChange(0, 27, 127).value());
        assert(runtime.macroMotion() == 127);
        assert(runtime.patternSwing() == mozart::generation::PatternSwing::Full);
        assert(runtime.noteRepeat() == mozart::generation::NoteRepeatRate::Quadruple);

        runtime.handleMidiController(
                mozart::midi::noteOn(0, 20, 100).value());
        assert(
                runtime.performanceScene() ==
                mozart::scheduler::PerformanceScene::kCustomScene);
    }

    {
        class RecordingMidiOutput final : public mozart::midi::MidiOutputTransport {
        public:
            mozart::midi::MidiSendResult send(
                    const mozart::midi::MidiShortMessage& message) noexcept override {
                {
                    std::lock_guard<std::mutex> lock(mutex);
                    messages.push_back(message);
                }
                condition.notify_all();
                return {
                    mozart::midi::MidiTransportStatus::Ok,
                    message.size
                };
            }

            void close() noexcept override {}

            bool waitForCount(const std::size_t expected) {
                std::unique_lock<std::mutex> lock(mutex);
                return condition.wait_for(
                        lock,
                        std::chrono::milliseconds(500),
                        [&] { return messages.size() >= expected; });
            }

            std::size_t count() const {
                std::lock_guard<std::mutex> lock(mutex);
                return messages.size();
            }

            mozart::midi::MidiShortMessage messageAt(const std::size_t index) const {
                std::lock_guard<std::mutex> lock(mutex);
                return messages.at(index);
            }

            std::vector<mozart::midi::MidiShortMessage> messagesCopy() const {
                std::lock_guard<std::mutex> lock(mutex);
                return messages;
            }

        private:
            mutable std::mutex mutex;
            std::condition_variable condition;
            std::vector<mozart::midi::MidiShortMessage> messages;
        };

        RecordingMidiOutput output;
        mozart::runtime::MozartRuntime runtime(output);
        runtime.start();

        // This mirrors the Android STOP path: accompaniment is stopped first,
        // then Link is disabled. Only one MIDI panic pair must be emitted.
        runtime.setAccompanimentEnabled(false);
        assert(output.waitForCount(2));
        assert(output.count() == 2);

        const auto allNotesOff = output.messageAt(0);
        const auto allSoundOff = output.messageAt(1);
        assert(allNotesOff.status == 0xB0);
        assert(allNotesOff.data1 == 123);
        assert(allNotesOff.data2 == 0);
        assert(allSoundOff.status == 0xB0);
        assert(allSoundOff.data1 == 120);
        assert(allSoundOff.data2 == 0);

        runtime.setLinkEnabled(false);
        assert(output.count() == 2);
    }

    {
        class CountingMidiOutput final : public mozart::midi::MidiOutputTransport {
        public:
            mozart::midi::MidiSendResult send(
                    const mozart::midi::MidiShortMessage& message) noexcept override {
                {
                    std::lock_guard<std::mutex> lock(mutex);
                    messages.push_back(message);
                }
                last = message;
                ++sendCount;
                condition.notify_all();
                return {
                    mozart::midi::MidiTransportStatus::Ok,
                    message.size
                };
            }

            void close() noexcept override {}

            std::vector<mozart::midi::MidiShortMessage> messagesCopy() const {
                std::lock_guard<std::mutex> lock(mutex);
                return messages;
            }

            mozart::midi::MidiShortMessage last{};
            std::atomic<std::size_t> sendCount{0};

        private:
            mutable std::mutex mutex;
            std::condition_variable condition;
            std::vector<mozart::midi::MidiShortMessage> messages;
        };

        CountingMidiOutput output;
        mozart::clock::LinkClock clock(120.0, 4.0);
        mozart::scheduler::MidiSendQueue queue(output);
        mozart::scheduler::AccompanimentScheduler scheduler(clock, queue);

        assert(
                scheduler.role() ==
                mozart::scheduler::AccompanimentRole::Bass);
        scheduler.setRole(
                mozart::scheduler::AccompanimentRole::Arpeggio);
        assert(
                scheduler.role() ==
                mozart::scheduler::AccompanimentRole::Arpeggio);
        scheduler.setRole(
                mozart::scheduler::AccompanimentRole::Bass);
        assert(
                scheduler.role() ==
                mozart::scheduler::AccompanimentRole::Bass);
        assert(
                scheduler.density() ==
                mozart::generation::PatternDensity::Full);
        scheduler.setDensity(
                mozart::generation::PatternDensity::Sparse);
        assert(
                scheduler.density() ==
                mozart::generation::PatternDensity::Sparse);
        scheduler.setDensity(
                mozart::generation::PatternDensity::Full);
        assert(
                scheduler.density() ==
                mozart::generation::PatternDensity::Full);
        assert(
                scheduler.accent() ==
                mozart::generation::PatternAccent::Off);
        scheduler.setAccent(
                mozart::generation::PatternAccent::Strong);
        assert(
                scheduler.accent() ==
                mozart::generation::PatternAccent::Strong);
        scheduler.setAccent(
                mozart::generation::PatternAccent::Off);
        assert(
                scheduler.swing() ==
                mozart::generation::PatternSwing::Off);
        scheduler.setSwing(
                mozart::generation::PatternSwing::Full);
        assert(
                scheduler.swing() ==
                mozart::generation::PatternSwing::Full);
        scheduler.setSwing(
                mozart::generation::PatternSwing::Off);

        clock.setEnabled(true);
        const auto beforeArm = clock.captureAppSnapshot();
        const auto expectedLaunchBeat =
                mozart::timing::nextQuantizedBeat(
                        beforeArm.beat,
                        beforeArm.quantum);
        const auto expectedLaunchHostTime =
                clock.hostTimeAtBeat(expectedLaunchBeat);

        queue.start();
        scheduler.start();
        scheduler.setArmed(true);

        bool generated = false;
        for (int attempt = 0; attempt < 800; ++attempt) {
            if (output.sendCount.load() > 0) {
                generated = true;
                break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }

        scheduler.setArmed(false);
        scheduler.stop();
        queue.stop();

        assert(generated);
        assert(output.last.size == 3);

        const auto messages = output.messagesCopy();
        assert(!messages.empty());
        for (const auto& message : messages) {
            assert(message.timestampNanos >=
                    static_cast<std::uint64_t>(
                            expectedLaunchHostTime.count()) * 1000ULL);
        }

        std::vector<std::uint64_t> noteOnTimestamps;
        for (const auto& message : messages) {
            if ((message.status & 0xF0) == 0x90 && message.data2 > 0) {
                noteOnTimestamps.push_back(message.timestampNanos);
            }
        }

        // The rolling scheduler should expose consecutive eighth-note bass
        // events instead of scheduling one whole bar and waiting for the next
        // bar boundary. At 120 BPM, the generated pattern is 250 ms apart.
        assert(noteOnTimestamps.size() >= 5);
        for (std::size_t i = 1; i < 5; ++i) {
            const auto deltaNanos =
                    noteOnTimestamps[i] - noteOnTimestamps[i - 1];
            assert(deltaNanos >= 120'000'000ULL);
            assert(deltaNanos <= 380'000'000ULL);
        }
    }

    {
        mozart::clock::LinkClock clock(120.0, 4.0);
        assert(!clock.isEnabled());
        assert(!clock.isStartStopSyncEnabled());

        const auto snapshot = clock.captureAppSnapshot();
        assert(!snapshot.enabled);
        assert(!snapshot.playing);
        assert(!snapshot.inSession);
        assert(!snapshot.startStopSyncEnabled);
        assert(snapshot.peers == 0);
        assert(std::abs(snapshot.tempoBpm - 120.0) < 1.0e-9);
        assert(std::abs(snapshot.quantum - 4.0) < 1.0e-12);
        assert(snapshot.phase >= 0.0);
        assert(snapshot.phase < snapshot.quantum);

        const auto targetBeat = 8.5;
        const auto targetTime = clock.hostTimeAtBeat(targetBeat);
        const auto roundTripBeat = clock.beatAtHostTime(targetTime);
        assert(std::abs(roundTripBeat - targetBeat) < 1.0e-9);

        clock.setEnabled(true);
        assert(clock.isEnabled());
        assert(!clock.isStartStopSyncEnabled());

        const auto enabledSnapshot = clock.captureAppSnapshot();
        assert(enabledSnapshot.enabled);
        assert(!enabledSnapshot.startStopSyncEnabled);
        assert(enabledSnapshot.peers == 0);
        assert(!enabledSnapshot.inSession);
        assert(std::abs(enabledSnapshot.tempoBpm - 120.0) < 1.0e-9);
        assert(std::abs(enabledSnapshot.quantum - 4.0) < 1.0e-12);
        assert(enabledSnapshot.phase >= 0.0);
        assert(enabledSnapshot.phase < enabledSnapshot.quantum);

        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        const auto advancedSnapshot = clock.captureAppSnapshot();
        assert(advancedSnapshot.enabled);
        assert(advancedSnapshot.beat > enabledSnapshot.beat + 0.05);
        assert(advancedSnapshot.phase >= 0.0);
        assert(advancedSnapshot.phase < advancedSnapshot.quantum);

        clock.setEnabled(false);
        assert(!clock.isEnabled());
        const auto disabledAgain = clock.captureAppSnapshot();
        assert(!disabledAgain.enabled);
        assert(!disabledAgain.startStopSyncEnabled);
    }
#endif

    return 0;
}