#include "Metronome.h"

#include <cmath>
#include <algorithm>

namespace mozart {

Metronome::Metronome() {
    secondsPerBeat_ = 60.0 / 120.0;
}

void Metronome::setBpm(float bpm) noexcept {
    bpm_.store(std::clamp(bpm, 20.0f, 300.0f), std::memory_order_relaxed);
    secondsPerBeat_ = 60.0 / bpm_.load(std::memory_order_relaxed);
}

float Metronome::bpm() const noexcept {
    return bpm_.load(std::memory_order_relaxed);
}

void Metronome::setTimeSignature(int numerator, int denominator) noexcept {
    if (numerator > 0) timeSigNum_.store(numerator, std::memory_order_relaxed);
    if (denominator > 0) timeSigDen_.store(denominator, std::memory_order_relaxed);
}

int Metronome::timeSignatureNumerator() const noexcept {
    return timeSigNum_.load(std::memory_order_relaxed);
}

int Metronome::timeSignatureDenominator() const noexcept {
    return timeSigDen_.load(std::memory_order_relaxed);
}

void Metronome::setSound(MetronomeSound sound) noexcept {
    sound_.store(sound, std::memory_order_relaxed);
}

MetronomeSound Metronome::sound() const noexcept {
    return sound_.load(std::memory_order_relaxed);
}

void Metronome::setVolume(float volume) noexcept {
    volume_.store(std::clamp(volume, 0.0f, 1.0f), std::memory_order_relaxed);
}

float Metronome::volume() const noexcept {
    return volume_.load(std::memory_order_relaxed);
}
void Metronome::setAccentVolume(float volume) noexcept {
    accentVolume_.store(std::clamp(volume, 0.0f, 2.0f), std::memory_order_relaxed);
}

float Metronome::accentVolume() const noexcept {
    return accentVolume_.load(std::memory_order_relaxed);
}

void Metronome::setEnabled(bool enabled) noexcept {
    enabled_.store(enabled, std::memory_order_relaxed);
}

bool Metronome::enabled() const noexcept {
    return enabled_.load(std::memory_order_relaxed);
}
void Metronome::setBeatPosition(double beatPosition) noexcept {
    beatPosition_.store(beatPosition, std::memory_order_relaxed);
    const int num = timeSigNum_.load(std::memory_order_relaxed);
    beatInBar_ = static_cast<int>(std::floor(beatPosition)) % num;
    if (beatInBar_ < 0) beatInBar_ += num;
    phase_ = 0.0;
    clickDuration_ = 0.0;
}

void Metronome::reset() noexcept {
    phase_ = 0.0;
    clickDuration_ = 0.0;
    beatInBar_ = 0;
}

float Metronome::generateClick(float t) noexcept {
    const float attack = 0.005f;
    const float decay = 0.05f;
    float envelope = 1.0f;
    if (t < attack) {
        envelope = t / attack;
    } else {
        envelope = std::exp(-(t - attack) / decay);
    }
    const float freq = 1000.0f;
    return std::sin(2.0f * 3.14159265358979323846f * freq * t) * envelope;
}

float Metronome::generateBeep(float t) noexcept {
    const float attack = 0.01f;
    const float decay = 0.1f;
    float envelope = 1.0f;
    if (t < attack) {
        envelope = t / attack;
    } else {
        envelope = std::exp(-(t - attack) / decay);
    }
    const float freq = 800.0f;
    return std::sin(2.0f * 3.14159265358979323846f * freq * t) * envelope;
}

float Metronome::generateWood(float t) noexcept {
    const float attack = 0.002f;
    const float decay = 0.03f;
    float envelope = 1.0f;
    if (t < attack) {
        envelope = t / attack;
    } else {
        envelope = std::exp(-(t - attack) / decay);
    }
    const float freq = 600.0f;
    return (std::sin(2.0f * 3.14159265358979323846f * freq * t) * 0.7f +
            std::sin(2.0f * 3.14159265358979323846f * freq * 2.0f * t) * 0.3f) * envelope;
}

bool Metronome::process(float sampleRate, double deltaSeconds, float& left, float& right) noexcept {
    left = 0.0f;
    right = 0.0f;

    if (!enabled_.load(std::memory_order_relaxed)) {
        return false;
    }

    const MetronomeSound sound = sound_.load(std::memory_order_relaxed);
    if (sound == MetronomeSound::None) {
        return false;
    }

    const float volume = volume_.load(std::memory_order_relaxed);
    if (volume <= 0.0f) {
        return false;
    }

    const int num = timeSigNum_.load(std::memory_order_relaxed);
    const float bpm = bpm_.load(std::memory_order_relaxed);
    const double spb = 60.0 / bpm;

    phase_ += deltaSeconds;

    bool pulseTriggered = false;
    while (phase_ >= spb) {
        phase_ -= spb;
        pulseTriggered = true;
        beatInBar_ = (beatInBar_ + 1) % num;
    }

    if (!pulseTriggered && clickDuration_ <= 0.0) {
        return false;
    }

    if (clickDuration_ > 0.0) {
        clickDuration_ -= deltaSeconds;
        const float t = static_cast<float>(std::max(0.0, -clickDuration_));

        float sample = 0.0f;
        switch (sound) {
            case MetronomeSound::Click:
                sample = generateClick(t);
                break;
            case MetronomeSound::Beep:
                sample = generateBeep(t);
                break;
            case MetronomeSound::Wood:
                sample = generateWood(t);
                break;
            case MetronomeSound::None:
                break;
        }

        float amp = volume;
        if (beatInBar_ == 0 && pulseTriggered) {
            amp *= accentVolume_.load(std::memory_order_relaxed);
        }

        left = sample * amp;
        right = sample * amp;

        if (clickDuration_ <= 0.0) {
            clickDuration_ = 0.0;
        }
        return true;
    }

    if (pulseTriggered) {
        clickDuration_ = 0.1;

        float sample = 0.0f;
        const float t = 0.0f;
        switch (sound) {
            case MetronomeSound::Click:
                sample = generateClick(t);
                break;
            case MetronomeSound::Beep:
                sample = generateBeep(t);
                break;
            case MetronomeSound::Wood:
                sample = generateWood(t);
                break;
            case MetronomeSound::None:
                break;
        }

        float amp = volume;
        if (beatInBar_ == 0) {
            amp *= accentVolume_.load(std::memory_order_relaxed);
        }

        left = sample * amp;
        right = sample * amp;
        return true;
    }

    return false;
}

} // namespace mozart


