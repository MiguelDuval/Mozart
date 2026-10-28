#pragma once
#include "GenerationTypes.h"
#include <cstdint>
#include <vector>
#include <string>
#include <optional>
#include <unordered_map>
namespace mozart::remi {
struct RemiDecoderConfig {
    std::uint32_t vocabSize = 0;
    std::uint8_t pitchMin = 21;
    std::uint8_t pitchMax = 109;
    std::uint8_t numVelocities = 32;
    bool useVelocities = true;
    std::uint32_t ticksPerBeat = 480;
    std::uint32_t ticksPerBar = 1920;
    std::uint32_t positionResolution = 8;
    double defaultNoteDurationBeats = 0.5;
    std::unordered_map<std::string, std::uint32_t> beatRes;
    std::uint8_t numTempos = 32;
    double tempoMin = 40.0;
    double tempoMax = 250.0;
    std::vector<int> programs;
    std::optional<std::uint32_t> padToken;
    std::optional<std::uint32_t> bosToken;
    std::optional<std::uint32_t> eosToken;
    std::optional<std::uint32_t> maskToken;
    std::uint32_t maxEvents = 1024;
    std::uint32_t maxBars = 32;
    std::uint32_t maxTracks = 8;
    static RemiDecoderConfig fromTokenizerJson(const std::string& jsonPath);
    static RemiDecoderConfig defaultConfig() noexcept;
};
} // namespace mozart::remi
