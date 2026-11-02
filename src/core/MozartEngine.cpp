#include "MozartEngine.h"

#include "ChannelMixer.h"
#include "Metronome.h"
#include "Project.h"
#include "Track.h"

#include <algorithm>

namespace mozart {

MozartEngine::MozartEngine() {
    project_ = new Project();
    channelMixer_ = new ChannelMixer();
    metronome_ = new Metronome();
}

MozartEngine::~MozartEngine() {
    delete project_;
    project_ = nullptr;
    delete channelMixer_;
    channelMixer_ = nullptr;
    delete metronome_;
    metronome_ = nullptr;
}

std::string MozartEngine::info() const {
    return "Mozart v0.1.0 | C++20 core | MIDI foundation | Ableton Link 4.0";
}

Project& MozartEngine::project() noexcept {
    return *project_;
}

const Project& MozartEngine::project() const noexcept {
    return *project_;
}

std::uint32_t MozartEngine::addTrack(std::string name) {
    const std::uint32_t id = project_->addTrack(std::move(name));
    Track* track = project_->track(id);
    if (track != nullptr) {
        channelMixer_->addTrack(track);
    }
    return id;
}

void MozartEngine::removeTrack(std::uint32_t trackId) {
    Track* track = project_->track(trackId);
    if (track != nullptr) {
        channelMixer_->removeTrack(track);
    }
    project_->removeTrack(trackId);
}

Track* MozartEngine::track(std::uint32_t trackId) noexcept {
    return project_->track(trackId);
}

const Track* MozartEngine::track(std::uint32_t trackId) const noexcept {
    return project_->track(trackId);
}

std::size_t MozartEngine::trackCount() const noexcept {
    return project_->tracks().size();
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
