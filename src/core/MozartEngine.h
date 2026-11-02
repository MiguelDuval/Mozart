#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace mozart {

class Track;
class ChannelMixer;
class Metronome;

class MozartEngine final {
public:
    MozartEngine();
    ~MozartEngine();

    MozartEngine(const MozartEngine&) = delete;
    MozartEngine& operator=(const MozartEngine&) = delete;

    [[nodiscard]] std::string info() const;

    std::uint32_t addTrack(std::string name);
    void removeTrack(std::uint32_t trackId);
    [[nodiscard]] Track* track(std::uint32_t trackId) noexcept;
    [[nodiscard]] const Track* track(std::uint32_t trackId) const noexcept;
    [[nodiscard]] std::size_t trackCount() const noexcept;

    [[nodiscard]] ChannelMixer& channelMixer() noexcept;
    [[nodiscard]] const ChannelMixer& channelMixer() const noexcept;

    [[nodiscard]] Metronome& metronome() noexcept;
    [[nodiscard]] const Metronome& metronome() const noexcept;

private:
    std::vector<Track*> tracks_;
    std::uint32_t nextTrackId_{1};
    ChannelMixer* channelMixer_{nullptr};
    Metronome* metronome_{nullptr};
};

} // namespace mozart
