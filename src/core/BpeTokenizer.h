#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace mozart::generation {

// Decodes the IDs emitted by MidiTok's Hugging Face BPE tokenizer back into
// one or more REMI/base-token names. A merged BPE ID may expand to multiple names.
struct BpeTokenDecodeResult {
    std::vector<std::string> tokenNames;
    std::size_t droppedTokenIds = 0;
    std::vector<std::string> warnings;
};

class BpeTokenizer {
public:
    static std::optional<BpeTokenizer> loadFromJson(const std::string& jsonPath);

    // Returns a token name only when the ID maps to exactly one base token.
    [[nodiscard]] std::optional<std::string> decodeToken(std::uint32_t tokenId) const noexcept;

    // Expands each BPE ID and flattens the resulting base-token sequence.
    [[nodiscard]] std::vector<std::string> decodeTokens(
        const std::vector<std::uint32_t>& tokenIds) const noexcept;

    // Keeps invalid model IDs observable for production diagnostics.
    [[nodiscard]] BpeTokenDecodeResult decodeTokensWithReport(
        const std::vector<std::uint32_t>& tokenIds) const noexcept;

    [[nodiscard]] std::size_t vocabSize() const noexcept { return idToEncodedToken_.size(); }
    [[nodiscard]] bool empty() const noexcept { return idToEncodedToken_.empty(); }
    [[nodiscard]] std::uint32_t padToken() const noexcept { return padToken_; }
    [[nodiscard]] std::uint32_t bosToken() const noexcept { return bosToken_; }
    [[nodiscard]] std::uint32_t eosToken() const noexcept { return eosToken_; }
    [[nodiscard]] std::uint32_t maskToken() const noexcept { return maskToken_; }

private:
    BpeTokenizer() = default;

    // Model vocabulary strings consist of one or more UTF-8 base-token characters.
    std::vector<std::string> idToEncodedToken_;
    std::unordered_map<std::string, std::string> baseCharacterToTokenName_;
    std::uint32_t padToken_ = 0;
    std::uint32_t bosToken_ = 1;
    std::uint32_t eosToken_ = 2;
    std::uint32_t maskToken_ = 3;

    [[nodiscard]] std::optional<std::vector<std::string>> decodeTokenToNames(
        std::uint32_t tokenId) const noexcept;
};

} // namespace mozart::generation
