#include "RemiEventAdapter.h"

#include <fstream>
#include <sstream>
#include <unordered_map>
#include "json.hpp"

namespace mozart::generation {

//----------------------------------------------------------------------
// RemiVocabulary implementation
//----------------------------------------------------------------------

std::optional<RemiVocabulary> RemiVocabulary::loadFromJson(const std::string& jsonPath) {
    try {
        std::ifstream file(jsonPath);
        if (!file.is_open()) {
            return std::nullopt;
        }

        nlohmann::json data = nlohmann::json::parse(file);

        // Parse _vocab_base for named musical tokens (matches MidiTok ID space)
        if (!data.contains("_vocab_base")) {
            return std::nullopt;
        }

        auto& vocab = data["_vocab_base"];

        std::unordered_map<std::uint32_t, TokenInfo> tokens;
        std::unordered_map<std::string, std::uint32_t> nameToId;

        for (const auto& [tokenStr, tokenId] : vocab.items()) {
            std::uint32_t id = tokenId.get<std::uint32_t>();
            // items() exposes the JSON object key as std::string.
            std::string name = tokenStr;

            // Parse token name to determine type and value
            RemiEventType type = RemiEventType::Unknown;
            std::uint32_t pitchOrValue = 0;
            std::uint8_t track = 0;

            if (name == "PAD_None" || name == "BOS_None" || name == "EOS_None" || name == "MASK_None") {
                type = RemiEventType::Unknown;
            } else if (name == "Bar_None") {
                type = RemiEventType::Bar;
            } else if (name.rfind("NoteOn_", 0) == 0) {
                type = RemiEventType::NoteOn;
                size_t pos = 7;
                size_t underscore = name.find('_', pos);
                if (underscore != std::string::npos) {
                    try {
                        pitchOrValue = static_cast<std::uint32_t>(std::stoul(name.substr(pos, underscore - pos)));
                        pos = underscore + 1;
                        if (name.rfind("T", pos) == pos) {
                            track = static_cast<std::uint8_t>(std::stoul(name.substr(pos + 1)));
                        }
                    } catch (...) {}
                }
            } else if (name.rfind("Pitch_", 0) == 0) {
                type = RemiEventType::NoteOn;
                try {
                    pitchOrValue = static_cast<std::uint32_t>(std::stoul(name.substr(6)));
                } catch (...) {}
            } else if (name.rfind("PitchDrum_", 0) == 0) {
                type = RemiEventType::NoteOn;
                try {
                    pitchOrValue = static_cast<std::uint32_t>(std::stoul(name.substr(10)));
                } catch (...) {}
            } else if (name.rfind("Velocity_", 0) == 0) {
                type = RemiEventType::Velocity;
                try {
                    pitchOrValue = static_cast<std::uint32_t>(std::stoul(name.substr(9)));
                } catch (...) {}
            } else if (name.rfind("Position_", 0) == 0) {
                type = RemiEventType::Position;
                try {
                    pitchOrValue = static_cast<std::uint32_t>(std::stoul(name.substr(9)));
                } catch (...) {}
            } else if (name.rfind("Tempo_", 0) == 0) {
                type = RemiEventType::Tempo;
                try {
                    pitchOrValue = static_cast<std::uint32_t>(std::stoul(name.substr(6)));
                } catch (...) {}
            } else if (name.rfind("TimeSig_", 0) == 0) {
                type = RemiEventType::TimeSignature;
                std::string tsPart = name.substr(8);
                size_t underscore = tsPart.find('_');
                if (underscore != std::string::npos) {
                    try {
                        std::uint32_t num = static_cast<std::uint32_t>(std::stoul(tsPart.substr(0, underscore)));
                        std::uint32_t den = static_cast<std::uint32_t>(std::stoul(tsPart.substr(underscore + 1)));
                        pitchOrValue = (num << 8) | den;
                    } catch (...) {}
                }
            } else if (name.rfind("Program_", 0) == 0) {
                type = RemiEventType::Program;
                try {
                    pitchOrValue = static_cast<std::uint32_t>(std::stoul(name.substr(8)));
                } catch (...) {}
            } else if (name.rfind("Chord_", 0) == 0) {
                type = RemiEventType::Chord;
            }

            tokens[id] = {id, name, type, pitchOrValue, track};
            nameToId[name] = id;
        }

        return RemiVocabulary(std::move(tokens), std::move(nameToId));
    } catch (const std::exception&) {
        return std::nullopt;
    }
}

RemiVocabulary RemiVocabulary::createFromConfig(const RemiDecoderConfig& config) {
    std::unordered_map<std::uint32_t, TokenInfo> tokens;
    std::unordered_map<std::string, std::uint32_t> nameToId;
    
    std::uint32_t nextId = 4;  // Start after special tokens (0-3)
    
    // Special tokens
    tokens[0] = {0, "PAD_None", RemiEventType::Unknown, 0, 0};
    tokens[1] = {1, "BOS_None", RemiEventType::Unknown, 0, 0};
    tokens[2] = {2, "EOS_None", RemiEventType::Unknown, 0, 0};
    tokens[3] = {3, "MASK_None", RemiEventType::Unknown, 0, 0};
    nameToId["PAD_None"] = 0;
    nameToId["BOS_None"] = 1;
    nameToId["EOS_None"] = 2;
    nameToId["MASK_None"] = 3;
    
    // Generate NoteOn tokens for each pitch in range
    for (std::uint8_t pitch = config.pitchMin; pitch <= config.pitchMax; ++pitch) {
        for (std::uint8_t track = 0; track < config.maxTracks; ++track) {
            std::string name = "NoteOn_" + std::to_string(pitch) + "_T" + std::to_string(track);
            tokens[nextId] = {nextId, name, RemiEventType::NoteOn, pitch, track};
            nameToId[name] = nextId;
            ++nextId;
        }
    }
    
    // Generate Velocity tokens
    for (std::uint8_t v = 0; v < config.numVelocities; ++v) {
        std::string name = "Velocity_" + std::to_string(v);
        tokens[nextId] = {nextId, name, RemiEventType::Velocity, v, 0};
        nameToId[name] = nextId;
        ++nextId;
    }
    
    // Generate Position tokens (based on beat resolution)
    const std::uint32_t positionsPerBar = config.ticksPerBar / (config.ticksPerBeat / 8);  // 8 subdivisions per beat
    for (std::uint32_t pos = 0; pos < positionsPerBar; ++pos) {
        std::string name = "Position_" + std::to_string(pos);
        tokens[nextId] = {nextId, name, RemiEventType::Position, pos, 0};
        nameToId[name] = nextId;
        ++nextId;
    }
    
    // Generate Bar tokens
    for (std::uint32_t bar = 0; bar < config.maxBars; ++bar) {
        std::string name = "Bar_" + std::to_string(bar);
        tokens[nextId] = {nextId, name, RemiEventType::Bar, bar, 0};
        nameToId[name] = nextId;
        ++nextId;
    }
    
    // Generate Tempo tokens
    for (std::uint8_t t = 0; t < config.numTempos; ++t) {
        std::string name = "Tempo_" + std::to_string(t);
        tokens[nextId] = {nextId, name, RemiEventType::Tempo, t, 0};
        nameToId[name] = nextId;
        ++nextId;
    }
    
    // Generate TimeSignature tokens (common ones)
    const std::vector<std::pair<std::uint8_t, std::uint8_t>> timeSigs = {
        {4, 4}, {3, 4}, {6, 8}, {2, 4}, {5, 4}, {7, 8}, {12, 8}
    };
    for (const auto& [num, den] : timeSigs) {
        std::string name = "TimeSig_" + std::to_string(num) + "_" + std::to_string(den);
        tokens[nextId] = {nextId, name, RemiEventType::TimeSignature, static_cast<std::uint32_t>((num << 8) | den), 0};
        nameToId[name] = nextId;
        ++nextId;
    }
    
    // Generate Program tokens
    for (int prog : config.programs) {
        std::string name = "Program_" + std::to_string(prog);
        tokens[nextId] = {nextId, name, RemiEventType::Program, static_cast<std::uint32_t>(prog), 0};
        nameToId[name] = nextId;
        ++nextId;
    }
    
    return RemiVocabulary(std::move(tokens), std::move(nameToId));
}

std::optional<RemiVocabulary::TokenInfo> RemiVocabulary::tokenInfo(std::uint32_t tokenId) const noexcept {
    auto it = tokens_.find(tokenId);
    if (it != tokens_.end()) {
        return it->second;
    }
    return std::nullopt;
}

std::optional<std::uint32_t> RemiVocabulary::tokenId(const std::string& tokenName) const noexcept {
    auto it = nameToId_.find(tokenName);
    if (it != nameToId_.end()) {
        return it->second;
    }
    return std::nullopt;
}

std::vector<RemiVocabulary::TokenInfo> RemiVocabulary::allTokens() const noexcept {
    std::vector<TokenInfo> result;
    result.reserve(tokens_.size());
    for (const auto& [id, info] : tokens_) {
        result.push_back(info);
    }
    std::sort(result.begin(), result.end(), 
              [](const TokenInfo& a, const TokenInfo& b) { return a.id < b.id; });
    return result;
}

} // namespace mozart::generation