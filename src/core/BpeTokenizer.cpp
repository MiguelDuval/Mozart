#include "RemiEventAdapter.h"
#include "GenerationTypes.h"

#include <fstream>
#include <string>
#include <vector>
#include <exception>
#include "json.hpp"

namespace mozart::generation {
namespace {

std::size_t utf8CharacterLength(unsigned char first) noexcept {
    if ((first & 0x80U) == 0) return 1;
    if ((first & 0xE0U) == 0xC0U) return 2;
    if ((first & 0xF0U) == 0xE0U) return 3;
    if ((first & 0xF8U) == 0xF0U) return 4;
    return 0;
}

bool isControlToken(const std::string& token) noexcept {
    return token == "PAD_None" || token == "BOS_None" ||
           token == "EOS_None" || token == "MASK_None";
}

bool looksLikeLegacyBaseToken(const std::string& token) noexcept {
    static constexpr const char* prefixes[] = {
        "Pitch_", "PitchDrum_", "NoteOn_", "Velocity_", "Duration_",
        "Position_", "Tempo_", "Program_", "Chord_", "TimeSig_", "Bar_"
    };
    for (const auto* prefix : prefixes) {
        if (token.rfind(prefix, 0) == 0) return true;
    }
    return false;
}

} // namespace

//----------------------------------------------------------------------
// BpeTokenizer Implementation
//----------------------------------------------------------------------

std::optional<BpeTokenizer> BpeTokenizer::loadFromJson(const std::string& jsonPath) {
    try {
        std::ifstream file(jsonPath);
        if (!file.is_open()) return std::nullopt;

        const nlohmann::json data = nlohmann::json::parse(file);
        BpeTokenizer tokenizer;

        // MidiTok stores a Unicode character -> base token mapping. These characters
        // may occupy 2–4 bytes in UTF-8, so keep each whole character as the map key.
        if (data.contains("_vocab_base_byte_to_token") &&
            data["_vocab_base_byte_to_token"].is_object()) {
            for (const auto& [encodedCharacter, tokenName] :
                 data["_vocab_base_byte_to_token"].items()) {
                if (!encodedCharacter.empty() && tokenName.is_string()) {
                    tokenizer.baseCharacterToTokenName_[encodedCharacter] =
                        tokenName.get<std::string>();
                }
            }
        }

        // The Hugging Face model vocabulary maps an encoded BPE string to its ID.
        // A model-vocabulary entry can represent multiple base music tokens.
        if (!data.contains("_model")) return std::nullopt;
        nlohmann::json modelJson;
        if (data["_model"].is_string()) {
            modelJson = nlohmann::json::parse(data["_model"].get<std::string>());
        } else if (data["_model"].is_object()) {
            modelJson = data["_model"];
        } else {
            return std::nullopt;
        }

        if (!modelJson.contains("model") ||
            !modelJson["model"].is_object() ||
            !modelJson["model"].contains("vocab") ||
            !modelJson["model"]["vocab"].is_object()) {
            return std::nullopt;
        }

        const auto& vocab = modelJson["model"]["vocab"];
        if (vocab.empty()) return std::nullopt;

        tokenizer.idToEncodedToken_.resize(vocab.size());
        std::vector<bool> occupied(vocab.size(), false);
        for (const auto& [encodedToken, tokenId] : vocab.items()) {
            if (!tokenId.is_number_integer()) return std::nullopt;
            const auto id = tokenId.get<std::int64_t>();
            if (id < 0 || static_cast<std::uint64_t>(id) >= vocab.size()) {
                return std::nullopt;
            }
            const auto index = static_cast<std::size_t>(id);
            if (occupied[index] || encodedToken.empty()) return std::nullopt;
            tokenizer.idToEncodedToken_[index] = encodedToken;
            occupied[index] = true;
        }
        for (const bool hasEntry : occupied) {
            if (!hasEntry) return std::nullopt;
        }

        // Keep the default special-token IDs for legacy files, but prefer the
        // actual token IDs recovered from the serialized base-character mapping.
        if (data.contains("config") && data["config"].is_object() &&
            data["config"].contains("special_tokens") &&
            data["config"]["special_tokens"].is_array() &&
            data["config"]["special_tokens"].size() >= 4) {
            tokenizer.padToken_ = 0;
            tokenizer.bosToken_ = 1;
            tokenizer.eosToken_ = 2;
            tokenizer.maskToken_ = 3;
        }
        for (std::size_t id = 0; id < tokenizer.idToEncodedToken_.size(); ++id) {
            auto decoded = tokenizer.decodeTokenToNames(static_cast<std::uint32_t>(id));
            if (!decoded.has_value() || decoded->size() != 1) continue;
            const auto& name = decoded->front();
            if (name == "PAD_None") tokenizer.padToken_ = static_cast<std::uint32_t>(id);
            else if (name == "BOS_None") tokenizer.bosToken_ = static_cast<std::uint32_t>(id);
            else if (name == "EOS_None") tokenizer.eosToken_ = static_cast<std::uint32_t>(id);
            else if (name == "MASK_None") tokenizer.maskToken_ = static_cast<std::uint32_t>(id);
        }

        return tokenizer;
    } catch (const std::exception&) {
        return std::nullopt;
    }
}

std::optional<std::vector<std::string>> BpeTokenizer::decodeTokenToNames(
    std::uint32_t tokenId) const noexcept {
    if (tokenId >= idToEncodedToken_.size()) return std::nullopt;

    const std::string& encoded = idToEncodedToken_[tokenId];
    if (encoded.empty()) return std::nullopt;

    // Some older/project-local tokenizer fixtures stored direct token names.
    if (isControlToken(encoded)) return std::vector<std::string>{encoded};

    std::vector<std::string> names;
    for (std::size_t offset = 0; offset < encoded.size();) {
        const auto first = static_cast<unsigned char>(encoded[offset]);
        const std::size_t length = utf8CharacterLength(first);
        if (length == 0 || offset + length > encoded.size()) {
            return std::nullopt;
        }
        for (std::size_t i = 1; i < length; ++i) {
            if ((static_cast<unsigned char>(encoded[offset + i]) & 0xC0U) != 0x80U) {
                return std::nullopt;
            }
        }

        const std::string character = encoded.substr(offset, length);
        const auto it = baseCharacterToTokenName_.find(character);
        if (it == baseCharacterToTokenName_.end()) {
            // Fall back only when no base-character map exists, for legacy test/config
            // files which stored literal REMI token names in model.vocab.
            if (baseCharacterToTokenName_.empty() && looksLikeLegacyBaseToken(encoded)) {
                return std::vector<std::string>{encoded};
            }
            return std::nullopt;
        }
        names.push_back(it->second);
        offset += length;
    }

    if (names.empty()) return std::nullopt;
    return names;
}

std::optional<std::string> BpeTokenizer::decodeToken(std::uint32_t tokenId) const noexcept {
    auto names = decodeTokenToNames(tokenId);
    if (!names.has_value() || names->size() != 1) return std::nullopt;
    return names->front();
}

BpeTokenDecodeResult BpeTokenizer::decodeTokensWithReport(
    const std::vector<std::uint32_t>& tokenIds) const noexcept {
    BpeTokenDecodeResult result;
    result.tokenNames.reserve(tokenIds.size());

    for (const std::uint32_t id : tokenIds) {
        auto names = decodeTokenToNames(id);
        if (names.has_value()) {
            result.tokenNames.insert(result.tokenNames.end(), names->begin(), names->end());
        } else {
            ++result.droppedTokenIds;
            result.warnings.push_back("Unable to decode BPE token ID " + std::to_string(id));
        }
    }
    return result;
}

std::vector<std::string> BpeTokenizer::decodeTokens(
    const std::vector<std::uint32_t>& tokenIds) const noexcept {
    return decodeTokensWithReport(tokenIds).tokenNames;
}

} // namespace mozart::generation
