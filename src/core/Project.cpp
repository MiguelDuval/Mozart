#include "Project.h"

#include <algorithm>

namespace mozart {

Project::Project() = default;

Project::~Project() {
    for (Pattern* pattern : patterns_) {
        delete pattern;
    }
    patterns_.clear();
    for (Track* track : tracks_) {
        delete track;
    }
    tracks_.clear();
}

std::uint32_t Project::addTrack(std::string name) {
    const std::uint32_t id = nextTrackId_++;
    Track* track = new Track(id, std::move(name));
    tracks_.push_back(track);
    return id;
}

void Project::removeTrack(std::uint32_t trackId) {
    // Удаляем все паттерны этого трека
    for (auto it = patterns_.begin(); it != patterns_.end();) {
        if ((*it)->trackId() == trackId) {
            delete *it;
            it = patterns_.erase(it);
        } else {
            ++it;
        }
    }
    for (auto it = tracks_.begin(); it != tracks_.end(); ++it) {
        if ((*it)->id() == trackId) {
            delete *it;
            tracks_.erase(it);
            return;
        }
    }
}

Track* Project::track(std::uint32_t trackId) noexcept {
    for (Track* track : tracks_) {
        if (track->id() == trackId) {
            return track;
        }
    }
    return nullptr;
}

const Track* Project::track(std::uint32_t trackId) const noexcept {
    for (const Track* track : tracks_) {
        if (track->id() == trackId) {
            return track;
        }
    }
    return nullptr;
}

std::uint32_t Project::addPattern(std::uint32_t trackId, std::string name) {
    // Проверяем, что трек существует
    if (track(trackId) == nullptr) {
        return 0;
    }
    const std::uint32_t id = nextPatternId_++;
    Pattern* pattern = new Pattern(id, trackId, std::move(name));
    patterns_.push_back(pattern);
    return id;
}

void Project::removePattern(std::uint32_t patternId) {
    for (auto it = patterns_.begin(); it != patterns_.end(); ++it) {
        if ((*it)->id() == patternId) {
            delete *it;
            patterns_.erase(it);
            return;
        }
    }
}

Pattern* Project::pattern(std::uint32_t patternId) noexcept {
    for (Pattern* pattern : patterns_) {
        if (pattern->id() == patternId) {
            return pattern;
        }
    }
    return nullptr;
}

const Pattern* Project::pattern(std::uint32_t patternId) const noexcept {
    for (const Pattern* pattern : patterns_) {
        if (pattern->id() == patternId) {
            return pattern;
        }
    }
    return nullptr;
}

std::vector<Pattern*> Project::patternsForTrack(std::uint32_t trackId) const noexcept {
    std::vector<Pattern*> result;
    for (const Pattern* pattern : patterns_) {
        if (pattern->trackId() == trackId) {
            result.push_back(const_cast<Pattern*>(pattern));
        }
    }
    return result;
}

MidiEvent* Project::findEvent(
        std::uint32_t trackId,
        std::uint32_t patternId,
        std::uint32_t eventId) noexcept {
    Pattern* pattern = this->pattern(patternId);
    if (pattern == nullptr || pattern->trackId() != trackId) {
        return nullptr;
    }
    return pattern->findEvent(eventId);
}

const MidiEvent* Project::findEvent(
        std::uint32_t trackId,
        std::uint32_t patternId,
        std::uint32_t eventId) const noexcept {
    const Pattern* pattern = this->pattern(patternId);
    if (pattern == nullptr || pattern->trackId() != trackId) {
        return nullptr;
    }
    return pattern->findEvent(eventId);
}

} // namespace mozart
