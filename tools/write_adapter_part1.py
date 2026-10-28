import os
os.makedirs('src/core', exist_ok=True)
f = open('src/core/RemiEventAdapter.cpp', 'w')
f.write('''#include "RemiEventAdapter.h"
#include "GenerationTypes.h"

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

std::optional<RemiEvent> RemiEventAdapter::tokenIdToEvent(std::uint32_t tokenId) const noexcept {
    if (tokenId == config_.padToken || tokenId == config_.bosToken || tokenId == config_.eosToken || tokenId == config_.maskToken) {
        return std::nullopt;
    }
    return std::nullopt;
}

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
''')
f.close()
print('Part 1 done')