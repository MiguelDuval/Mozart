#include "RemiEventAdapter.h"
#include "GenerationTypes.h"

#include <fstream>
#include <sstream>
#include <algorithm>
#include <cctype>
#include <stdexcept>
#include "json.hpp"

namespace mozart::generation {

//----------------------------------------------------------------------
// BpeTokenizer Implementation
//----------------------------------------------------------------------

std::optional<BpeTokenizer> BpeTokenizer::loadFromJson(const std::string& jsonPath) {
    try {
        std::ifstream file(jsonPath);
        if (!file.is_open()) {
            return std::nullopt;
        }
        
        nlohmann::json data = nlohmann::json::parse(file);
        
        BpeTokenizer tokenizer;
        
        // Parse _vocab_base_byte_to_token: maps byte (as string) to token name
        if (data.contains("_vocab_base_byte_to_token")) {
            for (const auto& [byteStr, tokenName] : data["_vocab_base_byte_to_token"].items()) {
                if (byteStr.size() == 1) {
                    tokenizer.byteToTokenName_[static_cast<std::uint8_t>(byteStr[0])] = tokenName;
                }
            }
        }
        
        // Parse _model (serialized HuggingFace tokenizer)
        if (data.contains("_model")) {
            auto modelJson = nlohmann::json::parse(data["_model"].get<std::string>());
            
            // Parse vocab: token_id -> token_string (bytes)
            if (modelJson.contains("model") && modelJson["model"].contains("vocab")) {
                auto& vocab = modelJson["model"]["vocab"];
                tokenizer.idToBytes_.resize(vocab.size());
                for (const auto& [tokenStr, tokenId] : vocab.items()) {
                    if (tokenId < tokenizer.idToBytes_.size()) {
                        std::vector<std::uint8_t> bytes;
                        bytes.reserve(tokenStr.size());
                        for (char c : tokenStr) {
                            bytes.push_back(static_cast<std::uint8_t>(c));
                        }
                        tokenizer.idToBytes_[tokenId] = std::move(bytes);
                    }
                }
            }
            
            // Parse merges
            if (modelJson.contains("model") && modelJson["model"].contains("merges")) {
                auto& merges = modelJson["model"]["merges"];
                tokenizer.merges_.reserve(merges.size());
                for (const auto& mergeStr : merges) {
                    std::string merge = mergeStr.get<std::string>();
                    size_t spacePos = merge.find(' ');
                    if (spacePos != std::string::npos) {
                        std::string first = merge.substr(0, spacePos);
                        std::string second = merge.substr(spacePos + 1);
                        if (first.size() == 1 && second.size() == 1) {
                            std::uint32_t firstByte = static_cast<std::uint8_t>(first[0]);
                            std::uint32_t secondByte = static_cast<std::uint8_t>(second[0]);
                            tokenizer.merges_.emplace_back(std::make_pair(firstByte, secondByte), 0);
                        }
                    }
                }
            }
        }
        
        // Special tokens from config
        if (data.contains("config") && data["config"].contains("special_tokens")) {
            auto& specialTokens = data["config"]["special_tokens"];
            if (specialTokens.is_array() && specialTokens.size() >= 4) {
                tokenizer.padToken_ = 0;
                tokenizer.bosToken_ = 1;
                tokenizer.eosToken_ = 2;
                tokenizer.maskToken_ = 3;
            }
        }
        
        return tokenizer;
    } catch (const std::exception& e) {
        return std::nullopt;
    }
}

std::vector<std::uint8_t> BpeTokenizer::decodeTokenToBytes(std::uint32_t tokenId) const noexcept {
    if (tokenId >= idToBytes_.size()) {
        return {};
    }
    return idToBytes_[tokenId];
}

std::vector<std::uint8_t> BpeTokenizer::applyReverseMerges(std::uint32_t tokenId) const noexcept {
    auto bytes = decodeTokenToBytes(tokenId);
    if (bytes.empty()) {
        return {};
    }
    if (bytes.size() == 1) {
        return bytes;
    }
    return bytes;
}

std::string BpeTokenizer::bytesToTokenName(const std::vector<std::uint8_t>& bytes) const noexcept {
    if (bytes.empty()) {
        return "";
    }
    // Interpret bytes as UTF-8 string to recover the token name.
    // The bytes in idToBytes_ are the final token string from the vocab,
    // so no per-byte lookup is needed.
    return std::string(bytes.begin(), bytes.end());
}

std::optional<std::string> BpeTokenizer::decodeToken(std::uint32_t tokenId) const noexcept {
    auto bytes = applyReverseMerges(tokenId);
    if (bytes.empty()) {
        return std::nullopt;
    }
    std::string name = bytesToTokenName(bytes);
    if (name.empty()) {
        return std::nullopt;
    }
    return name;
}

std::vector<std::string> BpeTokenizer::decodeTokens(const std::vector<std::uint32_t>& tokenIds) const noexcept {
    std::vector<std::string> result;
    result.reserve(tokenIds.size());
    for (std::uint32_t id : tokenIds) {
        auto name = decodeToken(id);
        if (name.has_value()) {
            result.push_back(*name);
        }
    }
    return result;
}

} // namespace mozart::generation
