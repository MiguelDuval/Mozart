#include "BpeTokenizer.h"

#include <fstream>
#include <sstream>
#include <third_party/nlohmann/json.hpp>

namespace mozart::remi {

using json = nlohmann::json;

std::optional<BpeTokenizer> BpeTokenizer::loadFromJson(const std::string& jsonPath) {
    std::ifstream file(jsonPath);
    if (!file.is_open()) return std::nullopt;

    json doc;
    try {
        file >> doc;
    } catch (...) {
        return std::nullopt;
    }

    BpeTokenizer tokenizer;

    // Parse model.vocab: tokenId -> encodedToken string
    if (doc.contains("_model")) {
        const auto& modelStr = doc["_model"];
        if (modelStr.is_string()) {
            try {
                json model = json::parse(modelStr.get<std::string>());
                if (model.contains("model") && model["model"].contains("vocab")) {
                    const auto& vocab = model["model"]["vocab"];
                    for (auto it = vocab.begin(); it != vocab.end(); ++it) {
                        const std::string& tokenName = it.key();
                        std::uint32_t tokenId = it.value().get<std::uint32_t>();
                        if (tokenId < tokenizer.idToEncodedToken_.size()) {
                            tokenizer.idToEncodedToken_[tokenId] = tokenName;
                        } else {
                            tokenizer.idToEncodedToken_.resize(tokenId + 1);
                            tokenizer.idToEncodedToken_[tokenId] = tokenName;
                        }
                    }
                }
            } catch (...) {
                // Ignore parse errors in model string
            }
        }
    }

    // Parse base vocab mapping
    if (doc.contains("_vocab_base_byte_to_token")) {
        const auto& baseMap = doc["_vocab_base_byte_to_token"];
        for (auto it = baseMap.begin(); it != baseMap.end(); ++it) {
            tokenizer.baseCharacterToTokenName_[it.key()] = it.value().get<std::string>();
        }
    }

    // Parse special tokens
    if (doc.contains("config") && doc["config"].contains("special_tokens")) {
        const auto& specialTokens = doc["config"]["special_tokens"];
        for (std::size_t i = 0; i < specialTokens.size(); ++i) {
            const std::string& tokenName = specialTokens[i].get<std::string>();
            if (tokenName == "PAD_None" || tokenName == "PAD") {
                tokenizer.padToken_ = static_cast<std::uint32_t>(i);
            } else if (tokenName == "BOS_None" || tokenName == "BOS") {
                tokenizer.bosToken_ = static_cast<std::uint32_t>(i);
            } else if (tokenName == "EOS_None" || tokenName == "EOS") {
                tokenizer.eosToken_ = static_cast<std::uint32_t>(i);
            } else if (tokenName == "MASK_None" || tokenName == "MASK") {
                tokenizer.maskToken_ = static_cast<std::uint32_t>(i);
            }
        }
    }

    return tokenizer;
}

std::optional<std::string> BpeTokenizer::decodeToken(std::uint32_t tokenId) const noexcept {
    if (tokenId >= idToEncodedToken_.size()) return std::nullopt;
    const auto& encoded = idToEncodedToken_[tokenId];
    if (encoded.empty()) return std::nullopt;

    // If the encoded token maps to exactly one base token name, return it
    auto it = baseCharacterToTokenName_.find(encoded);
    if (it != baseCharacterToTokenName_.end()) {
        return it->second;
    }

    // Otherwise, the encoded token itself may be a multi-character token name
    // Return it as-is if it looks like a token name
    return encoded;
}

std::vector<std::string> BpeTokenizer::decodeTokens(
        const std::vector<std::uint32_t>& tokenIds) const noexcept {
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

BpeTokenDecodeResult BpeTokenizer::decodeTokensWithReport(
        const std::vector<std::uint32_t>& tokenIds) const noexcept {
    BpeTokenDecodeResult result;
    for (std::uint32_t id : tokenIds) {
        if (id >= idToEncodedToken_.size() || idToEncodedToken_[id].empty()) {
            result.droppedTokenIds++;
            result.warnings.push_back("Dropped token ID " + std::to_string(id));
            continue;
        }
        auto name = decodeToken(id);
        if (name.has_value()) {
            result.tokenNames.push_back(*name);
        } else {
            result.droppedTokenIds++;
            result.warnings.push_back("Dropped token ID " + std::to_string(id) + " (no mapping)");
        }
    }
    return result;
}

std::optional<std::vector<std::string>> BpeTokenizer::decodeTokenToNames(
        std::uint32_t tokenId) const noexcept {
    if (tokenId >= idToEncodedToken_.size()) return std::nullopt;
    const auto& encoded = idToEncodedToken_[tokenId];
    if (encoded.empty()) return std::nullopt;

    std::vector<std::string> names;
    auto it = baseCharacterToTokenName_.find(encoded);
    if (it != baseCharacterToTokenName_.end()) {
        names.push_back(it->second);
    } else {
        names.push_back(encoded);
    }
    return names;
}

} // namespace mozart::remi
