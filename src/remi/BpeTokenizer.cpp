#include "BpeTokenizer.h"
#include "json.hpp"
#include <algorithm>
#include <fstream>
#include <iterator>
#include <string_view>

namespace mozart::remi {
namespace {
using json = nlohmann::json;
constexpr std::uint32_t kMaximumVocabEntries = 2'000'000;

bool isKnownSemanticTokenName(const std::string& token) noexcept {
    static constexpr std::string_view prefixes[] = {
        "PAD","BOS","EOS","MASK","Pitch","PitchDrum","Velocity","Duration",
        "Position","Bar","Tempo","TimeSig","Program","ControlChange","Rest",
        "Chord","KeySig","Pedal","PedalOff","PitchBend","NoteOn","NoteOff","Track"
    };
    const auto separator = token.find('_');
    if (separator == std::string::npos) return false;
    const std::string_view type(token.data(), separator);
    return std::any_of(std::begin(prefixes), std::end(prefixes),
        [type](std::string_view candidate) { return type == candidate; });
}

bool splitUtf8CodePoints(const std::string& text, std::vector<std::string>& characters) {
    characters.clear();
    for (std::size_t i = 0; i < text.size();) {
        const auto lead = static_cast<unsigned char>(text[i]);
        std::size_t length = 0;
        if (lead <= 0x7f) length = 1;
        else if ((lead & 0xe0U) == 0xc0U) length = 2;
        else if ((lead & 0xf0U) == 0xe0U) length = 3;
        else if ((lead & 0xf8U) == 0xf0U) length = 4;
        else return false;
        if (length > text.size() - i) return false;
        for (std::size_t j = 1; j < length; ++j) {
            if ((static_cast<unsigned char>(text[i+j]) & 0xc0U) != 0x80U) return false;
        }
        characters.emplace_back(text.substr(i, length));
        i += length;
    }
    return true;
}

void findMetaspaceReplacement(const json& node, std::string& replacement, bool& found) {
    if (node.is_object()) {
        if (node.value("type", std::string{}) == "Metaspace" &&
            node.contains("replacement") && node["replacement"].is_string()) {
            replacement = node["replacement"].get<std::string>();
            found = !replacement.empty();
        }
        if (node.contains("pretokenizers") && node["pretokenizers"].is_array()) {
            for (const auto& child : node["pretokenizers"])
                findMetaspaceReplacement(child, replacement, found);
        }
        if (node.contains("pre_tokenizer") && node["pre_tokenizer"].is_object())
            findMetaspaceReplacement(node["pre_tokenizer"], replacement, found);
    } else if (node.is_array()) {
        for (const auto& child : node) findMetaspaceReplacement(child, replacement, found);
    }
}

std::optional<std::string> canonicalSpecialName(const std::string& token) {
    if (token == "PAD" || token == "PAD_None") return "PAD_None";
    if (token == "BOS" || token == "BOS_None") return "BOS_None";
    if (token == "EOS" || token == "EOS_None") return "EOS_None";
    if (token == "MASK" || token == "MASK_None") return "MASK_None";
    return std::nullopt;
}
} // namespace

std::optional<BpeTokenizer> BpeTokenizer::loadFromJson(const std::string& jsonPath) {
    std::ifstream file(jsonPath);
    if (!file.is_open()) return std::nullopt;
    json document;
    try { file >> document; } catch (...) { return std::nullopt; }
    if (!document.is_object()) return std::nullopt;

    BpeTokenizer tokenizer;
    if (document.contains("_vocab_base_byte_to_token") &&
        document["_vocab_base_byte_to_token"].is_object()) {
        for (auto it = document["_vocab_base_byte_to_token"].begin();
             it != document["_vocab_base_byte_to_token"].end(); ++it) {
            if (it.value().is_string())
                tokenizer.baseCharacterToTokenName_[it.key()] = it.value().get<std::string>();
        }
    }

    json modelDocument;
    bool hasModelDocument = false;
    if (document.contains("_model")) {
        try {
            if (document["_model"].is_string()) {
                modelDocument = json::parse(document["_model"].get<std::string>());
                hasModelDocument = true;
            } else if (document["_model"].is_object()) {
                modelDocument = document["_model"];
                hasModelDocument = true;
            }
        } catch (...) { return std::nullopt; }
    }

    bool hasModelVocab = false;
    if (hasModelDocument && modelDocument.contains("model") &&
        modelDocument["model"].is_object()) {
        const auto& model = modelDocument["model"];
        if (model.contains("vocab") && model["vocab"].is_object()) {
            const auto& vocab = model["vocab"];
            std::uint32_t maxId = 0;
            bool hasAnyId = false;
            for (auto it = vocab.begin(); it != vocab.end(); ++it) {
                if (!it.value().is_number_integer()) return std::nullopt;
                const auto rawId = it.value().get<std::int64_t>();
                if (rawId < 0 || static_cast<std::uint64_t>(rawId) >= kMaximumVocabEntries)
                    return std::nullopt;
                maxId = std::max(maxId, static_cast<std::uint32_t>(rawId));
                hasAnyId = true;
            }
            if (hasAnyId) {
                tokenizer.idToEncodedToken_.resize(static_cast<std::size_t>(maxId) + 1U);
                std::vector<bool> assigned(tokenizer.idToEncodedToken_.size(), false);
                for (auto it = vocab.begin(); it != vocab.end(); ++it) {
                    const auto id = it.value().get<std::uint32_t>();
                    if (assigned[id]) return std::nullopt;
                    tokenizer.idToEncodedToken_[id] = it.key();
                    assigned[id] = true;
                }
                hasModelVocab = true;
            }
        }
        if (model.contains("continuing_subword_prefix") &&
            model["continuing_subword_prefix"].is_string())
            tokenizer.continuingSubwordPrefix_ = model["continuing_subword_prefix"].get<std::string>();
        if (model.contains("end_of_word_suffix") && model["end_of_word_suffix"].is_string())
            tokenizer.endOfWordSuffix_ = model["end_of_word_suffix"].get<std::string>();
        if (modelDocument.contains("added_tokens") && modelDocument["added_tokens"].is_array()) {
            for (const auto& added : modelDocument["added_tokens"]) {
                if (!added.is_object() || !added.contains("id") ||
                    !added["id"].is_number_integer() || !added.contains("content") ||
                    !added["content"].is_string()) continue;
                const auto rawId = added["id"].get<std::int64_t>();
                if (rawId < 0 || static_cast<std::uint64_t>(rawId) >= kMaximumVocabEntries) continue;
                const auto id = static_cast<std::size_t>(rawId);
                if (id >= tokenizer.idToEncodedToken_.size()) tokenizer.idToEncodedToken_.resize(id+1U);
                if (tokenizer.idToEncodedToken_[id].empty())
                    tokenizer.idToEncodedToken_[id] = added["content"].get<std::string>();
            }
        }
        bool found = false;
        findMetaspaceReplacement(modelDocument, tokenizer.metaspaceReplacement_, found);
        tokenizer.usesMetaspace_ = found;
    }

    // If no trained BPE model exists, IDs come from the base vocabulary.
    if (!hasModelVocab && document.contains("_vocab_base") &&
        document["_vocab_base"].is_object()) {
        const auto& vocab = document["_vocab_base"];
        std::uint32_t maxId = 0;
        bool hasAnyId = false;
        for (auto it = vocab.begin(); it != vocab.end(); ++it) {
            if (!it.value().is_number_integer()) return std::nullopt;
            const auto rawId = it.value().get<std::int64_t>();
            if (rawId < 0 || static_cast<std::uint64_t>(rawId) >= kMaximumVocabEntries)
                return std::nullopt;
            maxId = std::max(maxId, static_cast<std::uint32_t>(rawId));
            hasAnyId = true;
        }
        if (hasAnyId) {
            tokenizer.idToEncodedToken_.resize(static_cast<std::size_t>(maxId)+1U);
            for (auto it = vocab.begin(); it != vocab.end(); ++it)
                tokenizer.idToEncodedToken_[it.value().get<std::uint32_t>()] = it.key();
        }
    }
    if (tokenizer.idToEncodedToken_.empty()) return std::nullopt;

    const auto resolveSpecial = [&tokenizer](const std::string& canonical)
        -> std::optional<std::uint32_t> {
        for (std::size_t id = 0; id < tokenizer.idToEncodedToken_.size(); ++id) {
            if (tokenizer.idToEncodedToken_[id].empty()) continue;
            const auto names = tokenizer.decodeTokenToNames(static_cast<std::uint32_t>(id));
            if (names && names->size() == 1U && names->front() == canonical)
                return static_cast<std::uint32_t>(id);
        }
        return std::nullopt;
    };
    tokenizer.padToken_ = resolveSpecial("PAD_None");
    tokenizer.bosToken_ = resolveSpecial("BOS_None");
    tokenizer.eosToken_ = resolveSpecial("EOS_None");
    tokenizer.maskToken_ = resolveSpecial("MASK_None");
    if (document.contains("config") && document["config"].is_object() &&
        document["config"].contains("special_tokens") &&
        document["config"]["special_tokens"].is_array()) {
        for (const auto& value : document["config"]["special_tokens"]) {
            if (!value.is_string()) continue;
            const auto canonical = canonicalSpecialName(value.get<std::string>());
            if (!canonical) continue;
            if (*canonical == "PAD_None" && !tokenizer.padToken_) tokenizer.padToken_ = resolveSpecial(*canonical);
            else if (*canonical == "BOS_None" && !tokenizer.bosToken_) tokenizer.bosToken_ = resolveSpecial(*canonical);
            else if (*canonical == "EOS_None" && !tokenizer.eosToken_) tokenizer.eosToken_ = resolveSpecial(*canonical);
            else if (*canonical == "MASK_None" && !tokenizer.maskToken_) tokenizer.maskToken_ = resolveSpecial(*canonical);
        }
    }
    return tokenizer;
}

std::optional<std::vector<std::string>> BpeTokenizer::decodeTokenToNames(
        std::uint32_t tokenId) const noexcept {
    if (tokenId >= idToEncodedToken_.size()) return std::nullopt;
    const auto& encoded = idToEncodedToken_[tokenId];
    if (encoded.empty()) return std::nullopt;
    if (isKnownSemanticTokenName(encoded)) return std::vector<std::string>{encoded};
    const auto exact = baseCharacterToTokenName_.find(encoded);
    if (exact != baseCharacterToTokenName_.end()) return std::vector<std::string>{exact->second};

    std::string normalized = encoded;
    if (!continuingSubwordPrefix_.empty() &&
        normalized.rfind(continuingSubwordPrefix_, 0) == 0)
        normalized.erase(0, continuingSubwordPrefix_.size());
    if (!endOfWordSuffix_.empty() && normalized.size() >= endOfWordSuffix_.size() &&
        normalized.compare(normalized.size()-endOfWordSuffix_.size(),
            endOfWordSuffix_.size(), endOfWordSuffix_) == 0)
        normalized.erase(normalized.size()-endOfWordSuffix_.size());
    if (usesMetaspace_ && !metaspaceReplacement_.empty() &&
        normalized.rfind(metaspaceReplacement_, 0) == 0)
        normalized.erase(0, metaspaceReplacement_.size());
    if (normalized.empty()) return std::nullopt;

    std::vector<std::string> characters;
    if (!splitUtf8CodePoints(normalized, characters)) return std::nullopt;
    std::vector<std::string> names;
    names.reserve(characters.size());
    for (const auto& character : characters) {
        const auto found = baseCharacterToTokenName_.find(character);
        if (found == baseCharacterToTokenName_.end()) return std::nullopt;
        names.push_back(found->second);
    }
    if (names.empty()) return std::nullopt;
    return names;
}

std::optional<std::string> BpeTokenizer::decodeToken(std::uint32_t tokenId) const noexcept {
    const auto names = decodeTokenToNames(tokenId);
    if (!names || names->size() != 1U) return std::nullopt;
    return names->front();
}
std::vector<std::string> BpeTokenizer::decodeTokens(
        const std::vector<std::uint32_t>& tokenIds) const noexcept {
    std::vector<std::string> result;
    for (const auto id : tokenIds) {
        const auto names = decodeTokenToNames(id);
        if (names) result.insert(result.end(), names->begin(), names->end());
    }
    return result;
}
BpeTokenDecodeResult BpeTokenizer::decodeTokensWithReport(
        const std::vector<std::uint32_t>& tokenIds) const noexcept {
    BpeTokenDecodeResult result;
    for (const auto id : tokenIds) {
        const auto names = decodeTokenToNames(id);
        if (!names) {
            ++result.droppedTokenIds;
            result.warnings.push_back("Could not decode BPE token ID " + std::to_string(id));
        } else {
            result.tokenNames.insert(result.tokenNames.end(), names->begin(), names->end());
        }
    }
    return result;
}
} // namespace mozart::remi
