#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace mozart::generation {

// ------------------------------------------------------------------
// BpeTokenizer - inverse BPE tokenizer (MidiTok HF format)
// ------------------------------------------------------------------
class BpeTokenizer {
public:
    static std::optional<BpeTokenizer> loadFromJson(const std::string& jsonPath);

    [[nodiscard]] std::optional<std::vector<std::string>> decodeToken(std::uint32_t tokenId) const noexcept;
    [[nodiscard]] std::vector<std::string> decodeTokens(const std::vector<std::uint32_t>& tokenIds) const noexcept;

    [[nodiscard]] std::size_t vocabSize() const noexcept { return idToBytes_.size(); }
    [[nodiscard]] bool empty() const noexcept { return idToBytes_.empty(); }

    [[nodiscard]] std::uint32_t padToken() const noexcept { return padToken_; }
    [[nodiscard]] std::uint32_t bosToken() const noexcept { return bosToken_; }
    [[nodiscard]] std::uint32_t eosToken() const noexcept { return eosToken_; }
    [[nodiscard]] std::uint32_t maskToken() const noexcept { return maskToken_; }

private:
    BpeTokenizer() = default;

    std::vector<std::vector<std::uint8_t>> idToBytes_;
    std::vector<std::pair<std::pair<std::uint32_t, std::uint32_t>, std::uint32_t>> merges_;
    std::unordered_map<std::uint8_t, std::string> byteToTokenName_;
    std::uint32_t padToken_ = 0;
    std::uint32_t bosToken_ = 1;
    std::uint32_t eosToken_ = 2;
    std::uint32_t maskToken_ = 3;

    [[nodiscard]] std::vector<std::uint8_t> decodeTokenToBytes(std::uint32_t tokenId) const noexcept;
    [[nodiscard]] std::vector<std::uint8_t> applyReverseMerges(std::uint32_t tokenId) const noexcept;
    [[nodiscard]] std::string bytesToTokenName(const std::vector<std::uint8_t>& bytes) const noexcept;
};

} // namespace mozart::generation