#include "generation/LocalNeuralPatternProvider.h"

#include "generation/MidiEventDetokenizer.h"

namespace mozart::generation {

GenerationResult LocalNeuralPatternProvider::generate(
        const GenerationRequest& request) {
    constexpr std::size_t kMaxModelTokens = 16384;

    if (!request.isValid()) {
        return {
                GenerationStatus::InvalidRequest,
                {},
                "invalid generation request"
        };
    }

    if (!backend_.isAvailable()) {
        return {
                GenerationStatus::Unavailable,
                {},
                "local inference backend is unavailable"
        };
    }

    const auto inference =
            backend_.generateTokens(request, kMaxModelTokens);

    if (inference.status == TokenInferenceStatus::Unavailable) {
        return {
                GenerationStatus::Unavailable,
                {},
                inference.message.empty()
                        ? "local inference backend is unavailable"
                        : inference.message
        };
    }

    if (!inference.ok()) {
        return {
                GenerationStatus::Failed,
                {},
                inference.message.empty()
                        ? "local inference backend failed"
                        : inference.message
        };
    }

    const auto decoded =
            MidiEventDetokenizer::decode(inference.tokens);
    if (!decoded.has_value()) {
        return {
                GenerationStatus::Failed,
                {},
                "model token stream failed strict detokenization"
        };
    }

    auto proposal = *decoded;
    proposal.metadata.seed = request.seed;
    proposal.metadata.confidence = inference.confidence;
    proposal.metadata.generationTimeMs = inference.generationTimeMs;
    proposal.metadata.generatorId = backend_.id();

    const auto validation =
            PatternProposalValidator::validate(request, proposal);
    if (!validation.ok()) {
        return {
                GenerationStatus::Failed,
                {},
                validation.message.empty()
                        ? "model proposal failed validation"
                        : validation.message
        };
    }

    return {
            GenerationStatus::Ok,
            validation.proposal,
            {}
    };
}

} // namespace mozart::generation
