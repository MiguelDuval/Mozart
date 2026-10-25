#pragma once

#include "GenerationTypes.h"

#include <cstdint>
#include <vector>
#include <string>
#include <optional>
#include <unordered_map>

namespace mozart::generation {

//----------------------------------------------------------------------
// REMI Decoder Configuration
//----------------------------------------------------------------------

struct RemiDecoderConfig {
    // Tokenizer vocabulary parameters (from tokenizer.json)
    std::uint32_t vocabSize = 12000;
    std::uint8_t pitchMin = 21;
    std::uint8_t pitchMax = 109;
    std::uint8_t numVelocities = 16;
    std::uint32_t ticksPerBeat = 480;
    std::uint32_t ticksPerBar = 1920;  // 4/4 at 480 ticks/beat
    
    // Beat resolution mapping (from tokenizer config)
    std::unordered_map<std::string, std::uint32_t> beatRes;
    
    // Tempo range
    std::uint8_t numTempos = 32;
    double tempoMin = 40.0;
    double tempoMax = 250.0;
    
    // Program range
    std::vector<int> programs;  // Valid program numbers
    
    // Special tokens
    std::uint32_t padToken = 0;
    std::uint32_t bosToken = 1;
    std::uint32_t eosToken = 2;
    std::uint32_t maskToken = 3;
    
    // Limits
    std::uint32_t maxEvents = 1024;
    std::uint32_t maxBars = 32;
    std::uint32_t maxTracks = 8;
    
    static RemiDecoderConfig fromTokenizerJson(const std::string& jsonPath);
    static RemiDecoderConfig defaultConfig() noexcept;
};

//----------------------------------------------------------------------
// REMI Decode Result
//----------------------------------------------------------------------

enum class RemiDecodeResult {
    Ok,
    EmptySequence,
    InvalidToken,
    Truncated,
    ExceededMaxEvents,
    ExceededMaxBars,
    UnsupportedToken,
    MissingVelocity,
    MissingPosition,
    InvalidState
};

struct RemiDecodeReport {
    RemiDecodeResult result = RemiDecodeResult::Ok;
    std::string message;
    std::size_t processedTokens = 0;
    std::size_t droppedTokens = 0;
    std::vector<std::string> warnings;
    
    [[nodiscard]] bool isOk() const noexcept { return result == RemiDecodeResult::Ok; }
    [[nodiscard]] bool isError() const noexcept { return result != RemiDecodeResult::Ok && result != RemiDecodeResult::Truncated; }
};

} // namespace mozart::generation