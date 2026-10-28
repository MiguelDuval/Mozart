#include "generation/RemiBpePatternProvider.h"
#include "generation/PatternProposal.h"
#include "generation/RemiToLinkPatternConverter.h"
#include "remi/RemiEventAdapter.h"
#include <cmath>
#include <exception>
#include <utility>
#include <variant>

namespace mozart::generation {
RemiBpePatternProvider::RemiBpePatternProvider(RemiBpeInferenceBackend& backend)
    : backend_(backend) {
    try {
        const auto path = backend_.tokenizerArtifactPath();
        if (path.empty()) {
            initializationError_ = "REMI/BPE tokenizer artifact path is empty";
            return;
        }
        auto tokenizer = remi::BpeTokenizer::loadFromJson(path);
        if (!tokenizer.has_value() || tokenizer->empty()) {
            initializationError_ = "REMI/BPE tokenizer artifact could not be loaded";
            return;
        }
        if (!tokenizer->hasLearnedBpeVocabulary()) {
            initializationError_ =
                "REMI/BPE tokenizer has only the MidiTok base vocabulary; learned BPE model vocabulary is missing";
            return;
        }
        const auto expectedVocabularySize = backend_.expectedVocabularySize();
        if (expectedVocabularySize == 0) {
            initializationError_ =
                "REMI/BPE model manifest does not declare a valid output vocabulary size";
            return;
        }
        if (tokenizer->vocabSize() != expectedVocabularySize) {
            initializationError_ =
                "REMI/BPE model output vocabulary size does not match its paired tokenizer";
            return;
        }
        auto config = remi::RemiDecoderConfig::fromTokenizerJson(path);
        if (config.vocabSize != tokenizer->vocabSize()) {
            initializationError_ = "REMI/BPE tokenizer vocabulary size disagrees with loaded token IDs";
            return;
        }
        if (!config.bosToken.has_value() || !config.eosToken.has_value() ||
            !config.padToken.has_value()) {
            initializationError_ = "REMI/BPE tokenizer must define resolvable PAD, BOS and EOS IDs";
            return;
        }
        config_ = std::move(config);
        tokenizer_ = std::make_shared<remi::BpeTokenizer>(std::move(*tokenizer));
    } catch (const std::exception& error) {
        initializationError_ = std::string("REMI/BPE tokenizer initialization failed: ") + error.what();
    } catch (...) {
        initializationError_ = "REMI/BPE tokenizer initialization failed";
    }
}

GenerationResult RemiBpePatternProvider::failed(
        const GenerationStatus status, std::string message) const {
    return {status, {}, std::move(message)};
}

GenerationResult RemiBpePatternProvider::generate(const GenerationRequest& request) {
    if (!request.isValid()) {
        return failed(GenerationStatus::InvalidRequest, "invalid generation request");
    }
    if (!tokenizerReady()) {
        return failed(GenerationStatus::Failed, initializationError_);
    }
    // Runtime/backend availability is intentionally queried on this worker.
    if (!backend_.isAvailable()) {
        return failed(GenerationStatus::Unavailable, "REMI/BPE inference backend is unavailable");
    }

    auto inference = backend_.generateRemiTokens(request, kMaxGeneratedTokens);
    if (inference.status == TokenInferenceStatus::Unavailable) {
        return failed(GenerationStatus::Unavailable,
            inference.message.empty() ? "REMI/BPE inference backend is unavailable" : std::move(inference.message));
    }
    if (!inference.ok()) {
        return failed(GenerationStatus::Failed,
            inference.message.empty() ? "REMI/BPE inference failed" : std::move(inference.message));
    }
    if (!std::isfinite(inference.confidence) ||
        inference.confidence < 0.0 || inference.confidence > 1.0) {
        return failed(GenerationStatus::Failed, "REMI/BPE inference returned invalid confidence");
    }
    if (inference.tokenIds.size() < 2 ||
        inference.tokenIds.size() > kMaxGeneratedTokens) {
        return failed(GenerationStatus::Failed, "REMI/BPE token stream length is outside supported bounds");
    }

    const auto bos = *config_->bosToken;
    const auto eos = *config_->eosToken;
    const auto pad = *config_->padToken;
    if (inference.tokenIds.front() != bos || inference.tokenIds.back() != eos) {
        return failed(GenerationStatus::Failed, "REMI/BPE token stream must be BOS/EOS terminated");
    }
    for (std::size_t i = 1; i + 1 < inference.tokenIds.size(); ++i) {
        if (inference.tokenIds[i] == bos || inference.tokenIds[i] == eos ||
            inference.tokenIds[i] == pad ||
            (config_->maskToken.has_value() && inference.tokenIds[i] == *config_->maskToken)) {
            return failed(GenerationStatus::Failed, "REMI/BPE token stream contains a misplaced special token");
        }
    }

    remi::GenerationRequest remiRequest;
    remiRequest.targetBpm = request.tempoBpm;
    remiRequest.barCount = request.bars;
    remiRequest.seed = request.seed;

    remi::RemiEventAdapter adapter(*config_, tokenizer_);
    auto [source, decodeReport] = adapter.decodeTokensToProposal(
        inference.tokenIds, remiRequest, backend_.id(), backend_.id());
    if (!decodeReport.isOk()) {
        return failed(GenerationStatus::Failed,
            decodeReport.message.empty() ? "REMI/BPE token stream failed strict semantic decoding"
                                         : std::move(decodeReport.message));
    }
    if (!source.isValid()) {
        const auto error = source.validationError();
        return failed(GenerationStatus::Failed,
            error.has_value() ? *error : "REMI/BPE source proposal is invalid");
    }

    // The active scheduler is note-only. Refuse controls before they can become
    // a partially scheduled pattern or be silently discarded.
    for (const auto& event : source.events) {
        if (std::holds_alternative<remi::ControlChangeEvent>(event)) {
            return failed(GenerationStatus::Failed,
                "REMI/BPE proposal contains controls unsupported by the note-only scheduler");
        }
    }

    const RemiToLinkPatternConverter converter(config_->ticksPerBeat);
    auto converted = converter.convert(source);
    if (!converted.has_value()) {
        return failed(GenerationStatus::Failed,
            "REMI/BPE proposal could not be converted atomically to Link events");
    }
    if (!converted->controlEvents.empty()) {
        return failed(GenerationStatus::Failed, "Link scheduler currently accepts note events only");
    }

    // Reuse the common request-aware validator: bar length, pitch/key bounds,
    // density, polyphony and duplicate canonicalization are not REMI-specific.
    const auto validation = PatternProposalValidator::validate(request, *converted);
    if (!validation.ok()) {
        return failed(GenerationStatus::Failed,
            validation.message.empty() ? "REMI/BPE proposal failed the shared request validator"
                                       : validation.message);
    }

    auto proposal = validation.proposal;
    proposal.metadata.confidence = inference.confidence;
    proposal.metadata.generationTimeMs = inference.generationTimeMs;
    proposal.metadata.generatorId = backend_.id();
    proposal.metadata.seed = request.seed;
    if (!proposal.isWellFormed()) {
        return failed(GenerationStatus::Failed, "validated REMI/BPE proposal is malformed");
    }
    return {GenerationStatus::Ok, std::move(proposal), {}};
}
} // namespace mozart::generation
