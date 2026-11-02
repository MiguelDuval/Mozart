#pragma once

#include "MidiEvent.h"
#include "Pattern.h"
#include "Track.h"

#include <cstdint>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>

namespace mozart {

/**
 * Проектная модель: содержит треки, паттерны и их размещение.
 * Является единым источником истины для состояния сессии.
 */
class Project final {
public:
    Project();
    ~Project();

    Project(const Project&) = delete;
    Project& operator=(const Project&) = delete;

    // --- Треки ---

    std::uint32_t addTrack(std::string name);
    void removeTrack(std::uint32_t trackId);
    [[nodiscard]] Track* track(std::uint32_t trackId) noexcept;
    [[nodiscard]] const Track* track(std::uint32_t trackId) const noexcept;
    [[nodiscard]] const std::vector<Track*>& tracks() const noexcept { return tracks_; }

    // --- Паттерны ---

    std::uint32_t addPattern(std::uint32_t trackId, std::string name);
    void removePattern(std::uint32_t patternId);
    [[nodiscard]] Pattern* pattern(std::uint32_t patternId) noexcept;
    [[nodiscard]] const Pattern* pattern(std::uint32_t patternId) const noexcept;
    [[nodiscard]] std::vector<Pattern*> patternsForTrack(std::uint32_t trackId) const noexcept;

    // --- MIDI события ---

    /**
     * Находит событие по уникальной тройке (trackId, patternId, eventId).
     * Это правильная идентификация события при наличии нескольких паттернов.
     */
    [[nodiscard]] MidiEvent* findEvent(
            std::uint32_t trackId,
            std::uint32_t patternId,
            std::uint32_t eventId) noexcept;

    [[nodiscard]] const MidiEvent* findEvent(
            std::uint32_t trackId,
            std::uint32_t patternId,
            std::uint32_t eventId) const noexcept;

private:
    std::vector<Track*> tracks_;
    std::vector<Pattern*> patterns_;
    std::uint32_t nextTrackId_{1};
    std::uint32_t nextPatternId_{1};
};

} // namespace mozart
