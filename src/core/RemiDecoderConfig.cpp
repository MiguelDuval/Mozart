#include "RemiDecoderConfig.h"

#include <fstream>
#include <sstream>
#include <algorithm>
#include "json.hpp"

namespace mozart::generation {

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
        if (!file.is_open()) {
            return config;
        }

        nlohmann::json data = nlohmann::json::parse(file);

        if (!data.contains("config")) {
            return config;
        }

        auto& cfg = data["config"];

        if (cfg.contains("pitch_range") && cfg["pitch_range"].is_array() && cfg["pitch_range"].size() >= 2) {
            config.pitchMin = static_cast<std::uint8_t>(cfg["pitch_range"][0].get<std::uint32_t>());
            config.pitchMax = static_cast<std::uint8_t>(cfg["pitch_range"][1].get<std::uint32_t>());
        }

        if (cfg.contains("beat_res") && cfg["beat_res"].is_object()) {
            config.beatRes.clear();
            for (const auto& [key, val] : cfg["beat_res"].items()) {
                config.beatRes[key] = val.get<std::uint32_t>();
            }
        }

        if (cfg.contains("num_velocities")) {
            config.numVelocities = static_cast<std::uint8_t>(cfg["num_velocities"].get<std::uint32_t>());
        }

        if (cfg.contains("num_tempos")) {
            config.numTempos = static_cast<std::uint8_t>(cfg["num_tempos"].get<std::uint32_t>());
        }

        if (cfg.contains("tempo_range") && cfg["tempo_range"].is_array() && cfg["tempo_range"].size() >= 2) {
            config.tempoMin = cfg["tempo_range"][0].get<double>();
            config.tempoMax = cfg["tempo_range"][1].get<double>();
        }

    } catch (const std::exception&) {
    }

    return config;
}

} // namespace mozart::generation