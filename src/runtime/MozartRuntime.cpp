#include "MozartRuntime.h"

#include "core/MidiTypes.h"

#include <chrono>

namespace mozart::runtime {

MozartRuntime::MozartRuntime(midi::MidiOutputTransport& midiOutput)
    : sendQueue_(midiOutput),
      scheduler_(linkClock_, sendQueue_) {}

MozartRuntime::~MozartRuntime() {
    stop();
}

void MozartRuntime::start() {
    if (started_) {
        return;
    }

    sendQueue_.start();
    scheduler_.start();
    started_ = true;
}

void MozartRuntime::stop() {
    if (!started_) {
        return;
    }

    // Reuse the normal accompaniment shutdown path while the MIDI send queue
    // is still alive, so an in-flight Note On cannot leave a stuck note.
    setAccompanimentEnabled(false);
    setLinkEnabled(false);

    sendQueue_.stop();
    started_ = false;
}

void MozartRuntime::setLinkEnabled(const bool enabled) noexcept {
    linkClock_.setEnabled(enabled);

    // Disabling Link should stop an armed accompanist, but must not invoke the
    // shutdown path twice when callers already stopped accompaniment first.
    if (!enabled && accompanimentEnabled()) {
        setAccompanimentEnabled(false);
    }
}

void MozartRuntime::setAccompanimentEnabled(const bool enabled) noexcept {
    if (enabled) {
        if (started_) {
            scheduler_.start();
        }
        scheduler_.setArmed(true);
        return;
    }

    scheduler_.setArmed(false);
    scheduler_.stop();
    sendQueue_.clearPending();

    // STOP must not leave a Note On sounding after its queued Note Off was
    // discarded. Send a transport-level panic after clearing future events.
    const auto now = std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
    const auto timestamp =
            static_cast<std::uint64_t>(now + 10'000'000LL);

    const auto allNotesOff = midi::controlChange(0, 123, 0, timestamp);
    const auto allSoundOff = midi::controlChange(0, 120, 0, timestamp);

    if (allNotesOff.has_value()) {
        (void) sendQueue_.enqueue(*allNotesOff);
    }
    if (allSoundOff.has_value()) {
        (void) sendQueue_.enqueue(*allSoundOff);
    }
}

void MozartRuntime::setKeyScale(const musical::KeyScale& keyScale) {
    if (!keyScale.isValid()) {
        return;
    }

    // A direct manual edit is the performer's explicit override from Audio
    // back to Manual. The scheduler receives the resolved domain context.
    keyContext_.setManualKeyScale(keyScale);
    keyContext_.setSource(musical::KeyContextSource::Manual);
    scheduler_.setKeyScale(keyContext_.resolvedKeyScale());
}

void MozartRuntime::setKeyContextSource(
        const musical::KeyContextSource source) noexcept {
    keyContext_.setSource(source);
    scheduler_.setKeyScale(keyContext_.resolvedKeyScale());
}

void MozartRuntime::updateAudioKeyDetection(
        const musical::AudioKeyDetectionResult& result) noexcept {
    const auto before = keyContext_.resolvedKeyScale();
    keyContext_.updateAudioDetection(result);
    const auto after = keyContext_.resolvedKeyScale();

    if (before.isValid() &&
        after.isValid() &&
        (before.rootPitchClass() != after.rootPitchClass() ||
         before.scale() != after.scale())) {
        scheduler_.setKeyScale(after);
    }
}

void MozartRuntime::resetAudioKeyContext() noexcept {
    keyContext_.resetAudio();
    scheduler_.setKeyScale(keyContext_.resolvedKeyScale());
}

void MozartRuntime::setAccompanimentRole(
        const scheduler::AccompanimentRole role) noexcept {
    scheduler_.setRole(role);
}

scheduler::AccompanimentRole MozartRuntime::accompanimentRole() const noexcept {
    return scheduler_.role();
}

void MozartRuntime::setPatternDensity(
        const generation::PatternDensity density) noexcept {
    scheduler_.setDensity(density);
}

generation::PatternDensity MozartRuntime::patternDensity() const noexcept {
    return scheduler_.density();
}

void MozartRuntime::setPatternAccent(
        const generation::PatternAccent accent) noexcept {
    scheduler_.setAccent(accent);
}

generation::PatternAccent MozartRuntime::patternAccent() const noexcept {
    return scheduler_.accent();
}

void MozartRuntime::setPatternSwing(
        const generation::PatternSwing swing) noexcept {
    scheduler_.setSwing(swing);
}

generation::PatternSwing MozartRuntime::patternSwing() const noexcept {
    return scheduler_.swing();
}

void MozartRuntime::setPerformanceScene(
        const std::uint8_t sceneIndex) noexcept {
    scheduler_.setScene(sceneIndex);
}

std::uint8_t MozartRuntime::performanceScene() const noexcept {
    return scheduler_.scene();
}

void MozartRuntime::requestPatternMutation() noexcept {
    scheduler_.requestMutation();
}

void MozartRuntime::setNoteRepeat(
        const generation::NoteRepeatRate rate) noexcept {
    scheduler_.setNoteRepeat(rate);
}

generation::NoteRepeatRate MozartRuntime::noteRepeat() const noexcept {
    return scheduler_.noteRepeat();
}

void MozartRuntime::setMacro(
        const scheduler::MacroControl control,
        const std::uint8_t value) noexcept {
    scheduler_.setMacro(control, value);
}

std::uint8_t MozartRuntime::macroEnergy() const noexcept {
    return scheduler_.macroEnergy();
}

std::uint8_t MozartRuntime::macroMotion() const noexcept {
    return scheduler_.macroMotion();
}

void MozartRuntime::handleMidiController(
        const midi::MidiShortMessage& message) noexcept {
    const auto command = controllerMapping_.resolve(message);
    if (command.action == midi::ControllerAction::None) {
        return;
    }

    const auto scaledIndex = [](const std::uint8_t value,
                                const std::uint8_t count) noexcept {
        return static_cast<std::uint8_t>(
                (static_cast<std::uint16_t>(value) * count) / 128u);
    };

    switch (command.action) {
        case midi::ControllerAction::Scene:
            setPerformanceScene(
                    static_cast<std::uint8_t>(
                            scaledIndex(command.value,
                                        scheduler::PerformanceScene::kSceneCount)));
            break;
        case midi::ControllerAction::Density:
            setPatternDensity(
                    command.value < 43
                            ? generation::PatternDensity::Sparse
                            : (command.value < 85
                                       ? generation::PatternDensity::Normal
                                       : generation::PatternDensity::Full));
            break;
        case midi::ControllerAction::Accent:
            setPatternAccent(
                    command.value < 43
                            ? generation::PatternAccent::Off
                            : (command.value < 85
                                       ? generation::PatternAccent::Mild
                                       : generation::PatternAccent::Strong));
            break;
        case midi::ControllerAction::Swing:
            setPatternSwing(
                    command.value < 43
                            ? generation::PatternSwing::Off
                            : (command.value < 85
                                       ? generation::PatternSwing::Light
                                       : generation::PatternSwing::Full));
            break;
        case midi::ControllerAction::NoteRepeat:
            setNoteRepeat(
                    command.value < 32
                            ? generation::NoteRepeatRate::Off
                            : (command.value < 64
                                       ? generation::NoteRepeatRate::Double
                                       : (command.value < 96
                                                  ? generation::NoteRepeatRate::Triple
                                                  : generation::NoteRepeatRate::Quadruple)));
            break;
        case midi::ControllerAction::Mutation:
            if (command.value >= 64) {
                requestPatternMutation();
            }
            break;
        case midi::ControllerAction::MacroEnergy:
            setMacro(scheduler::MacroControl::Energy, command.value);
            break;
        case midi::ControllerAction::MacroMotion:
            setMacro(scheduler::MacroControl::Motion, command.value);
            break;
        case midi::ControllerAction::None:
        default:
            break;
    }
}

bool MozartRuntime::sendDiagnosticNote() {
    start();

    using namespace std::chrono;
    const auto now = duration_cast<nanoseconds>(
            steady_clock::now().time_since_epoch()).count();
    const auto noteOnTimestamp =
            static_cast<std::uint64_t>(now + 50'000'000LL);
    const auto noteOffTimestamp =
            static_cast<std::uint64_t>(now + 300'000'000LL);

    const auto noteOn = midi::noteOn(0, 36, 100, noteOnTimestamp);
    const auto noteOff = midi::noteOff(0, 36, 0, noteOffTimestamp);

    if (!noteOn.has_value() || !noteOff.has_value()) {
        return false;
    }

    const bool onQueued = sendQueue_.enqueue(*noteOn);
    const bool offQueued = sendQueue_.enqueue(*noteOff);
    return onQueued && offQueued;
}

bool MozartRuntime::linkEnabled() const noexcept {
    return linkClock_.isEnabled();
}

bool MozartRuntime::accompanimentEnabled() const noexcept {
    return scheduler_.isArmed();
}

clock::LinkClockSnapshot MozartRuntime::captureLinkSnapshot() const {
    return linkClock_.captureAppSnapshot();
}

bool MozartRuntime::registerModel(generation::ModelCatalogEntry entry) {
    return modelCatalog_.registerModel(std::move(entry));
}

bool MozartRuntime::selectModel(const std::string_view modelId) {
    return modelCatalog_.selectModel(modelId);
}

void MozartRuntime::clearSelectedModel() noexcept {
    modelCatalog_.clearSelection();
}

std::string MozartRuntime::selectedModelId() const {
    return modelCatalog_.selectedModelId();
}

bool MozartRuntime::selectedModelIsPrivateExperimental() const noexcept {
    const auto modelId = modelCatalog_.selectedModelId();
    return !modelId.empty() && modelCatalog_.isPrivateExperimental(modelId);
}

bool MozartRuntime::selectedModelBackendAvailable() const noexcept {
    return modelCatalog_.resolveSelectedBackend() != nullptr;
}

musical::KeyContextSnapshot MozartRuntime::captureKeyContextSnapshot() const {
    return keyContext_.snapshot();
}

} // namespace mozart::runtime
