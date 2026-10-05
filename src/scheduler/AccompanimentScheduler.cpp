#include "AccompanimentScheduler.h"

#include "core/MidiTypes.h"
#include "core/TransportMath.h"
#include "generation/DrumPatternGenerator.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <limits>

namespace mozart::scheduler {

namespace {

[[nodiscard]] std::uint64_t beatToTimestampNanos(
        const std::chrono::microseconds hostTime) noexcept {
    if (hostTime.count() <= 0) {
        return 0;
    }

    const auto micros = static_cast<std::uint64_t>(hostTime.count());
    constexpr std::uint64_t kNanosPerMicrosecond = 1'000ULL;

    if (micros > std::numeric_limits<std::uint64_t>::max() /
            kNanosPerMicrosecond) {
        return std::numeric_limits<std::uint64_t>::max();
    }

    return micros * kNanosPerMicrosecond;
}

} // namespace

AccompanimentScheduler::AccompanimentScheduler(
        clock::LinkClock& clock,
        MidiSendQueue& sendQueue)
    : clock_(clock),
      sendQueue_(sendQueue) {}

AccompanimentScheduler::~AccompanimentScheduler() {
    stop();
}

void AccompanimentScheduler::start() {
    std::lock_guard<std::mutex> lifecycleLock(lifecycleMutex_);
    if (running_.exchange(true)) {
        return;
    }

    worker_ = std::thread(&AccompanimentScheduler::run, this);
}

void AccompanimentScheduler::stop() {
    std::lock_guard<std::mutex> lifecycleLock(lifecycleMutex_);
    if (!running_.exchange(false)) {
        return;
    }

    wakeCondition_.notify_all();

    if (worker_.joinable()) {
        worker_.join();
    }

    launchBarStart_ = -1.0;
    nextBarIndex_ = 0;
    nextEventIndex_ = 0;
    activeRole_ = requestedRole_.load();
    activeDensity_ = requestedDensity_.load();
    activeAccent_ = requestedAccent_.load();
    activeSwing_ = requestedSwing_.load();

    std::lock_guard<std::mutex> lock(generatedPatternMutex_);
    pendingGeneratedPattern_.reset();
    activeGeneratedPattern_.reset();
    activeGeneratedPatternStartBeat_ = -1.0;
}

void AccompanimentScheduler::setArmed(const bool armed) noexcept {
    armed_.store(armed);
    wakeCondition_.notify_all();
}

bool AccompanimentScheduler::isArmed() const noexcept {
    return armed_.load();
}

void AccompanimentScheduler::setKeyScale(const musical::KeyScale& keyScale) {
    if (!keyScale.isValid()) {
        return;
    }

    std::lock_guard<std::mutex> lock(stateMutex_);
    requestedKeyScale_ = keyScale;
}

musical::KeyScale AccompanimentScheduler::keyScale() const {
    std::lock_guard<std::mutex> lock(stateMutex_);
    return requestedKeyScale_;
}

void AccompanimentScheduler::setRole(
        const AccompanimentRole role) noexcept {
    requestedRole_.store(role);
    requestedScene_.store(PerformanceScene::kCustomScene);
    wakeCondition_.notify_all();
}

AccompanimentRole AccompanimentScheduler::role() const noexcept {
    return requestedRole_.load();
}

void AccompanimentScheduler::setDensity(
        const generation::PatternDensity density) noexcept {
    requestedDensity_.store(density);
    requestedScene_.store(PerformanceScene::kCustomScene);
    wakeCondition_.notify_all();
}

generation::PatternDensity AccompanimentScheduler::density() const noexcept {
    return requestedDensity_.load();
}

void AccompanimentScheduler::setAccent(
        const generation::PatternAccent accent) noexcept {
    requestedAccent_.store(accent);
    requestedScene_.store(PerformanceScene::kCustomScene);
    wakeCondition_.notify_all();
}

generation::PatternAccent AccompanimentScheduler::accent() const noexcept {
    return requestedAccent_.load();
}

void AccompanimentScheduler::setSwing(
        const generation::PatternSwing swing) noexcept {
    requestedSwing_.store(swing);
    requestedScene_.store(PerformanceScene::kCustomScene);
    wakeCondition_.notify_all();
}

generation::PatternSwing AccompanimentScheduler::swing() const noexcept {
    return requestedSwing_.load();
}

void AccompanimentScheduler::setScene(
        const std::uint8_t sceneIndex) noexcept {
    requestedScene_.store(
            static_cast<std::uint8_t>(
                    sceneIndex % PerformanceScene::kSceneCount));
    wakeCondition_.notify_all();
}

std::uint8_t AccompanimentScheduler::scene() const noexcept {
    return requestedScene_.load();
}

void AccompanimentScheduler::requestMutation() noexcept {
    mutationRequested_.store(true);
    wakeCondition_.notify_all();
}

void AccompanimentScheduler::setNoteRepeat(
        const generation::NoteRepeatRate rate) noexcept {
    requestedNoteRepeat_.store(rate);
    requestedScene_.store(PerformanceScene::kCustomScene);
    wakeCondition_.notify_all();
}

generation::NoteRepeatRate AccompanimentScheduler::noteRepeat() const noexcept {
    return requestedNoteRepeat_.load();
}

void AccompanimentScheduler::setMacro(
        const MacroControl control,
        const std::uint8_t value) noexcept {
    const auto state = MacroControls::map(control, value);
    switch (control) {
        case MacroControl::Energy:
            macroEnergy_.store(value);
            requestedDensity_.store(state.density);
            requestedAccent_.store(state.accent);
            break;
        case MacroControl::Motion:
            macroMotion_.store(value);
            requestedSwing_.store(state.swing);
            requestedNoteRepeat_.store(state.noteRepeat);
            break;
    }

    requestedScene_.store(PerformanceScene::kCustomScene);
    wakeCondition_.notify_all();
}

std::uint8_t AccompanimentScheduler::macroEnergy() const noexcept {
    return macroEnergy_.load();
}

std::uint8_t AccompanimentScheduler::macroMotion() const noexcept {
    return macroMotion_.load();
}

[[nodiscard]] bool AccompanimentScheduler::queueGeneratedPattern(
        generation::PatternProposal proposal) {
    // The scheduler currently has a note-event playback path only.
    // Reject proposals carrying controls rather than silently dropping part
    // of an otherwise valid AI result. Control-event playback is a separate
    // semantic scheduling feature and must be added explicitly.
    if (!proposal.isWellFormed() ||
        proposal.noteEvents.empty() ||
        !proposal.controlEvents.empty() ||
        proposal.metadata.lengthBeats <= 0.0 ||
        !std::isfinite(proposal.metadata.lengthBeats)) {
        return false;
    }

    std::lock_guard<std::mutex> lock(generatedPatternMutex_);
    if (pendingGeneratedPattern_.has_value()) {
        return false;
    }

    pendingGeneratedPattern_ = std::move(proposal);
    wakeCondition_.notify_all();
    return true;
}

void AccompanimentScheduler::activatePendingGeneratedPattern(
        const double startBeat) {
    std::lock_guard<std::mutex> lock(generatedPatternMutex_);
    if (!pendingGeneratedPattern_.has_value()) {
        return;
    }

    activeGeneratedPattern_ = std::move(pendingGeneratedPattern_);
    activeGeneratedPatternStartBeat_ = startBeat;
}
void AccompanimentScheduler::applyRequestedScene() noexcept {
    const auto requestedScene = requestedScene_.load();
    if (requestedScene == PerformanceScene::kCustomScene) {
        activeScene_.store(PerformanceScene::kCustomScene);
        activeRole_ = requestedRole_.load();
        activeDensity_ = requestedDensity_.load();
        activeAccent_ = requestedAccent_.load();
        activeSwing_ = requestedSwing_.load();
        activeNoteRepeat_ = requestedNoteRepeat_.load();
        return;
    }

    const auto scene = PerformanceScene::preset(requestedScene);
    activeScene_.store(scene.index);
    activeRole_ = scene.role;
    activeDensity_ = scene.density;
    activeAccent_ = scene.accent;
    activeSwing_ = scene.swing;
    activeNoteRepeat_ = requestedNoteRepeat_.load();
    requestedRole_.store(scene.role);
    requestedDensity_.store(scene.density);
    requestedAccent_.store(scene.accent);
    requestedSwing_.store(scene.swing);
    seed_ = scene.seed;
}

void AccompanimentScheduler::run() {
    constexpr double kLookAheadSeconds = 0.032;
    constexpr double kEpsilon = 1.0e-9;
    constexpr std::chrono::milliseconds kPollPeriod{5};

    while (running_.load()) {
        if (!armed_.load() || !clock_.isEnabled()) {
            launchBarStart_ = -1.0;
            nextBarIndex_ = 0;
            nextEventIndex_ = 0;
        } else {
            const auto snapshot = clock_.captureAppSnapshot();

            // START/STOP Sync is intentionally not part of this stage. The
            // local START button arms accompaniment; Link supplies the shared
            // beat/tempo/phase timeline whether or not a remote peer is
            // publishing a start/stop state.
            if (!(snapshot.tempoBpm > 0.0) ||
                !std::isfinite(snapshot.tempoBpm)) {
                launchBarStart_ = -1.0;
                nextBarIndex_ = 0;
                nextEventIndex_ = 0;
            } else {
                // The musical cursor is deliberately independent of tempo.
                // A Link tempo change changes beat->host-time conversion, not
                // which note comes next. This prevents the sequence from
                // restarting or waiting for a new bar after a tempo change.
                if (launchBarStart_ < 0.0) {
                    // START is quantized once, at arming time. After launch,
                    // this reference beat is never recomputed from tempo.
                    launchBarStart_ =
                            timing::nextQuantizedBeat(
                                    snapshot.beat,
                                    snapshot.quantum);
                    nextBarIndex_ = 0;
                    nextEventIndex_ = 0;
                    applyRequestedScene();
                    activatePendingGeneratedPattern(launchBarStart_);
                    {
                        std::lock_guard<std::mutex> lock(stateMutex_);
                        activeKeyScale_ = requestedKeyScale_;
                    }
                }

                musical::KeyScale activeKeyScale;
                {
                    std::lock_guard<std::mutex> lock(stateMutex_);
                    activeKeyScale = activeKeyScale_;
                }

                const double lookAheadBeats =
                        std::max(
                                0.03125,
                                snapshot.tempoBpm * kLookAheadSeconds / 60.0);

                if (activeGeneratedPattern_.has_value()) {
                    const auto& proposal = *activeGeneratedPattern_;
                    const double patternEndBeat =
                            activeGeneratedPatternStartBeat_ +
                            proposal.metadata.lengthBeats;

                    while (nextEventIndex_ < proposal.noteEvents.size()) {
                        const double eventBeat =
                                activeGeneratedPatternStartBeat_ +
                                proposal.noteEvents[nextEventIndex_].startBeat;

                        if (eventBeat > snapshot.beat + lookAheadBeats + kEpsilon) {
                            break;
                        }

                        scheduleEvent(
                                snapshot,
                                proposal.noteEvents[nextEventIndex_],
                                eventBeat);
                        ++nextEventIndex_;
                    }

                    if (nextEventIndex_ >= proposal.noteEvents.size() &&
                        snapshot.beat + kEpsilon >= patternEndBeat) {
                        activeGeneratedPattern_.reset();
                        activeGeneratedPatternStartBeat_ = -1.0;
                        nextEventIndex_ = 0;
                        nextBarIndex_ = 0;
                        launchBarStart_ = patternEndBeat;
                        applyRequestedScene();

                        {
                            std::lock_guard<std::mutex> lock(stateMutex_);
                            activeKeyScale_ = requestedKeyScale_;
                        }
                    }
                } else {
                    const auto generatedEvents =
                            activeRole_ == AccompanimentRole::Arpeggio
                                    ? generation::ArpeggioGenerator::generateBar(
                                            activeKeyScale,
                                            4,
                                            seed_,
                                            0,
                                            activeDensity_,
                                            activeAccent_,
                                            activeSwing_)
                                    : (activeRole_ == AccompanimentRole::Drums
                                               ? generation::DrumPatternGenerator::generateBar(
                                                       seed_, activeDensity_)
                                               : generation::BassGenerator::generateBar(
                                                       activeKeyScale,
                                                       2,
                                                       seed_,
                                                       0,
                                                       activeDensity_,
                                                       activeAccent_,
                                                       activeSwing_));
                    const auto events =
                            generation::NoteRepeat::apply(
                                    generatedEvents,
                                    activeNoteRepeat_);

                    if (!events.empty() &&
                        snapshot.beat + kEpsilon >= launchBarStart_) {
                        while (nextEventIndex_ < events.size()) {
                            const double eventBeat =
                                    launchBarStart_ +
                                    static_cast<double>(nextBarIndex_) *
                                            snapshot.quantum +
                                    events[nextEventIndex_].startBeat;

                            if (eventBeat > snapshot.beat + lookAheadBeats + kEpsilon) {
                                break;
                            }

                            scheduleEvent(
                                    snapshot,
                                    events[nextEventIndex_],
                                    eventBeat);

                            ++nextEventIndex_;
                        }

                        if (nextEventIndex_ >= events.size()) {
                            nextEventIndex_ = 0;
                            ++nextBarIndex_;

                            applyRequestedScene();

                            if (mutationRequested_.exchange(false)) {
                                seed_ = seed_ == 0 ? 0x9E3779B9u : seed_;
                                seed_ ^= seed_ << 13;
                                seed_ ^= seed_ >> 17;
                                seed_ ^= seed_ << 5;
                                if (seed_ == 0) {
                                    seed_ = 0xA341316Cu;
                                }
                            }

                            const double nextCycleStartBeat =
                                    launchBarStart_ +
                                    static_cast<double>(nextBarIndex_) *
                                            snapshot.quantum;
                            activatePendingGeneratedPattern(nextCycleStartBeat);

                            {
                                std::lock_guard<std::mutex> lock(stateMutex_);
                                activeKeyScale_ = requestedKeyScale_;
                            }
                        }
                    }
                }
            }
        }

        std::unique_lock<std::mutex> lock(wakeMutex_);
        wakeCondition_.wait_for(
                lock,
                kPollPeriod,
                [this] { return !running_.load(); });
    }
}

void AccompanimentScheduler::scheduleEvent(
        const clock::LinkClockSnapshot& snapshot,
        const musical::MusicalNoteEvent& event,
        const double startBeat) {
    const double endBeat = startBeat + event.durationBeats;

    // If the scheduler wakes up slightly late, sending the current note with
    // an immediate monotonic timestamp is preferable to dropping a musical
    // step. Normal operation keeps events inside the look-ahead horizon.
    const auto nowTimestamp = beatToTimestampNanos(snapshot.hostTime);
    const auto desiredStartTimestamp =
            beatToTimestampNanos(clock_.hostTimeAtBeat(startBeat));
    const auto noteOnTimestamp =
            desiredStartTimestamp < nowTimestamp
                    ? nowTimestamp
                    : desiredStartTimestamp;

    const auto desiredNoteOffTimestamp =
            beatToTimestampNanos(clock_.hostTimeAtBeat(endBeat));
    const auto minimumNoteOffTimestamp =
            noteOnTimestamp + 1'000'000ULL;
    const auto noteOffTimestamp =
            desiredNoteOffTimestamp < minimumNoteOffTimestamp
                    ? minimumNoteOffTimestamp
                    : desiredNoteOffTimestamp;

    const auto noteOn =
            midi::noteOn(
                    event.channel,
                    event.note,
                    event.velocity,
                    noteOnTimestamp);

    const auto noteOff =
            midi::noteOff(
                    event.channel,
                    event.note,
                    0,
                    noteOffTimestamp);

    if (noteOn.has_value()) {
        (void) sendQueue_.enqueue(*noteOn);
    }

    if (noteOff.has_value()) {
        (void) sendQueue_.enqueue(*noteOff);
    }
}

} // namespace mozart::scheduler
