#pragma once
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace mozart::remi {
struct BpeTokenDecodeResult {
    std::vector<std::string> tokenNames;
    std::size_t droppedTokenIds = 0;
    std::vector<std::string> warnings;
};
class BpeTokenizer final {
public:
    static std::optional<BpeTokenizer> loadFromJson(const std::string& jsonPath);
    [[nodiscard]] std::optional<std::string> decodeToken(std::uint32_t tokenId) const noexcept;
    [[nodiscard]] std::vector<std::string> decodeTokens(
        const std::vector<std::uint32_t>& tokenIds) const noexcept;
    [[nodiscard]] BpeTokenDecodeResult decodeTokensWithReport(
        const std::vector<std::uint32_t>& tokenIds) const noexcept;
    [[nodiscard]] std::optional<std::vector<std::string>> decodeTokenToNames(
        std::uint32_t tokenId) const noexcept;
    [[nodiscard]] std::size_t vocabSize() const noexcept { return idToEncodedToken_.size(); }
    [[nodiscard]] bool empty() const noexcept { return idToEncodedToken_.empty(); }
    [[nodiscard]] std::optional<std::uint32_t> padToken() const noexcept { return padToken_; }
    [[nodiscard]] std::optional<std::uint32_t> bosToken() const noexcept { return bosToken_; }
    [[nodiscard]] std::optional<std::uint32_t> eosToken() const noexcept { return eosToken_; }
    [[nodiscard]] std::optional<std::uint32_t> maskToken() const noexcept { return maskToken_; }
private:
    BpeTokenizer() = default;
    std::vector<std::string> idToEncodedToken_;
    std::unordered_map<std::string, std::string> baseCharacterToTokenName_;
    std::string continuingSubwordPrefix_;
    std::string endOfWordSuffix_;
    std::string metaspaceReplacement_;
    bool usesMetaspace_ = false;
    std::optional<std::uint32_t> padToken_;
    std::optional<std::uint32_t> bosToken_;
    std::optional<std::uint32_t> eosToken_;
    std::optional<std::uint32_t> maskToken_;
};
} // namespace mozart::remi
