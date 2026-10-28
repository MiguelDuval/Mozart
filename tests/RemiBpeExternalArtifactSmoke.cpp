#include "remi/BpeTokenizer.h"
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
        {"eos_token_id", *eosId}
    };
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
