#include "RemiEventAdapter.h"
#include "GenerationTypes.h"
#include "RemiDecoderConfig.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <limits>
#include <sstream>

namespace mozart::generation {

RemiEventAdapter::RemiEventAdapter(const RemiDecoderConfig& config) noexcept
    : config_(config), tokenizer_(nullptr) {}

RemiEventAdapter::RemiEventAdapter(const RemiDecoderConfig& config, std::shared_ptr<BpeTokenizer> tokenizer) noexcept
    : config_(config), tokenizer_(std::move(tokenizer)) {}

std::uint8_t RemiEventAdapter::velocityBinToMidi(std::uint8_t bin) const noexcept {
    if (config_.numVelocities == 0) return 64;
    const double ratio = static_cast<double>(bin) / static_cast<double>(config_.numVelocities - 1);
    return static_cast<std::uint8_t>(1 + ratio * 126);
}

std::uint32_t RemiEventAdapter::positionBinToTicks(std::uint32_t bin) const noexcept {
    const std::uint32_t ticksPerPosition = config_.ticksPerBeat / 8;
    return bin * ticksPerPosition;
}

double RemiEventAdapter::tempoBinToBpm(std::uint8_t bin) const noexcept {
    if (config_.numTempos == 0) return 120.0;
    const double ratio = static_cast<double>(bin) / static_cast<double>(config_.numTempos - 1);
    return config_.tempoMin + ratio * (config_.tempoMax - config_.tempoMin);
}

static std::optional<double> parseFloat(const std::string& str) {
    try { return std::stod(str); } catch (...) { return std::nullopt; }
}

static std::optional<std::uint32_t> parseDuration(const std::string& str, std::uint32_t ticksPerBeat) {
    size_t dot1 = str.find(".");
    size_t dot2 = str.find(".", dot1 + 1);
    if (dot1 == std::string::npos || dot2 == std::string::npos) return std::nullopt;
    try {
        double beats = std::stod(str.substr(0, dot1));
        double subdivision = std::stod(str.substr(dot1 + 1, dot2 - dot1 - 1));
        int resolution = std::stoi(str.substr(dot2 + 1));
        double totalBeats = beats + subdivision / resolution;
        return static_cast<std::uint32_t>(totalBeats * ticksPerBeat + 0.5);
    } catch (...) { return std::nullopt; }
}

std::optional<RemiEvent> RemiEventAdapter::parseTokenName(const std::string& tokenName) const noexcept {
    if (tokenName.empty()) return std::nullopt;
    if (tokenName == "PAD_None" || tokenName == "BOS_None" || tokenName == "EOS_None" || tokenName == "MASK_None") return std::nullopt;
    if (tokenName == "Bar_None") return RemiBarEvent{0};
    if (tokenName.rfind("Pitch_", 0) == 0) {
        std::string pitchStr = tokenName.substr(6);
        try {
            int pitch = std::stoi(pitchStr);
            if (pitch >= config_.pitchMin && pitch <= config_.pitchMax) {
                return RemiNoteOnEvent{static_cast<std::uint8_t>(pitch), 0, 0, 0};
            }
        } catch (...) { return std::nullopt; }
    }
    if (tokenName.rfind("PitchDrum_", 0) == 0) {
        std::string pitchStr = tokenName.substr(10);
        try {
            int pitch = std::stoi(pitchStr);
            return RemiNoteOnEvent{static_cast<std::uint8_t>(pitch), 0, 0, 0};
        } catch (...) { return std::nullopt; }
    }
    if (tokenName.rfind("Velocity_", 0) == 0) {
        std::string velStr = tokenName.substr(9);
        try {
            int velocity = std::stoi(velStr);
            if (velocity >= 0 && velocity <= 127) {
                return RemiVelocityEvent{static_cast<std::uint8_t>(velocity)};
            }
        } catch (...) { return std::nullopt; }
    }
    if (tokenName.rfind("Duration_", 0) == 0) {
        std::string durStr = tokenName.substr(9);
        auto durationTicks = parseDuration(durStr, config_.ticksPerBeat);
        if (durationTicks.has_value()) {
            return RemiNoteOffEvent{0, 0, 0};
        }
        return std::nullopt;
    }
    if (tokenName.rfind("Position_", 0) == 0) {
        std::string posStr = tokenName.substr(9);
        try {
            int bin = std::stoi(posStr);
            return RemiPositionEvent{positionBinToTicks(static_cast<std::uint32_t>(bin))};
        } catch (...) { return std::nullopt; }
    }
    if (tokenName.rfind("Tempo_", 0) == 0) {
        std::string tempoStr = tokenName.substr(6);
        auto bpm = parseFloat(tempoStr);
        if (bpm.has_value() && *bpm >= config_.tempoMin && *bpm <= config_.tempoMax) {
            return RemiTempoEvent{*bpm};
        }
        return std::nullopt;
    }
    if (tokenName.rfind("Program_", 0) == 0) {
        std::string progStr = tokenName.substr(8);
        try {
            int program = std::stoi(progStr);
            if (program >= -1 && program <= 127) {
                return RemiProgramEvent{static_cast<std::uint8_t>(program >= 0 ? program : 0), 0};
            }
        } catch (...) { return std::nullopt; }
    }
    if (tokenName.rfind("Chord_", 0) == 0) {
        std::string quality = tokenName.substr(6);
        return RemiChordEvent{"C", quality};
    }
    if (tokenName.rfind("TimeSig_", 0) == 0) {
        std::string tsPart = tokenName.substr(8);
        size_t underscore = tsPart.find("_");
        if (underscore != std::string::npos) {
            try {
                int num = std::stoi(tsPart.substr(0, underscore));
                int den = std::stoi(tsPart.substr(underscore + 1));
                if (num > 0 && den > 0) {
                    return RemiTimeSignatureEvent{static_cast<std::uint8_t>(num), static_cast<std::uint8_t>(den)};
                }
            } catch (...) { return std::nullopt; }
        }
    }
    return std::nullopt;
}

std::optional<RemiEvent> RemiEventAdapter::tokenNameToEvent(const std::string& tokenName) const noexcept {
    return parseTokenName(tokenName);
}

std::pair<PatternProposal, RemiDecodeReport> RemiEventAdapter::decodeTokensToProposal(
    const std::vector<std::uint32_t>& tokenIds,
    const GenerationRequest& request,
    const std::string& providerId,
    const std::string& modelId) const noexcept {
    auto startTime = std::chrono::high_resolution_clock::now();
    DecodeState state;
    RemiDecodeReport report;
    report.result = RemiDecodeResult::Ok;
    if (tokenIds.empty()) {
        report.result = RemiDecodeResult::EmptySequence;
        report.message = "Empty token sequence";
        return {PatternProposal{}, report};
    }
    if (!tokenizer_) {
        report.result = RemiDecodeResult::InvalidToken;
        report.message = "No BPE tokenizer loaded.";
        return {PatternProposal{}, report};
    }
    std::vector<std::string> tokenNames = tokenizer_->decodeTokens(tokenIds);
    if (tokenNames.empty()) {
        report.result = RemiDecodeResult::EmptySequence;
        report.message = "No valid tokens after BPE decoding";
        return {PatternProposal{}, report};
    }
    std::vector<RemiEvent> remiEvents;
    remiEvents.reserve(tokenNames.size());
    for (const auto& tokenName : tokenNames) {
        auto event = parseTokenName(tokenName);
        if (event.has_value()) {
            remiEvents.push_back(*event);
        } else {
            state.warnings.push_back("Unknown token: " + tokenName);
            state.droppedTokens++;
        }
    }
    auto result = decodeEventsToProposal(remiEvents, request, providerId, modelId);
    auto endTime = std::chrono::high_resolution_clock::now();
    auto generationTime = std::chrono::duration_cast<std::chrono::nanoseconds>(endTime - startTime);
    result.first.generationTime = generationTime;
    report.warnings.insert(report.warnings.end(), state.warnings.begin(), state.warnings.end());
    report.droppedTokens += state.droppedTokens;
    return result;
}

} // namespace mozart::generation
