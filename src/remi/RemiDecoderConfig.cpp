#include "RemiDecoderConfig.h"

#include <fstream>
#include <sstream>

namespace mozart::remi {

RemiDecoderConfig RemiDecoderConfig::defaultConfig() noexcept {
    RemiDecoderConfig config;
    config.vocabSize = 12000;
    config.pitchMin = 21;
    config.pitchMax = 109;
    config.numVelocities = 16;
    config.ticksPerBeat = 480;
    config.ticksPerBar = 1920;
    config.positionResolution = 16;
    config.defaultNoteDurationBeats = 0.5;
    config.beatRes.clear();
    config.beatRes["8"] = 60;
    config.beatRes["12"] = 40;
    config.beatRes["16"] = 30;
    config.numTempos = 32;
    config.tempoMin = 40.0;
    config.tempoMax = 250.0;
    config.programs.clear();
    for (int p = 0; p <= 127; ++p) config.programs.push_back(p);
    config.padToken = 0;
    config.bosToken = 1;
    config.eosToken = 2;
    config.maskToken = 3;
    config.maxEvents = 1024;
    config.maxBars = 32;
    config.maxTracks = 8;
    return config;
}

RemiDecoderConfig RemiDecoderConfig::fromTokenizerJson(const std::string& jsonPath) {
    (void)jsonPath;
    return defaultConfig();
}

} // namespace mozart::remi
