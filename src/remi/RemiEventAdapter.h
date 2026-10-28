#pragma once

#include "GenerationTypes.h"
#include "RemiDecoderConfig.h"
#include "BpeTokenizer.h"

#include <cstddef>
#include <cstdint>
#include <vector>
#include <string>
#include <optional>
#include <unordered_map>
#include <chrono>
#include <memory>
#include <variant>

namespace mozart::remi {

enum class RemiEventType {
    NoteOn, NoteOff, Velocity, Position, Bar, Tempo, TimeSignature, Program, Chord, Rest, SustainPedal, PitchBend, Unknown
};

struct RemiNoteOnEvent {
    std::uint8_t pitch = 0;
    std::uint8_t velocity = 64;
    std::uint32_t position = 0;
    std::uint8_t track = 0;
};

struct RemiNoteOffEvent {
    std::uint8_t pitch = 0;
    std::uint32_t position = 0;
    std::uint8_t track = 0;
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
    std::uint8_t numerator = 4;
    std::uint8_t denominator = 4;
};

struct RemiProgramEvent {
    std::uint8_t program = 0;
    std::uint8_t track = 0;
};

struct RemiChordEvent {
    std::string root;
    std::string quality;
};

using RemiEvent = std::variant<
    RemiNoteOnEvent, RemiNoteOffEvent, RemiVelocityEvent, RemiPositionEvent,
    RemiBarEvent, RemiTempoEvent, RemiTimeSignatureEvent, RemiProgramEvent, RemiChordEvent
>;

struct RemiDecodeReport {
    std::string message;
    std::size_t processedTokens = 0;
    std::size_t droppedTokens = 0;
    std::vector<std::string> warnings;

    [[nodiscard]] bool isOk() const noexcept { return droppedTokens == 0 && warnings.empty(); }
};

//----------------------------------------------------------------------
// RemiEventAdapter - converts REMI tokens/events to remi::PatternProposal
//----------------------------------------------------------------------

class RemiEventAdapter final {
public:
    explicit RemiEventAdapter(const RemiDecoderConfig& config = RemiDecoderConfig::defaultConfig()) noexcept;
    explicit RemiEventAdapter(const RemiDecoderConfig& config, std::shared_ptr<BpeTokenizer> tokenizer) noexcept;

    [[nodiscard]] std::pair<PatternProposal, RemiDecodeReport> decodeEventsToProposal(
        const std::vector<RemiEvent>& events,
        const GenerationRequest& request = {},
        const std::string& providerId = "remi-bpe",
        const std::string& modelId = "edm-finetune") const noexcept;

    [[nodiscard]] std::pair<PatternProposal, RemiDecodeReport> decodeTokensToProposal(
        const std::vector<std::uint32_t>& tokenIds,
        const GenerationRequest& request = {},
        const std::string& providerId = "remi-bpe",
        const std::string& modelId = "edm-finetune") const noexcept;

    [[nodiscard]] std::optional<PatternEvent> convertEvent(
        const RemiEvent& event, std::uint32_t currentTick, std::uint8_t currentTrack,
        std::uint8_t currentVelocity) const noexcept;

    [[nodiscard]] const RemiDecoderConfig& config() const noexcept { return config_; }
    [[nodiscard]] bool hasTokenizer() const noexcept { return tokenizer_ != nullptr; }

    [[nodiscard]] std::uint8_t velocityBinToMidi(std::uint8_t bin) const noexcept;
    [[nodiscard]] std::uint32_t positionBinToTicks(std::uint32_t bin) const noexcept;
    [[nodiscard]] double tempoBinToBpm(std::uint8_t bin) const noexcept;

private:
    RemiDecoderConfig config_;
    std::shared_ptr<BpeTokenizer> tokenizer_;
};

} // namespace mozart::remi
