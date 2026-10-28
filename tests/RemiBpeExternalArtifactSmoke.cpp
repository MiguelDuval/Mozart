#include "remi/BpeTokenizer.h"
#include "remi/RemiDecoderConfig.h"
#include "remi/RemiEventAdapter.h"
#include "generation/RemiToLinkPatternConverter.h"
#include "generation/RemiBpePatternProvider.h"
#include "json.hpp"

#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace {
using json = nlohmann::json;

bool fail(const std::string& message) {
    std::cerr << "ERROR: " << message << '\n';
    return false;
}

std::optional<std::uint32_t> configId(
        const json& config, const char* canonicalKey, const char* alternateKey = nullptr) {
    const json* value = nullptr;
    if (config.contains(canonicalKey) && !config[canonicalKey].is_null()) {
        value = &config[canonicalKey];
    } else if (alternateKey && config.contains(alternateKey) && !config[alternateKey].is_null()) {
        value = &config[alternateKey];
    }
    if (!value || !value->is_number_integer()) return std::nullopt;
    const auto raw = value->get<std::int64_t>();
    if (raw < 0 || static_cast<std::uint64_t>(raw) > std::numeric_limits<std::uint32_t>::max())
        return std::nullopt;
    return static_cast<std::uint32_t>(raw);
}

bool assertSpecial(
        const char* label,
        const std::optional<std::uint32_t> actual,
        const std::optional<std::uint32_t> expected) {
    if (!actual || !expected) {
        fail(std::string("missing or unresolvable ") + label + " ID");
        return false;
    }
    if (*actual != *expected) {
        fail(std::string(label) + " ID mismatch: tokenizer=" +
            std::to_string(*actual) + " model_config=" + std::to_string(*expected));
        return false;
    }
    return true;
}

class RealTokenReplayBackend final : public mozart::generation::RemiBpeInferenceBackend {
public:
    RealTokenReplayBackend(
            std::string tokenizerPath,
            std::size_t vocabularySize,
            std::vector<std::uint32_t> tokenIds,
            std::uint32_t eosTokenId)
        : tokenizerPath_(std::move(tokenizerPath)),
          vocabularySize_(vocabularySize),
          tokenIds_(std::move(tokenIds)),
          eosTokenId_(eosTokenId) {}

    mozart::generation::RemiBpeTokenInferenceResult generateRemiTokens(
            const mozart::generation::GenerationRequest&,
            const std::size_t) override {
        ++inferenceCalls_;
        // Mirror OnnxInferenceBridge.generateRemiBpe: it returns FAILED (not
        // OK with a partial sequence) when the greedy token cap is reached
        // without EOS. Keep the IDs for diagnostics, but the provider must not
        // turn a failed inference result into a partial proposal.
        if (tokenIds_.empty() || tokenIds_.back() != eosTokenId_) {
            return {
                mozart::generation::TokenInferenceStatus::Failed,
                tokenIds_,
                0.0,
                1,
                "REMI/BPE generation reached token limit without EOS"
            };
        }
        return {
            mozart::generation::TokenInferenceStatus::Ok,
            tokenIds_,
            0.75,
            1,
            {}
        };
    }

    bool isAvailable() const noexcept override {
        return true;
    }

    std::string id() const override {
        return "real-checkpoint-replay";
    }

    std::string tokenizerArtifactPath() const override {
        return tokenizerPath_;
    }

    std::size_t expectedVocabularySize() const noexcept override {
        return vocabularySize_;
    }

    std::size_t inferenceCalls() const noexcept {
        return inferenceCalls_;
    }

private:
    std::string tokenizerPath_;
    std::size_t vocabularySize_;
    std::vector<std::uint32_t> tokenIds_;
    std::uint32_t eosTokenId_;
    std::size_t inferenceCalls_ = 0;
};

const char* generationStatusName(const mozart::generation::GenerationStatus status) {
    switch (status) {
        case mozart::generation::GenerationStatus::Ok: return "ok";
        case mozart::generation::GenerationStatus::InvalidRequest: return "invalid_request";
        case mozart::generation::GenerationStatus::Unavailable: return "unavailable";
        case mozart::generation::GenerationStatus::Failed: return "failed";
    }
    return "unknown";
}
} // namespace

int main(int argc, char** argv) {
    if (argc != 5) {
        std::cerr << "Usage: remi_bpe_external_artifact_smoke tokenizer.json config.json generated_token_ids.json report.json\n";
        return 2;
    }

    const auto tokenizer = mozart::remi::BpeTokenizer::loadFromJson(argv[1]);
    if (!tokenizer || tokenizer->empty()) {
        fail("C++ BPE tokenizer failed to load");
        return 1;
    }
    if (!tokenizer->hasLearnedBpeVocabulary()) {
        fail("artifact contains only a base vocabulary");
        return 1;
    }

    json modelConfig;
    json generatedIds;
    try {
        std::ifstream configInput(argv[2]);
        if (!configInput.is_open()) {
            fail("could not open model config");
            return 1;
        }
        configInput >> modelConfig;
        std::ifstream tokenInput(argv[3]);
        if (!tokenInput.is_open()) {
            fail("could not open generated token ID file");
            return 1;
        }
        tokenInput >> generatedIds;
    } catch (const std::exception& error) {
        fail(std::string("could not parse artifact input: ") + error.what());
        return 1;
    }

    if (!modelConfig.is_object() || !modelConfig.contains("vocab_size") ||
        !modelConfig["vocab_size"].is_number_integer()) {
        fail("config.json has no integer vocab_size");
        return 1;
    }
    const auto rawVocabSize = modelConfig["vocab_size"].get<std::int64_t>();
    if (rawVocabSize <= 0 || static_cast<std::uint64_t>(rawVocabSize) != tokenizer->vocabSize()) {
        fail("C++ learned BPE vocabulary size does not match model config");
        return 1;
    }

    const auto padId = tokenizer->padToken();
    const auto bosId = tokenizer->bosToken();
    const auto eosId = tokenizer->eosToken();
    if (!assertSpecial("PAD", padId, configId(modelConfig, "pad_token_id", "pad")) ||
        !assertSpecial("BOS", bosId, configId(modelConfig, "bos_token_id")) ||
        !assertSpecial("EOS", eosId, configId(modelConfig, "eos_token_id"))) {
        return 1;
    }
    if (!generatedIds.is_array() || generatedIds.empty()) {
        fail("generated IDs must be a non-empty array");
        return 1;
    }

    std::vector<std::uint32_t> tokenIds;
    tokenIds.reserve(generatedIds.size());
    for (const auto& item : generatedIds) {
        if (!item.is_number_integer()) {
            fail("generated token IDs must be integers");
            return 1;
        }
        const auto raw = item.get<std::int64_t>();
        if (raw < 0 || static_cast<std::uint64_t>(raw) >= tokenizer->vocabSize()) {
            fail("generated token ID is outside the learned BPE vocabulary");
            return 1;
        }
        tokenIds.push_back(static_cast<std::uint32_t>(raw));
    }

    std::size_t individuallyDecodable = 0;
    for (std::size_t id = 0; id < tokenizer->vocabSize(); ++id) {
        if (tokenizer->decodeTokenToNames(static_cast<std::uint32_t>(id))) {
            ++individuallyDecodable;
        }
    }
    if (individuallyDecodable != tokenizer->vocabSize()) {
        fail("C++ tokenizer cannot independently decode every learned BPE vocabulary entry");
        return 1;
    }
    const auto decoded = tokenizer->decodeTokensWithReport(tokenIds);
    if (decoded.droppedTokenIds != 0) {
        fail("C++ tokenizer dropped " + std::to_string(decoded.droppedTokenIds) +
            " token(s) from actual ONNX-generated IDs");
        return 1;
    }
    if (decoded.tokenNames.empty()) {
        fail("actual ONNX-generated IDs decoded to no REMI semantic tokens");
        return 1;
    }

    const bool completeBosEosStream =
            !tokenIds.empty() && tokenIds.front() == *bosId && tokenIds.back() == *eosId;

    bool noMisplacedSpecialTokens = true;
    for (std::size_t i = 1; i + 1 < tokenIds.size(); ++i) {
        if (tokenIds[i] == *bosId || tokenIds[i] == *eosId ||
            tokenIds[i] == *padId ||
            (tokenizer->maskToken().has_value() && tokenIds[i] == *tokenizer->maskToken())) {
            noMisplacedSpecialTokens = false;
            break;
        }
    }

    json report = {
        {"status", "verified"},
        {"vocabulary_size", tokenizer->vocabSize()},
        {"generated_token_count_including_bos", tokenIds.size()},
        {"decoded_semantic_name_count", decoded.tokenNames.size()},
        {"dropped_token_ids", decoded.droppedTokenIds},
        {"independently_decodable_vocab_entries", individuallyDecodable},
        {"all_vocab_entries_decodable", individuallyDecodable == tokenizer->vocabSize()},
        {"pad_token_id", *padId},
        {"bos_token_id", *bosId},
        {"eos_token_id", *eosId},
        {"complete_bos_eos_stream", completeBosEosStream},
        {"no_misplaced_special_tokens", noMisplacedSpecialTokens},
        {"provider_ready", false},
        {"production_provider_initialized", false},
        {"production_provider_status", "not_run"},
        {"production_provider_message", ""},
        {"production_provider_ready", false},
        {"production_provider_note_count", 0},
        {"production_provider_control_count", 0},
        {"production_provider_inference_calls", 0},
        {"semantic_adapter_status", "not_run"},
        {"semantic_adapter_message", ""},
        {"semantic_proposal_valid", false},
        {"semantic_note_count", 0},
        {"semantic_program_change_count", 0},
        {"semantic_control_change_count", 0},
        {"request_validation_status", "not_run"},
        {"request_validation_message", ""},
        {"semantic_input_token_count", 0},
        {"semantic_diagnostic_prefix_used", false},
        {"semantic_tokens_omitted_for_diagnostic", 0},
        {"link_conversion_status", "not_run"},
        {"link_note_count", 0},
        {"link_control_count", 0}
    };

    // Exercise the production REMI/BPE provider with the exact unmodified
    // ONNX output. The replay backend replaces only the model inference call;
    // tokenizer loading, BOS/EOS gates, strict decoding, conversion and shared
    // request validation are the production implementation under test.
    try {
        RealTokenReplayBackend replayBackend(argv[1], tokenizer->vocabSize(), tokenIds, *eosId);
        mozart::generation::RemiBpePatternProvider productionProvider(replayBackend);
        report["production_provider_initialized"] = productionProvider.tokenizerReady();
        report["production_provider_inference_calls"] = 0;
        if (!productionProvider.tokenizerReady()) {
            report["production_provider_status"] = "initialization_failed";
            report["production_provider_message"] = productionProvider.initializationError();
        } else {
            mozart::generation::GenerationRequest productionRequest;
            productionRequest.bars = 16;
            const auto productionResult = productionProvider.generate(productionRequest);
            report["production_provider_status"] = generationStatusName(productionResult.status);
            report["production_provider_message"] = productionResult.message;
            report["production_provider_ready"] = productionResult.ok();
            report["production_provider_note_count"] = productionResult.proposal.noteEvents.size();
            report["production_provider_control_count"] = productionResult.proposal.controlEvents.size();
            report["production_provider_inference_calls"] = replayBackend.inferenceCalls();
        }
    } catch (const std::exception& error) {
        report["production_provider_status"] = "exception";
        report["production_provider_message"] = error.what();
    }

    // First test the complete generated stream without repairing it. If a bounded
    // diagnostic generation ends mid-note and has no EOS, try shorter prefixes
    // solely to establish whether a complete event boundary can flow through the
    // typed adapter and Link converter. The report always marks truncation and
    // never promotes a prefix-only result to provider_ready.
    try {
        const auto config = mozart::remi::RemiDecoderConfig::fromTokenizerJson(argv[1]);
        const auto adapterTokenizer = std::make_shared<mozart::remi::BpeTokenizer>(*tokenizer);
        mozart::remi::RemiEventAdapter adapter(config, adapterTokenizer);
        mozart::remi::GenerationRequest request;
        request.seed = 20261028U;
        const mozart::generation::RemiToLinkPatternConverter converter(config.ticksPerBeat);

        auto inspectCandidate = [&](const std::vector<std::uint32_t>& candidate,
                                    const bool diagnosticPrefix) -> bool {
            auto [proposal, decodeReport] = adapter.decodeTokensToProposal(
                    candidate, request, "real-remi-bpe-smoke", "NathanFradet/Maestro-REMI-bpe20k");
            if (!decodeReport.isOk() || !proposal.isValid()) {
                if (!diagnosticPrefix) report["semantic_adapter_message"] = decodeReport.message;
                return false;
            }

            std::size_t noteCount = 0;
            std::size_t programChangeCount = 0;
            std::size_t controlChangeCount = 0;
            for (const auto& event : proposal.events) {
                if (std::holds_alternative<mozart::remi::NoteEvent>(event)) ++noteCount;
                if (std::holds_alternative<mozart::remi::ProgramChangeEvent>(event)) ++programChangeCount;
                if (std::holds_alternative<mozart::remi::ControlChangeEvent>(event)) ++controlChangeCount;
            }
            report["semantic_adapter_status"] = diagnosticPrefix
                    ? "valid_diagnostic_prefix" : "valid_proposal";
            report["semantic_adapter_message"] = diagnosticPrefix
                    ? "Only a shorter complete-event prefix is valid; the complete generated stream remains unaccepted"
                    : "";
            report["semantic_proposal_valid"] = true;
            report["semantic_note_count"] = noteCount;
            report["semantic_program_change_count"] = programChangeCount;
            report["semantic_control_change_count"] = controlChangeCount;
            report["semantic_input_token_count"] = candidate.size();
            report["semantic_diagnostic_prefix_used"] = diagnosticPrefix;
            report["semantic_tokens_omitted_for_diagnostic"] = tokenIds.size() - candidate.size();

            const auto linkProposal = converter.convert(proposal);
            bool linkStageAccepted = false;
            if (linkProposal.has_value() && linkProposal->isWellFormed()) {
                report["link_conversion_status"] = "accepted";
                report["link_note_count"] = linkProposal->noteEvents.size();
                report["link_control_count"] = linkProposal->controlEvents.size();
                mozart::generation::GenerationRequest linkRequest;
                const auto requestValidation =
                        mozart::generation::PatternProposalValidator::validate(
                                linkRequest, *linkProposal);
                report["request_validation_status"] = requestValidation.ok()
                        ? "accepted" : "rejected";
                report["request_validation_message"] = requestValidation.message;
                linkStageAccepted =
                        programChangeCount == 0 &&
                        controlChangeCount == 0 &&
                        linkProposal->controlEvents.empty() &&
                        requestValidation.ok();
                report["provider_ready"] =
                        completeBosEosStream &&
                        noMisplacedSpecialTokens &&
                        !diagnosticPrefix &&
                        candidate.size() == tokenIds.size() &&
                        linkStageAccepted;
            } else if (programChangeCount != 0) {
                report["link_conversion_status"] = "rejected_unsupported_program_change";
            } else {
                report["link_conversion_status"] = "rejected_by_link_converter";
            }
            // The diagnostic prefix scan must continue until it finds a prefix
            // accepted by the same adapter -> Link -> request-validator chain.
            return linkStageAccepted;
        };

        if (!inspectCandidate(tokenIds, false) && !completeBosEosStream) {
            // Diagnostic-only scan: keep BOS, do not fabricate EOS, and leave
            // the provider-ready state false for any shortened prefix.
            for (std::size_t length = tokenIds.size(); length > 2; --length) {
                std::vector<std::uint32_t> prefix(tokenIds.begin(), tokenIds.begin() + length - 1);
                if (inspectCandidate(prefix, true)) break;
            }
        }
    } catch (const std::exception& error) {
        report["semantic_adapter_status"] = "exception";
        report["semantic_adapter_message"] = error.what();
    }
    std::ofstream reportOutput(argv[4]);
    if (!reportOutput.is_open()) {
        fail("could not open C++ tokenizer verification report for writing");
        return 1;
    }
    reportOutput << report.dump(2) << '\n';
    if (!reportOutput.good()) {
        fail("could not write C++ tokenizer verification report");
        return 1;
    }

    std::cout << "PASS: real REMI/BPE tokenizer loaded by Mozart C++"
              << " vocab=" << tokenizer->vocabSize()
              << " generated_ids=" << tokenIds.size()
              << " decoded_names=" << decoded.tokenNames.size()
              << " dropped_ids=" << decoded.droppedTokenIds
              << " independently_decodable_vocab_entries=" << individuallyDecodable
              << '\n';
    return 0;
}
