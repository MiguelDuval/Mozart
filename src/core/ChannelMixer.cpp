#include "ChannelMixer.h"

#include <algorithm>
#include <cmath>

namespace mozart {

ChannelMixer::ChannelMixer() = default;

void ChannelMixer::addTrack(Track* track) {
    if (track == nullptr) {
        return;
    }
    if (trackCount_ == trackCapacity_) {
        const std::size_t newCapacity = trackCapacity_ == 0 ? 4 : trackCapacity_ * 2;
        Track** newTracks = new Track*[newCapacity];
        for (std::size_t i = 0; i < trackCount_; ++i) {
            newTracks[i] = tracks_[i];
        }
        delete[] tracks_;
        tracks_ = newTracks;
        trackCapacity_ = newCapacity;
    }
    tracks_[trackCount_++] = track;
}

void ChannelMixer::removeTrack(Track* track) {
    for (std::size_t i = 0; i < trackCount_; ++i) {
        if (tracks_[i] == track) {
            tracks_[i] = tracks_[trackCount_ - 1];
            --trackCount_;
            return;
        }
    }
}

void ChannelMixer::panCoefficients(float pan, float& leftGain, float& rightGain) noexcept {
    // Equal Power панорамирование: при pan=0 оба канала имеют gain=sqrt(0.5) ≈ 0.707
    const float angle = (pan + 1.0f) * 3.14159265358979323846f / 4.0f; // 0 .. pi/2
    leftGain = std::cos(angle);
    rightGain = std::sin(angle);
}

void ChannelMixer::process(const float* samples_in, float* samples_out, std::size_t frameCount) noexcept {
    // Очищаем выходной буфер
    for (std::size_t i = 0; i < frameCount * 2; ++i) {
        samples_out[i] = 0.0f;
    }

    // Смешиваем каждый трек с его level и pan
    for (std::size_t t = 0; t < trackCount_; ++t) {
        Track* track = tracks_[t];
        if (track == nullptr || track->isMuted()) {
            continue;
        }

        const float level = track->level();
        if (level <= 0.0f) {
            continue;
        }

        const float pan = track->pan();
        float leftGain, rightGain;
        panCoefficients(pan, leftGain, rightGain);

        const float lGain = level * leftGain;
        const float rGain = level * rightGain;

        for (std::size_t i = 0; i < frameCount; ++i) {
            // samples_in может быть моно или стерео. Берём один источник на трек.
            const float sample = samples_in[i]; // моно источник
            samples_out[i * 2] += sample * lGain;     // левый канал
            samples_out[i * 2 + 1] += sample * rGain; // правый канал
        }
    }
}

std::vector<ChannelMixer::TrackSnapshot> ChannelMixer::captureSnapshots() const noexcept {
    std::vector<TrackSnapshot> snapshots;
    snapshots.reserve(trackCount_);
    for (std::size_t i = 0; i < trackCount_; ++i) {
        Track* track = tracks_[i];
        if (track != nullptr) {
            snapshots.push_back(TrackSnapshot{
                track->id(),
                track->level(),
                track->pan(),
            });
        }
    }
    return snapshots;
}

} // namespace mozart
