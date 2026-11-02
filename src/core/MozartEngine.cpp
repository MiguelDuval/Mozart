#include "MozartEngine.h"

#include "ChannelMixer.h"
#include "Metronome.h"
#include "Track.h"

#include <algorithm>

namespace mozart {

MozartEngine::MozartEngine() {
    channelMixer_ = new ChannelMixer();
    metronome_ = new Metronome();
}

MozartEngine::~MozartEngine() {
    for (Track* track : tracks_) {
        delete track;
    }
    tracks_.clear();
    delete channelMixer_;
    channelMixer_ = nullptr;
    delete metronome_;
    metronome_ = nullptr;
}

std::string MozartEngine::info() const {
    return "Mozart v0.1.0 | C++20 core | MIDI foundation | Ableton Link 4.0";
}

std::uint32_t MozartEngine::addTrack(std::string name) {
    const std::uint32_t id = nextTrackId_++;
    Track* track = new Track(id, std::move(name));
    tracks_.push_back(track);
    channelMixer_->addTrack(track);
    return id;
}

void MozartEngine::removeTrack(std::uint32_t trackId) {
    for (auto it = tracks_.begin(); it != tracks_.end(); ++it) {
        if ((*it)->id() == trackId) {
            channelMixer_->removeTrack(*it);
            delete *it;
            tracks_.erase(it);
            return;
        }
    }
}

Track* MozartEngine::track(std::uint32_t trackId) noexcept {
    for (Track* track : tracks_) {
        if (track->id() == trackId) {
            return track;
        }
    }
    return nullptr;
}

const Track* MozartEngine::track(std::uint32_t trackId) const noexcept {
    for (const Track* track : tracks_) {
        if (track->id() == trackId) {
            return track;
        }
    }
    return nullptr;
}

std::size_t MozartEngine::trackCount() const noexcept {
    return tracks_.size();
}

ChannelMixer& MozartEngine::channelMixer() noexcept {
    return *channelMixer_;
}

const ChannelMixer& MozartEngine::channelMixer() const noexcept {
    return *channelMixer_;
}

Metronome& MozartEngine::metronome() noexcept {
    return *metronome_;
}

const Metronome& MozartEngine::metronome() const noexcept {
    return *metronome_;
}

} // namespace mozart
