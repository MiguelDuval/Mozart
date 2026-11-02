#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace mozart {

class Track;
class ChannelMixer;
class Metronome;
class Project;

/**
 * Движок Mozart — ядро аудио/MIDI инструмента.
 * Управляет проектами, треками, микшером каналов и метрономом.
 */
class MozartEngine final {
public:
    MozartEngine();
    ~MozartEngine();

    MozartEngine(const MozartEngine&) = delete;
    MozartEngine& operator=(const MozartEngine&) = delete;

    [[nodiscard]] std::string info() const;

    // --- Проект ---

    [[nodiscard]] Project& project() noexcept;
    [[nodiscard]] const Project& project() const noexcept;

    // --- Треки (делегируются проекту) ---

    std::uint32_t addTrack(std::string name);
    void removeTrack(std::uint32_t trackId);
    [[nodiscard]] Track* track(std::uint32_t trackId) noexcept;
    [[nodiscard]] const Track* track(std::uint32_t trackId) const noexcept;
    [[nodiscard]] std::size_t trackCount() const noexcept;

    // --- Микшер каналов ---

    [[nodiscard]] ChannelMixer& channelMixer() noexcept;
    [[nodiscard]] const ChannelMixer& channelMixer() const noexcept;

    // --- Метроном ---

    [[nodiscard]] Metronome& metronome() noexcept;
    [[nodiscard]] const Metronome& metronome() const noexcept;

private:
    Project* project_{nullptr};
    ChannelMixer* channelMixer_{nullptr};
    Metronome* metronome_{nullptr};
};

} // namespace mozart
