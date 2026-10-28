#include "remi/BpeTokenizer.h"
#include "remi/RemiDecoderConfig.h"
#include "remi/RemiEventAdapter.h"
#include "generation/RemiToLinkPatternConverter.h"
#include "json.hpp"

#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
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
        {"provider_ready", completeBosEosStream},
        {"semantic_adapter_status", "not_run"},
        {"semantic_adapter_message", ""},
        {"semantic_proposal_valid", false},
        {"semantic_note_count", 0},
        {"semantic_program_change_count", 0},
        {"link_conversion_status", "not_run"},
        {"link_note_count", 0},
        {"link_control_count", 0}
    };

    // This diagnostic intentionally does not fabricate EOS or discard unsupported
    // events. It reports whether the actual bounded ONNX prefix can be decoded
    // into Mozart's typed REMI proposal and converted to the Link proposal. The
    // provider_ready flag remains false unless the generated stream has BOS/EOS.
    try {
        const auto config = mozart::remi::RemiDecoderConfig::fromTokenizerJson(argv[1]);
        mozart::remi::RemiEventAdapter adapter(config, tokenizer);
        mozart::remi::GenerationRequest request;
        request.seed = 20261028U;
        auto [proposal, decodeReport] = adapter.decodeTokensToProposal(
                tokenIds, request, "real-remi-bpe-smoke", "NathanFradet/Maestro-REMI-bpe20k");

        report["semantic_adapter_status"] =
                decodeReport.isOk() && proposal.isValid() ? "valid_proposal" : "rejected";
        report["semantic_adapter_message"] = decodeReport.message;
        report["semantic_proposal_valid"] = decodeReport.isOk() && proposal.isValid();

        std::size_t noteCount = 0;
        std::size_t programChangeCount = 0;
        if (decodeReport.isOk() && proposal.isValid()) {
            for (const auto& event : proposal.events) {
                if (std::holds_alternative<mozart::remi::NoteEvent>(event)) ++noteCount;
                if (std::holds_alternative<mozart::remi::ProgramChangeEvent>(event)) ++programChangeCount;
            }
            report["semantic_note_count"] = noteCount;
            report["semantic_program_change_count"] = programChangeCount;

            const mozart::generation::RemiToLinkPatternConverter converter(config.ticksPerBeat);
            const auto linkProposal = converter.convert(proposal);
            if (linkProposal.has_value() && linkProposal->isWellFormed()) {
                report["link_conversion_status"] = "accepted";
                report["link_note_count"] = linkProposal->noteEvents.size();
                report["link_control_count"] = linkProposal->controlEvents.size();
            } else if (programChangeCount != 0) {
                report["link_conversion_status"] = "rejected_unsupported_program_change";
            } else {
                report["link_conversion_status"] = "rejected_by_link_converter";
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
