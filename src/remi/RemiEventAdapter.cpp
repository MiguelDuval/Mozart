#include "RemiEventAdapter.h"
#include "GenerationTypes.h"

#include <algorithm>
#include <cmath>
#include <chrono>
#include <limits>
#include <type_traits>
#include <utility>

namespace mozart::remi {

RemiEventAdapter::RemiEventAdapter(const RemiDecoderConfig& config) noexcept
    : config_(config) {}

RemiEventAdapter::RemiEventAdapter(const RemiDecoderConfig& config,
                                    std::shared_ptr<BpeTokenizer> tokenizer) noexcept
    : config_(config), tokenizer_(std::move(tokenizer)) {}

std::uint32_t RemiEventAdapter::positionBinToTicks(std::uint32_t bin) const noexcept {
    if (config_.positionResolution == 0 ||
        config_.ticksPerBeat % config_.positionResolution != 0) {
        return std::numeric_limits<std::uint32_t>::max();
    }
    const auto ticksPerPosition = config_.ticksPerBeat / config_.positionResolution;
    const auto ticks = static_cast<std::uint64_t>(bin) * ticksPerPosition;
    if (ticks > std::numeric_limits<std::uint32_t>::max()) {
        return std::numeric_limits<std::uint32_t>::max();
    }
    return static_cast<std::uint32_t>(ticks);
}

double RemiEventAdapter::tempoBinToBpm(std::uint8_t bin) const noexcept {
    if (config_.numTempos <= 1) return config_.tempoMin;
    return config_.tempoMin +
        (static_cast<double>(bin) * (config_.tempoMax - config_.tempoMin)) /
        (config_.numTempos - 1);
}

std::pair<PatternProposal, RemiDecodeReport> RemiEventAdapter::decodeEventsToProposal(
        const std::vector<RemiEvent>& events,
        const GenerationRequest& request,
        const std::string& providerId,
        const std::string& modelId) const noexcept {

    auto startTime = std::chrono::high_resolution_clock::now();

    PatternProposal proposal;
    proposal.providerId = providerId;
    proposal.modelId = modelId;
    if (request.seed.has_value()) proposal.seed = request.seed.value();

    std::uint32_t currentTick = 0;
    std::int64_t currentBar = -1;
    std::uint8_t currentVelocity = 64;
    bool hasTempo = false;
    bool hasTimeSignature = false;
    std::vector<PatternEvent> events_out;
    std::size_t droppedTokens = 0;
    std::vector<std::string> warnings;
    std::optional<std::size_t> durationTargetIndex;

    for (std::size_t i = 0; i < events.size(); ++i) {
        if (events_out.size() >= config_.maxEvents) {
            warnings.push_back("Truncated at max events: " + std::to_string(config_.maxEvents));
            droppedTokens += events.size() - i;
            break;
        }

        if (currentBar >= static_cast<std::int64_t>(config_.maxBars)) {
            warnings.push_back("Truncated at max bars: " + std::to_string(config_.maxBars));
            droppedTokens += events.size() - i;
            break;
        }

        const auto& event = events[i];

        std::visit([&](const auto& e) {
            using T = std::decay_t<decltype(e)>;

            if constexpr (std::is_same_v<T, RemiNoteOnEvent>) {
                // A pitch starts a note-token group. MidiTok may then emit
                // Velocity and Duration events for this exact note.
                durationTargetIndex.reset();
                if (e.pitch < config_.pitchMin || e.pitch > config_.pitchMax) {
                    warnings.push_back("Pitch out of range: " + std::to_string(e.pitch));
                    droppedTokens++;
                    return;
                }
                if (e.track >= config_.maxTracks) {
                    warnings.push_back("Track index out of range: " + std::to_string(e.track));
                    droppedTokens++;
                    return;
                }

                const double defaultTicks =
                    config_.defaultNoteDurationBeats * static_cast<double>(config_.ticksPerBeat);
                if (!std::isfinite(defaultTicks) || defaultTicks < 1.0 ||
                    defaultTicks > static_cast<double>(std::numeric_limits<std::uint32_t>::max())) {
                    warnings.push_back("Default note duration is outside supported tick range");
                    droppedTokens++;
                    return;
                }

                const std::uint64_t absolutePosition =
                    static_cast<std::uint64_t>(currentTick) + e.position;
                if (absolutePosition > static_cast<std::uint64_t>(std::numeric_limits<std::uint32_t>::max())) {
                    warnings.push_back("Note position exceeds supported tick range");
                    droppedTokens++;
                    return;
                }

                NoteEvent note;
                note.pitch = e.pitch;
                note.velocity = e.velocity != 0 ? e.velocity : currentVelocity;
                note.position = static_cast<std::uint32_t>(absolutePosition);
                note.duration = static_cast<std::uint32_t>(std::llround(defaultTicks));
                note.channel = 0;
                note.track = e.track;

                events_out.push_back(note);
                durationTargetIndex = events_out.size() - 1;
                currentTick = static_cast<std::uint32_t>(absolutePosition);
            }
            else if constexpr (std::is_same_v<T, RemiPositionEvent>) {
                durationTargetIndex.reset();
                if (currentBar < 0) {
                    currentBar = 0;
                }
                const auto positionTicks = positionBinToTicks(e.position);
                const std::uint64_t barStart =
                    static_cast<std::uint64_t>(currentBar) * config_.ticksPerBar;
                const std::uint64_t absolutePosition = barStart + positionTicks;
                if (positionTicks == std::numeric_limits<std::uint32_t>::max() ||
                    positionTicks >= config_.ticksPerBar ||
                    absolutePosition > std::numeric_limits<std::uint32_t>::max()) {
                    warnings.push_back("Position token exceeds supported bar/tick range");
                    droppedTokens++;
                    return;
                }
                currentTick = static_cast<std::uint32_t>(absolutePosition);
            }
            else if constexpr (std::is_same_v<T, RemiBarEvent>) {
                durationTargetIndex.reset();
                if (e.barNumber.has_value()) {
                    currentBar = static_cast<std::int64_t>(*e.barNumber);
                } else {
                    currentBar = currentBar < 0 ? 0 : currentBar + 1;
                }
                const std::uint64_t barStart =
                    static_cast<std::uint64_t>(currentBar) * config_.ticksPerBar;
                if (barStart > std::numeric_limits<std::uint32_t>::max()) {
                    warnings.push_back("Bar token exceeds supported tick range");
                    droppedTokens++;
                    return;
                }
                currentTick = static_cast<std::uint32_t>(barStart);
            }
            else if constexpr (std::is_same_v<T, RemiTempoEvent>) {
                durationTargetIndex.reset();
                if (!hasTempo) {
                    TempoEvent te;
                    te.position = currentTick;
                    te.bpm = e.bpm;
                    events_out.insert(events_out.begin(), te);
                    hasTempo = true;
                }
            }
            else if constexpr (std::is_same_v<T, RemiTimeSignatureEvent>) {
                durationTargetIndex.reset();
                if (!hasTimeSignature) {
                    TimeSignatureEvent tse;
                    tse.position = currentTick;
                    tse.numerator = e.numerator;
                    tse.denominator = e.denominator;
                    const std::size_t insertIndex = hasTempo ? 1 : 0;
                    events_out.insert(events_out.begin() + insertIndex, tse);
                    hasTimeSignature = true;
                }
            }
            else if constexpr (std::is_same_v<T, RemiProgramEvent>) {
                durationTargetIndex.reset();
                if (e.track < config_.maxTracks) {
                    ProgramChangeEvent pce;
                    pce.position = currentTick;
                    pce.channel = e.track % 16;
                    pce.program = e.program;
                    events_out.push_back(pce);
                } else {
                    warnings.push_back("Program event track index is out of range");
                    droppedTokens++;
                }
            }
            else if constexpr (std::is_same_v<T, RemiVelocityEvent>) {
                // MidiTok labels Velocity tokens with the quantized MIDI value
                // itself (Velocity_127 means velocity 127), not a bin index.
                currentVelocity = e.velocity;
                if (durationTargetIndex.has_value() &&
                    *durationTargetIndex < events_out.size()) {
                    if (auto* note = std::get_if<NoteEvent>(&events_out[*durationTargetIndex])) {
                        note->velocity = e.velocity;
                    }
                }
            }
            else if constexpr (std::is_same_v<T, RemiDurationEvent>) {
                if (e.resolution == 0 || !std::isfinite(e.beats) || e.beats < 0.0 ||
                    e.subdivision >= e.resolution) {
                    warnings.push_back("Duration token has invalid beats/subdivision/resolution");
                    droppedTokens++;
                    durationTargetIndex.reset();
                    return;
                }
                if (!durationTargetIndex.has_value() ||
                    *durationTargetIndex >= events_out.size()) {
                    warnings.push_back("Duration token has no immediately preceding note");
                    droppedTokens++;
                    durationTargetIndex.reset();
                    return;
                }

                const double totalBeats =
                    e.beats + static_cast<double>(e.subdivision) /
                                  static_cast<double>(e.resolution);
                const long double durationTicks =
                    static_cast<long double>(totalBeats) * config_.ticksPerBeat;
                if (!std::isfinite(totalBeats) || durationTicks < 1.0L ||
                    durationTicks > std::numeric_limits<std::uint32_t>::max()) {
                    warnings.push_back("Duration token exceeds supported tick range");
                    droppedTokens++;
                    durationTargetIndex.reset();
                    return;
                }
                auto* note = std::get_if<NoteEvent>(&events_out[*durationTargetIndex]);
                if (note == nullptr) {
                    warnings.push_back("Duration token target is not a note");
                    droppedTokens++;
                } else {
                    note->duration = static_cast<std::uint32_t>(std::llround(durationTicks));
                }
                durationTargetIndex.reset();
            }
        }, event);
    }

    proposal.events = std::move(events_out);

    std::uint64_t maxPos = 0;
    for (const auto& event : proposal.events) {
        std::uint64_t pos = 0;
        std::visit([&pos](const auto& e) { pos = e.position; }, event);
        if (const auto* note = std::get_if<NoteEvent>(&event)) {
            pos += note->duration;
        }
        maxPos = std::max(maxPos, pos);
    }
    if (maxPos > std::numeric_limits<std::uint32_t>::max()) {
        warnings.push_back("Pattern length exceeds supported tick range");
        droppedTokens++;
        proposal.clear();
        RemiDecodeReport report;
        report.message = "Pattern length exceeds supported tick range";
        report.processedTokens = events.size();
        report.droppedTokens = droppedTokens;
        report.warnings = std::move(warnings);
        return {std::move(proposal), std::move(report)};
    }
    proposal.totalTicks = std::max(static_cast<std::uint32_t>(maxPos), std::uint32_t(480));
    proposal.trackCount = 1;

    auto endTime = std::chrono::high_resolution_clock::now();
    proposal.generationTime = std::chrono::duration_cast<std::chrono::nanoseconds>(endTime - startTime);

    RemiDecodeReport report;
    report.message = "Decoded " + std::to_string(proposal.events.size()) + " events";
    report.processedTokens = events.size();
    report.droppedTokens = droppedTokens;
    report.warnings = std::move(warnings);

    return {proposal, report};
}
std::pair<PatternProposal, RemiDecodeReport> RemiEventAdapter::decodeTokensToProposal(
        const std::vector<std::uint32_t>& tokenIds,
        const GenerationRequest& request,
        const std::string& providerId,
        const std::string& modelId) const noexcept {

    if (!tokenizer_) {
        PatternProposal empty;
        RemiDecodeReport report;
        report.message = "No tokenizer available";
        return {empty, report};
    }

    auto decoded = tokenizer_->decodeTokens(tokenIds);

    std::vector<RemiEvent> remiEvents;
    for (const auto& name : decoded) {
        auto event = tokenNameToEvent(name);
        if (event.has_value()) {
            remiEvents.push_back(*event);
        }
    }

    return decodeEventsToProposal(remiEvents, request, providerId, modelId);
}

std::optional<PatternEvent> RemiEventAdapter::convertEvent(
        const RemiEvent& event, std::uint32_t currentTick, std::uint8_t currentTrack,
        std::uint8_t currentVelocity) const noexcept {
    (void)event;
    (void)currentTick;
    (void)currentTrack;
    (void)currentVelocity;
    return std::nullopt;
}

std::optional<RemiEvent> RemiEventAdapter::tokenNameToEvent(const std::string& tokenName) const noexcept {
    if (tokenName.rfind("Pitch_", 0) == 0) {
        try {
            std::uint8_t pitch = static_cast<std::uint8_t>(std::stoi(tokenName.substr(6)));
            return RemiNoteOnEvent{pitch, 64, 0, 0};
        } catch (...) { return std::nullopt; }
    }
    if (tokenName == "Bar_None") {
        return RemiBarEvent{std::nullopt};
    }
    if (tokenName.rfind("Position_", 0) == 0) {
        try {
            std::uint32_t pos = static_cast<std::uint32_t>(std::stoi(tokenName.substr(9)));
            return RemiPositionEvent{pos};
        } catch (...) { return std::nullopt; }
    }
    if (tokenName.rfind("Velocity_", 0) == 0) {
        try {
            std::uint8_t vel = static_cast<std::uint8_t>(std::stoi(tokenName.substr(9)));
            return RemiVelocityEvent{vel};
        } catch (...) { return std::nullopt; }
    }
    if (tokenName.rfind("Tempo_", 0) == 0) {
        try {
            double bpm = std::stod(tokenName.substr(6));
            return RemiTempoEvent{bpm};
        } catch (...) { return std::nullopt; }
    }
    if (tokenName.rfind("Duration_", 0) == 0) {
        try {
            const std::string body = tokenName.substr(9);
            const std::size_t dot1 = body.find('.');
            const std::size_t dot2 = body.find('.', dot1 + 1);
            if (dot1 == std::string::npos || dot2 == std::string::npos) {
                return std::nullopt;
            }
            RemiDurationEvent dur;
            dur.beats = std::stod(body.substr(0, dot1));
            dur.subdivision = static_cast<std::uint32_t>(std::stoul(body.substr(dot1 + 1, dot2 - dot1 - 1)));
            dur.resolution = static_cast<std::uint32_t>(std::stoul(body.substr(dot2 + 1)));
            return dur;
        } catch (...) { return std::nullopt; }
    }
    return std::nullopt;
}

} // namespace mozart::remi


