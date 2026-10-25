#include "RemiDecoderConfig.h"

#include <fstream>
#include <sstream>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <optional>
#include <unordered_map>
#include "json.hpp"

namespace mozart::generation {
namespace {

std::optional<std::uint32_t> readUnsigned32(const nlohmann::json& value) {
    if (!value.is_number_integer()) return std::nullopt;

    if (value.is_number_unsigned()) {
        const auto number = value.get<std::uint64_t>();
        if (number > std::numeric_limits<std::uint32_t>::max()) return std::nullopt;
        return static_cast<std::uint32_t>(number);
    }

    const auto number = value.get<std::int64_t>();
    if (number < 0 || static_cast<std::uint64_t>(number) >
                          std::numeric_limits<std::uint32_t>::max()) {
        return std::nullopt;
    }
    return static_cast<std::uint32_t>(number);
}

bool isValidTempoRange(const nlohmann::json& value, double& minBpm, double& maxBpm) {
    if (!value.is_array() || value.size() < 2 ||
        !value[0].is_number() || !value[1].is_number()) {
        return false;
    }

    const double candidateMin = value[0].get<double>();
    const double candidateMax = value[1].get<double>();
    if (!std::isfinite(candidateMin) || !std::isfinite(candidateMax) ||
        candidateMin <= 0.0 || candidateMax < candidateMin) {
        return false;
    }

    minBpm = candidateMin;
    maxBpm = candidateMax;
    return true;
}

} // namespace

RemiDecoderConfig RemiDecoderConfig::defaultConfig() noexcept {
    RemiDecoderConfig config;
    config.vocabSize = 12000;
    config.pitchMin = 21;
    config.pitchMax = 109;
    config.numVelocities = 16;
    config.ticksPerBeat = 480;
    config.ticksPerBar = 1920;
    config.numTempos = 32;
    config.tempoMin = 40.0;
    config.tempoMax = 250.0;
    config.padToken = 0;
    config.bosToken = 1;
    config.eosToken = 2;
    config.maskToken = 3;
    config.maxEvents = 1024;
    config.maxBars = 32;
    config.maxTracks = 8;
    
    // Default beat resolution (from tokenizer.json)
    config.beatRes["0_4"] = 8;
    config.beatRes["4_12"] = 4;
    
    // Standard GM programs
    config.programs.reserve(128);
    for (int i = 0; i < 128; ++i) {
        config.programs.push_back(i);
    }
    config.programs.insert(config.programs.begin(), -1);  // -1 for drums
    
    return config;
}

RemiDecoderConfig RemiDecoderConfig::fromTokenizerJson(const std::string& jsonPath) {
    RemiDecoderConfig config = defaultConfig();

    try {
        std::ifstream file(jsonPath);
        if (!file.is_open()) return config;

        const nlohmann::json data = nlohmann::json::parse(file);
        if (!data.contains("config") || !data["config"].is_object()) return config;
        const auto& cfg = data["config"];

        // Parse each field independently. A malformed tokenizer setting must not wrap
        // through a narrow integer cast or leave a half-parsed invalid configuration.
        if (cfg.contains("pitch_range") && cfg["pitch_range"].is_array() &&
            cfg["pitch_range"].size() >= 2) {
            const auto minPitch = readUnsigned32(cfg["pitch_range"][0]);
            const auto maxPitch = readUnsigned32(cfg["pitch_range"][1]);
            if (minPitch && maxPitch && *minPitch <= *maxPitch && *maxPitch <= 127U) {
                config.pitchMin = static_cast<std::uint8_t>(*minPitch);
                config.pitchMax = static_cast<std::uint8_t>(*maxPitch);
            }
        }

        if (cfg.contains("beat_res") && cfg["beat_res"].is_object()) {
            std::unordered_map<std::string, std::uint32_t> parsedBeatRes;
            bool valid = !cfg["beat_res"].empty();
            for (const auto& [key, value] : cfg["beat_res"].items()) {
                const auto resolution = readUnsigned32(value);
                if (!resolution || *resolution == 0U || key.empty()) {
                    valid = false;
                    break;
                }
                parsedBeatRes.emplace(key, *resolution);
            }
            if (valid) config.beatRes = std::move(parsedBeatRes);
        }

        if (cfg.contains("num_velocities")) {
            const auto value = readUnsigned32(cfg["num_velocities"]);
            if (value && *value >= 1U && *value <= 255U) {
                config.numVelocities = static_cast<std::uint8_t>(*value);
            }
        }

        if (cfg.contains("num_tempos")) {
            const auto value = readUnsigned32(cfg["num_tempos"]);
            if (value && *value >= 1U && *value <= 255U) {
                config.numTempos = static_cast<std::uint8_t>(*value);
            }
        }

        if (cfg.contains("tempo_range")) {
            double minBpm = config.tempoMin;
            double maxBpm = config.tempoMax;
            if (isValidTempoRange(cfg["tempo_range"], minBpm, maxBpm)) {
                config.tempoMin = minBpm;
                config.tempoMax = maxBpm;
            }
        }
    } catch (const std::exception&) {
        // Malformed JSON preserves safe defaults; callers may still use deterministic decode.
    }

    return config;
}
} // namespace mozart::generation