#include "RemiEventAdapter.h"
#include "GenerationTypes.h"
#include "RemiDecoderConfig.h"

#include <algorithm>
#include <cmath>
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
    if (config_.numVelocities <= 1) return 64;
    const auto boundedBin = std::min<std::uint8_t>(bin, static_cast<std::uint8_t>(config_.numVelocities - 1));
    const double ratio = static_cast<double>(boundedBin) / static_cast<double>(config_.numVelocities - 1);
    // Round to the nearest MIDI velocity; truncation makes midpoint bins biased low.
    return static_cast<std::uint8_t>(std::lround(1.0 + ratio * 126.0));
}

std::uint32_t RemiEventAdapter::positionBinToTicks(std::uint32_t bin) const noexcept {
    const std::uint32_t ticksPerPosition = config_.ticksPerBeat / 8;
    return bin * ticksPerPosition;
}

double RemiEventAdapter::tempoBinToBpm(std::uint8_t bin) const noexcept {
    if (config_.numTempos == 0) return 120.0;
    if (config_.numTempos == 1) return config_.tempoMin;
    const auto boundedBin = std::min<std::uint8_t>(bin, static_cast<std::uint8_t>(config_.numTempos - 1));
    const double ratio = static_cast<double>(boundedBin) / static_cast<double>(config_.numTempos - 1);
    return config_.tempoMin + ratio * (config_.tempoMax - config_.tempoMin);
}

static std::optional<int> parseInt(const std::string& str) {
    try {
        size_t consumed = 0;
        const int value = std::stoi(str, &consumed);
        if (consumed != str.size()) return std::nullopt;
        return value;
    } catch (...) {
        return std::nullopt;
    }
}

static std::optional<double> parseFloat(const std::string& str) {
    try {
        size_t consumed = 0;
        const double value = std::stod(str, &consumed);
        if (consumed != str.size() || !std::isfinite(value)) return std::nullopt;
        return value;
    } catch (...) {
        return std::nullopt;
    }
}

static std::optional<std::uint32_t> parseDuration(const std::string& str, std::uint32_t ticksPerBeat) {
    const size_t dot1 = str.find('.');
    if (dot1 == std::string::npos) return std::nullopt;
    const size_t dot2 = str.find('.', dot1 + 1);
    if (dot2 == std::string::npos || str.find('.', dot2 + 1) != std::string::npos) {
        return std::nullopt;
    }

    try {
        const std::string beatsText = str.substr(0, dot1);
        const std::string subdivisionText = str.substr(dot1 + 1, dot2 - dot1 - 1);
        const std::string resolutionText = str.substr(dot2 + 1);

        size_t beatsChars = 0;
        const double beats = std::stod(beatsText, &beatsChars);
        if (beatsChars != beatsText.size() || !std::isfinite(beats) || beats < 0.0) {
            return std::nullopt;
        }

        size_t subdivisionChars = 0;
        const double subdivision = std::stod(subdivisionText, &subdivisionChars);
        if (subdivisionChars != subdivisionText.size() || !std::isfinite(subdivision) ||
            subdivision < 0.0) {
            return std::nullopt;
        }

        size_t resolutionChars = 0;
        const int resolution = std::stoi(resolutionText, &resolutionChars);
        if (resolutionChars != resolutionText.size() || resolution <= 0 ||
            subdivision >= static_cast<double>(resolution)) {
            return std::nullopt;
        }

        const long double ticks =
            (static_cast<long double>(beats) +
             static_cast<long double>(subdivision) / static_cast<long double>(resolution)) *
            static_cast<long double>(ticksPerBeat);
        if (!std::isfinite(ticks) || ticks < 0.0L ||
            ticks > static_cast<long double>(std::numeric_limits<std::uint32_t>::max())) {
            return std::nullopt;
        }

        const long double roundedTicks = std::floor(ticks + 0.5L);
        if (!std::isfinite(roundedTicks) || roundedTicks < 1.0L ||
            roundedTicks > static_cast<long double>(std::numeric_limits<std::uint32_t>::max())) {
            return std::nullopt;
        }
        return static_cast<std::uint32_t>(roundedTicks);
    } catch (...) {
        return std::nullopt;
    }
}

std::optional<RemiEvent> RemiEventAdapter::parseTokenName(const std::string& tokenName) const noexcept {
    if (tokenName.empty()) return std::nullopt;
    if (tokenName == "PAD_None" || tokenName == "BOS_None" || tokenName == "EOS_None" || tokenName == "MASK_None") return std::nullopt;
    if (tokenName == "Bar_None") return RemiBarEvent{std::numeric_limits<std::uint32_t>::max()};
    if (tokenName.rfind("Pitch_", 0) == 0) {
        const auto pitch = parseInt(tokenName.substr(6));
        if (pitch.has_value() && *pitch >= config_.pitchMin && *pitch <= config_.pitchMax) {
            return RemiNoteOnEvent{static_cast<std::uint8_t>(*pitch), 0, 0, 0};
        }
        return std::nullopt;
    }
    if (tokenName.rfind("PitchDrum_", 0) == 0) {
        const auto pitch = parseInt(tokenName.substr(10));
        // Validate before narrowing to uint8_t; otherwise 300 wraps to MIDI pitch 44.
        if (pitch.has_value() && *pitch >= config_.pitchMin && *pitch <= config_.pitchMax) {
            return RemiNoteOnEvent{static_cast<std::uint8_t>(*pitch), 0, 0, 0};
        }
        return std::nullopt;
    }
    if (tokenName.rfind("Velocity_", 0) == 0) {
        const auto velocityBin = parseInt(tokenName.substr(9));
        if (velocityBin.has_value() && *velocityBin >= 0 && *velocityBin < config_.numVelocities) {
            return RemiVelocityEvent{static_cast<std::uint8_t>(*velocityBin)};
        }
        return std::nullopt;
    }
    if (tokenName.rfind("Duration_", 0) == 0) {
        std::string durStr = tokenName.substr(9);
        auto durationTicks = parseDuration(durStr, config_.ticksPerBeat);
        if (durationTicks.has_value()) {
            // Токен Duration_ кодирует длительность ноты. Так как вариант RemiEvent не
            // содержит отдельного события длительности, duration представляется маркером
            // note-off с pitch == 0: позиция хранит длительность в тиках, track — 0.
            // pitch == 0 недопустим как высота ноты (pitchMin >= 21), поэтому маркер не
            // пересекается с реальными нотами. Декодер прикрепляет длительность к
            // соответствующей ноте в decodeEventsToProposal().
            return RemiNoteOffEvent{0, *durationTicks, 0};
        }
        return std::nullopt;
    }
    if (tokenName.rfind("Position_", 0) == 0) {
        const auto bin = parseInt(tokenName.substr(9));
        const std::uint32_t ticksPerPosition = config_.ticksPerBeat / 8;
        if (!bin.has_value() || *bin < 0 || ticksPerPosition == 0 || config_.ticksPerBar == 0) {
            return std::nullopt;
        }

        // Position_ is a within-bar bin, not an absolute tick. Bar_ advances the bar;
        // reject bins beyond the configured bar before they can overflow during conversion.
        const std::uint32_t positionsPerBar =
            config_.ticksPerBar / ticksPerPosition +
            (config_.ticksPerBar % ticksPerPosition == 0 ? 0U : 1U);
        if (static_cast<std::uint32_t>(*bin) >= positionsPerBar) {
            return std::nullopt;
        }

        // Keep the encoded bin here; decodeEventsToProposal converts it to ticks.
        return RemiPositionEvent{static_cast<std::uint32_t>(*bin)};
    }
    if (tokenName.rfind("Tempo_", 0) == 0) {
        std::string tempoStr = tokenName.substr(6);
        // MidiTok-style model vocabularies often encode a tempo bin (0..numTempos-1).
        // Preserve support for explicit BPM tokens such as Tempo_120 or Tempo_120.0.
        if (tempoStr.find_first_of(".eE") == std::string::npos) {
            const auto tempoBin = parseInt(tempoStr);
            if (!tempoBin.has_value()) return std::nullopt;
            if (*tempoBin >= 0 && *tempoBin < config_.numTempos) {
                return RemiTempoEvent{tempoBinToBpm(static_cast<std::uint8_t>(*tempoBin))};
            }
        }
        auto bpm = parseFloat(tempoStr);
        if (bpm.has_value() && *bpm >= config_.tempoMin && *bpm <= config_.tempoMax) {
            return RemiTempoEvent{*bpm};
        }
        return std::nullopt;
    }
    if (tokenName.rfind("Program_", 0) == 0) {
        const auto program = parseInt(tokenName.substr(8));
        if (program.has_value() && *program >= -1 && *program <= 127) {
            return RemiProgramEvent{static_cast<std::uint8_t>(*program >= 0 ? *program : 0), 0};
        }
        return std::nullopt;
    }
    if (tokenName.rfind("Chord_", 0) == 0) {
        std::string quality = tokenName.substr(6);
        return RemiChordEvent{"C", quality};
    }
    if (tokenName.rfind("TimeSig_", 0) == 0) {
        const std::string tsPart = tokenName.substr(8);
        const size_t underscore = tsPart.find("_");
        if (underscore == std::string::npos) return std::nullopt;
        const auto numerator = parseInt(tsPart.substr(0, underscore));
        const auto denominator = parseInt(tsPart.substr(underscore + 1));
        if (numerator.has_value() && denominator.has_value() &&
            *numerator > 0 && *numerator <= 255 &&
            *denominator > 0 && *denominator <= 255) {
            return RemiTimeSignatureEvent{
                static_cast<std::uint8_t>(*numerator), static_cast<std::uint8_t>(*denominator)};
        }
        return std::nullopt;
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
    auto bpeResult = tokenizer_->decodeTokensWithReport(tokenIds);
    std::vector<std::string> tokenNames = std::move(bpeResult.tokenNames);
    state.warnings = std::move(bpeResult.warnings);
    state.droppedTokens = bpeResult.droppedTokenIds;
    if (tokenNames.empty()) {
        report.result = RemiDecodeResult::EmptySequence;
        report.message = "No valid tokens after BPE decoding";
        report.droppedTokens = state.droppedTokens;
        report.warnings = std::move(state.warnings);
        return {PatternProposal{}, report};
    }
    std::vector<RemiEvent> remiEvents;
    remiEvents.reserve(tokenNames.size());
    std::size_t bpeDropped = tokenIds.size() - tokenNames.size();
    for (const auto& tokenName : tokenNames) {
        // These are standard sequence-control tokens, not malformed musical events.
        if (tokenName == "PAD_None" || tokenName == "BOS_None" ||
            tokenName == "EOS_None" || tokenName == "MASK_None") {
            continue;
        }
        auto event = parseTokenName(tokenName);
        if (event.has_value()) {
            remiEvents.push_back(*event);
        } else {
            state.warnings.push_back("Unknown token: " + tokenName);
            state.droppedTokens++;
        }
    }
    state.droppedTokens += static_cast<std::uint32_t>(bpeDropped);
    auto result = decodeEventsToProposal(remiEvents, request, providerId, modelId);
    auto endTime = std::chrono::high_resolution_clock::now();
    auto generationTime = std::chrono::duration_cast<std::chrono::nanoseconds>(endTime - startTime);
    result.first.generationTime = generationTime;
    result.second.warnings.insert(
        result.second.warnings.end(), state.warnings.begin(), state.warnings.end());
    result.second.droppedTokens += state.droppedTokens;
    return result;
}

} // namespace mozart::generation
