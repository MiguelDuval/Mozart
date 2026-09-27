#include "KeyContext.h"

namespace mozart::musical {

KeyContext::KeyContext(
        const KeyScale& initialManualKeyScale,
        const double minimumAudioConfidence,
        const std::size_t requiredAudioObservations) noexcept
    : manualKeyScale_(
              initialManualKeyScale.isValid()
                      ? initialManualKeyScale
                      : KeyScale{6, Scale::NaturalMinor}),
      resolvedKeyScale_(manualKeyScale_),
      audioFilter_(minimumAudioConfidence, requiredAudioObservations) {}

void KeyContext::setManualKeyScale(const KeyScale& keyScale) {
    if (!keyScale.isValid()) {
        return;
    }

    std::lock_guard<std::mutex> lock(mutex_);
    manualKeyScale_ = keyScale;
    if (source_ == KeyContextSource::Manual) {
        resolvedKeyScale_ = keyScale;
    }
}

void KeyContext::setSource(const KeyContextSource source) noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    source_ = source;

    if (source_ == KeyContextSource::Manual) {
        resolvedKeyScale_ = manualKeyScale_;
        return;
    }

    // Switching to Audio never makes the resolved key invalid. Until the
    // filter has a stable audio estimate, keep the last resolved/manual key.
    const auto audio = audioFilter_.snapshot();
    if (audio.hasStableKey && audio.keyScale.isValid()) {
        resolvedKeyScale_ = audio.keyScale;
    }
}

void KeyContext::updateAudioDetection(
        const AudioKeyDetectionResult& result) noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    audioFilter_.update(result);

    if (source_ != KeyContextSource::Audio) {
        return;
    }

    const auto audio = audioFilter_.snapshot();
    if (audio.hasStableKey && audio.keyScale.isValid()) {
        resolvedKeyScale_ = audio.keyScale;
    }
}

void KeyContext::resetAudio() noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    audioFilter_.reset();

    if (source_ == KeyContextSource::Audio) {
        resolvedKeyScale_ = manualKeyScale_;
    }
}

KeyContextSource KeyContext::source() const noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    return source_;
}

KeyScale KeyContext::resolvedKeyScale() const noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    return resolvedKeyScale_;
}

KeyContextSnapshot KeyContext::snapshot() const noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    return KeyContextSnapshot{
        source_,
        resolvedKeyScale_,
        manualKeyScale_,
        audioFilter_.snapshot()
    };
}

} // namespace mozart::musical
