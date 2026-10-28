#include "RemiDecoderConfig.h"
#include "BpeTokenizer.h"
#include "json.hpp"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <stdexcept>
namespace mozart::remi {
namespace {
using json = nlohmann::json;
template <typename T>
bool readNumericPair(const json& object,const char* key,T& first,T& second) {
    if (!object.contains(key)||!object[key].is_array()||object[key].size()!=2U||
        !object[key][0].is_number()||!object[key][1].is_number()) return false;
    first=object[key][0].get<T>(); second=object[key][1].get<T>(); return true;
}
}
RemiDecoderConfig RemiDecoderConfig::defaultConfig() noexcept {
    RemiDecoderConfig c;
    c.vocabSize=0;c.pitchMin=21;c.pitchMax=109;c.numVelocities=32;
    c.ticksPerBeat=480;c.ticksPerBar=1920;c.positionResolution=8;
    c.defaultNoteDurationBeats=0.5;c.beatRes={{"0_4",8},{"4_12",4}};
    c.numTempos=32;c.tempoMin=40.0;c.tempoMax=250.0;c.programs.clear();
    for(int p=0;p<=127;++p)c.programs.push_back(p);
    c.padToken.reset();c.bosToken.reset();c.eosToken.reset();c.maskToken.reset();
    c.maxEvents=1024;c.maxBars=32;c.maxTracks=8;return c;
}
RemiDecoderConfig RemiDecoderConfig::fromTokenizerJson(const std::string& jsonPath) {
    std::ifstream file(jsonPath);
    if(!file.is_open())throw std::runtime_error("Unable to open MidiTok tokenizer JSON");
    json doc;
    try{file>>doc;}catch(const std::exception&){throw std::runtime_error("Unable to parse MidiTok tokenizer JSON");}
    if(!doc.is_object()||!doc.contains("config")||!doc["config"].is_object())
        throw std::runtime_error("Tokenizer JSON is missing its config object");
    if(doc.contains("tokenization")&&doc["tokenization"].is_string()&&
       doc["tokenization"].get<std::string>()!="REMI")
        throw std::runtime_error("Tokenizer is not a MidiTok REMI tokenizer");
    const auto tokenizer=BpeTokenizer::loadFromJson(jsonPath);
    if(!tokenizer||tokenizer->empty())throw std::runtime_error("Tokenizer vocabulary could not be loaded");
    const auto& s=doc["config"]; RemiDecoderConfig c=defaultConfig();
    c.vocabSize=static_cast<std::uint32_t>(tokenizer->vocabSize());
    c.padToken=tokenizer->padToken();c.bosToken=tokenizer->bosToken();
    c.eosToken=tokenizer->eosToken();c.maskToken=tokenizer->maskToken();
    std::uint32_t lo=c.pitchMin,hi=c.pitchMax;
    if(readNumericPair(s,"pitch_range",lo,hi)){
        if(lo>127U||hi>127U||lo>=hi)throw std::runtime_error("Tokenizer pitch_range is invalid");
        c.pitchMin=static_cast<std::uint8_t>(lo);c.pitchMax=static_cast<std::uint8_t>(hi);
    }
    if(s.contains("num_velocities")&&s["num_velocities"].is_number_integer()){
        const auto n=s["num_velocities"].get<std::int64_t>();
        if(n<1||n>128)throw std::runtime_error("Tokenizer num_velocities is invalid");
        c.numVelocities=static_cast<std::uint8_t>(n);
    }
    if(s.contains("default_note_duration")&&s["default_note_duration"].is_number()){
        c.defaultNoteDurationBeats=s["default_note_duration"].get<double>();
        if(!std::isfinite(c.defaultNoteDurationBeats)||c.defaultNoteDurationBeats<=0.0||
           c.defaultNoteDurationBeats>64.0)throw std::runtime_error("Tokenizer default_note_duration is invalid");
    }
    if(s.contains("beat_res")&&s["beat_res"].is_object()){
        c.beatRes.clear();std::uint32_t maxRes=0;
        for(auto it=s["beat_res"].begin();it!=s["beat_res"].end();++it){
            if(!it.value().is_number_integer())throw std::runtime_error("Tokenizer beat_res has a non-integer value");
            const auto v=it.value().get<std::int64_t>();
            if(v<=0||v>1024)throw std::runtime_error("Tokenizer beat_res value is outside range");
            c.beatRes.emplace(it.key(),static_cast<std::uint32_t>(v));
            maxRes=std::max(maxRes,static_cast<std::uint32_t>(v));
        }
        if(maxRes==0||c.ticksPerBeat%maxRes!=0)throw std::runtime_error("Tokenizer beat_res is incompatible with tick resolution");
        c.positionResolution=maxRes;
    }
    if(s.contains("num_tempos")&&s["num_tempos"].is_number_integer()){
        const auto n=s["num_tempos"].get<std::int64_t>();
        if(n<1||n>255)throw std::runtime_error("Tokenizer num_tempos is invalid");
        c.numTempos=static_cast<std::uint8_t>(n);
    }
    std::uint32_t tmin=static_cast<std::uint32_t>(c.tempoMin),tmax=static_cast<std::uint32_t>(c.tempoMax);
    if(readNumericPair(s,"tempo_range",tmin,tmax)){
        if(tmin==0||tmin>=tmax||tmax>500U)throw std::runtime_error("Tokenizer tempo_range is invalid");
        c.tempoMin=static_cast<double>(tmin);c.tempoMax=static_cast<double>(tmax);
    }
    if(s.contains("programs")&&s["programs"].is_array()){
        c.programs.clear();
        for(const auto& item:s["programs"]){
            if(!item.is_number_integer())throw std::runtime_error("Tokenizer programs contains a non-integer");
            const auto p=item.get<std::int64_t>();
            if(p< -1||p>127)throw std::runtime_error("Tokenizer program is outside MIDI range");
            c.programs.push_back(static_cast<int>(p));
        }
    }
    if(!c.padToken.has_value())throw std::runtime_error("Tokenizer PAD special-token ID could not be resolved");
    return c;
}
} // namespace mozart::remi
