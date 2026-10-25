#pragma once

#include "GenerationTypes.h"
#include "RemiDecoderConfig.h"

#include <cstdint>
#include <vector>
#include <string>
#include <optional>
#include <unordered_map>
#include <chrono>
#include <memory>
#include <variant>

namespace mozart::generation {

enum class RemiEventType {
    NoteOn, NoteOff, Velocity, Position, Bar, Tempo, TimeSignature, Program, PitchDrum, Chord, Rest, SustainPedal, PitchBend, Unknown
};

struct RemiNoteOnEvent {
    std::uint8_t pitch = 0; std::uint8_t velocity = 64; std::uint32_t position = 0; std::uint8_t track = 0;
};
struct RemiNoteOffEvent {
    std::uint8_t pitch = 0; std::uint32_t position = 0; std::uint8_t track = 0;
};
struct RemiVelocityEvent {
    std::uint8_t velocity = 64;
};
struct RemiPositionEvent {
    std::uint32_t position = 0;
};
struct RemiBarEvent {
    std::uint32_t barNumber = 0;
};
struct RemiTempoEvent {
    double bpm = 120.0;
};
struct RemiTimeSignatureEvent {
    std::uint8_t numerator = 4; std::uint8_t denominator = 4;
};
struct RemiProgramEvent {
    std::uint8_t program = 0; std::uint8_t track = 0;
};
struct RemiChordEvent {
    std::string root; std::string quality;
};

using RemiEvent = std::variant<
    RemiNoteOnEvent, RemiNoteOffEvent, RemiVelocityEvent, RemiPositionEvent, RemiBarEvent, RemiTempoEvent, RemiTimeSignatureEvent, RemiProgramEvent, RemiChordEvent
>;

//----------------------------------------------------------------------
// RemiVocabulary - vocabulary for REMI tokenization
//----------------------------------------------------------------------

class RemiVocabulary {
public:
    struct TokenInfo {
        std::uint32_t id;
        std::string name;
        RemiEventType type;
        std::uint32_t pitchOrValue;
        std::uint8_t track;
    };

    RemiVocabulary() = default;
    RemiVocabulary(std::unordered_map<std::uint32_t, TokenInfo> tokens, std::unordered_map<std::string, std::uint32_t> nameToId)
        : tokens_(std::move(tokens)), nameToId_(std::move(nameToId)) {}

    static std::optional<RemiVocabulary> loadFromJson(const std::string& jsonPath);
    static RemiVocabulary createFromConfig(const RemiDecoderConfig& config);

    [[nodiscard]] std::optional<TokenInfo> tokenInfo(std::uint32_t tokenId) const noexcept;
    [[nodiscard]] std::optional<std::uint32_t> tokenId(const std::string& tokenName) const noexcept;
    [[nodiscard]] std::vector<TokenInfo> allTokens() const noexcept;
    [[nodiscard]] std::size_t size() const noexcept { return tokens_.size(); }
    [[nodiscard]] bool empty() const noexcept { return tokens_.empty(); }

private:
    std::unordered_map<std::uint32_t, TokenInfo> tokens_;
    std::unordered_map<std::string, std::uint32_t> nameToId_;
};

//----------------------------------------------------------------------
// BpeTokenizer - BPE tokenizer for REMI tokens
//----------------------------------------------------------------------

class BpeTokenizer {
public:
    static std::optional<BpeTokenizer> loadFromJson(const std::string& jsonPath);
    [[nodiscard]] std::optional<std::string> decodeToken(std::uint32_t tokenId) const noexcept;
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
    std::uint32_t padToken_ = 0; std::uint32_t bosToken_ = 1; std::uint32_t eosToken_ = 2; std::uint32_t maskToken_ = 3;
    [[nodiscard]] std::vector<std::uint8_t> decodeTokenToBytes(std::uint32_t tokenId) const noexcept;
    [[nodiscard]] std::vector<std::uint8_t> applyReverseMerges(std::uint32_t tokenId) const noexcept;
    [[nodiscard]] std::string bytesToTokenName(const std::vector<std::uint8_t>& bytes) const noexcept;
};

//----------------------------------------------------------------------
// RemiEventAdapter - converts REMI tokens/events to PatternProposal
//----------------------------------------------------------------------

class RemiEventAdapter final {
public:
    explicit RemiEventAdapter(const RemiDecoderConfig& config = RemiDecoderConfig::defaultConfig()) noexcept;
    explicit RemiEventAdapter(const RemiDecoderConfig& config, std::shared_ptr<BpeTokenizer> tokenizer) noexcept;
    [[nodiscard]] std::pair<PatternProposal, RemiDecodeReport> decodeTokensToProposal(const std::vector<std::uint32_t>& tokenIds, const GenerationRequest& request = {}, const std::string& providerId = "remi-bpe", const std::string& modelId = "edm-finetune") const noexcept;
    [[nodiscard]] std::pair<PatternProposal, RemiDecodeReport> decodeEventsToProposal(const std::vector<RemiEvent>& events, const GenerationRequest& request = {}, const std::string& providerId = "remi-bpe", const std::string& modelId = "edm-finetune") const noexcept;
    [[nodiscard]] std::optional<PatternEvent> convertEvent(const RemiEvent& event, std::uint32_t currentTick, std::uint8_t currentTrack, std::uint8_t currentVelocity) const noexcept;
    [[nodiscard]] const RemiDecoderConfig& config() const noexcept { return config_; }
    [[nodiscard]] bool hasTokenizer() const noexcept { return tokenizer_ != nullptr; }

    // Public mapping utilities used by the decoder's configuration diagnostics and tests.
    [[nodiscard]] std::uint8_t velocityBinToMidi(std::uint8_t bin) const noexcept;
    [[nodiscard]] std::uint32_t positionBinToTicks(std::uint32_t bin) const noexcept;
    [[nodiscard]] double tempoBinToBpm(std::uint8_t bin) const noexcept;

private:
    RemiDecoderConfig config_;
    std::shared_ptr<BpeTokenizer> tokenizer_;
    struct DecodeState {
        std::uint32_t currentTick = 0; std::uint32_t currentBar = 0; std::uint8_t currentTrack = 0; std::uint8_t currentVelocity = 64; std::uint8_t currentProgram = 0; double currentTempo = 120.0; std::uint8_t timeSigNumerator = 4; std::uint8_t timeSigDenominator = 4; bool hasTempo = false; bool hasTimeSignature = false; std::vector<PatternEvent> events; std::vector<std::string> warnings; std::size_t droppedTokens = 0;
        // Длительность, полученная из токена Duration_ (формат beats.subdivision.resolution).
        // Применяется к следующей ноте, если нет предшествующей ноты, к которой можно
        // прикрепить длительность (например, когда Duration_ идёт перед NoteOn).
        std::uint32_t pendingDurationTicks = 0;
        bool hasPendingDuration = false;
        // True only while the current position still points at a just-emitted note.
        // This disambiguates Duration_ for that note from a duration preceding the next one.
        bool hasNoteAtCurrentPosition = false;
    };
    [[nodiscard]] std::pair<PatternProposal, RemiDecodeReport> finalizeProposal(DecodeState& state, const GenerationRequest& request, const std::string& providerId, const std::string& modelId, std::chrono::nanoseconds generationTime) const noexcept;
    [[nodiscard]] std::optional<RemiEvent> tokenNameToEvent(const std::string& tokenName) const noexcept;
    [[nodiscard]] std::optional<RemiEvent> parseTokenName(const std::string& tokenName) const noexcept;
};

} // namespace mozart::generation
