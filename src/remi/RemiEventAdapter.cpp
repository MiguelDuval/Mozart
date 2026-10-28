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
                // The selected MusicMaker checkpoint is piano-only. Program_0 is
                // its expected acoustic-piano track marker, not a MIDI program
                // change to schedule. Reject other programs rather than silently
                // outputting notes with the wrong instrument.
                if (e.track >= config_.maxTracks) {
                    warnings.push_back("Program event track index is out of range");
                    droppedTokens++;
                } else if (e.program != 0) {
                    warnings.push_back("Unsupported instrument program for piano-only runtime: " +
                                       std::to_string(e.program));
                    droppedTokens++;
                }
            }
            else if constexpr (std::is_same_v<T, RemiControlChangeEvent>) {
                durationTargetIndex.reset();
                if (e.track >= config_.maxTracks || e.controller > 127 || e.value > 127) {
                    warnings.push_back("ControlChange event is outside supported range");
                    droppedTokens++;
                } else {
                    events_out.push_back(ControlChangeEvent{
                        currentTick,
                        static_cast<std::uint8_t>(e.track % 16),
                        e.controller,
                        e.value
                    });
                }
            }
            else if constexpr (std::is_same_v<T, RemiChordEvent>) {
                // Chord tokens are annotations in this REMI+ tokenizer. The
                // actual pitches are emitted independently and remain the
                // scheduled source of truth, so this metadata token is accepted.
                durationTargetIndex.reset();
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

    if (!report.isOk()) {
        proposal.clear();
        report.message = "REMI event stream rejected atomically";
        return {std::move(proposal), std::move(report)};
    }
    return {std::move(proposal), std::move(report)};
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
        report.processedTokens = tokenIds.size();
        report.droppedTokens = tokenIds.size();
        report.warnings.push_back(report.message);
        return {std::move(empty), std::move(report)};
    }

    const auto tokenReport = tokenizer_->decodeTokensWithReport(tokenIds);
    if (tokenReport.droppedTokenIds != 0) {
        PatternProposal empty;
        RemiDecodeReport report;
        report.message = "BPE token stream contains undecodable IDs";
        report.processedTokens = tokenIds.size();
        report.droppedTokens = tokenReport.droppedTokenIds;
        report.warnings = tokenReport.warnings;
        return {std::move(empty), std::move(report)};
    }

    std::vector<RemiEvent> remiEvents;
    remiEvents.reserve(tokenReport.tokenNames.size());
    for (const auto& name : tokenReport.tokenNames) {
        if (name == "PAD_None" || name == "BOS_None" || name == "MASK_None") {
            continue;
        }
        if (name == "EOS_None") {
            break;
        }

        const auto event = tokenNameToEvent(name);
        if (!event.has_value()) {
            PatternProposal empty;
            RemiDecodeReport report;
            report.message = "Unsupported REMI token: " + name;
            report.processedTokens = tokenIds.size();
            report.droppedTokens = 1;
            report.warnings.push_back(report.message);
            return {std::move(empty), std::move(report)};
        }
        remiEvents.push_back(*event);
    }

    auto [proposal, report] =
        decodeEventsToProposal(remiEvents, request, providerId, modelId);
    report.processedTokens = tokenIds.size();
    if (!report.isOk()) {
        proposal.clear();
        report.message = "REMI token stream rejected atomically";
    }
    return {std::move(proposal), std::move(report)};
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

std::optional<RemiEvent> RemiEventAdapter::tokenNameToEvent(
        const std::string& tokenName) const noexcept {
    const auto parseUnsigned = [](const std::string& text, const std::uint32_t maximum)
        -> std::optional<std::uint32_t> {
        try {
            std::size_t used = 0;
            const auto value = std::stoull(text, &used, 10);
            if (used != text.size() || value > maximum) return std::nullopt;
            return static_cast<std::uint32_t>(value);
        } catch (...) {
            return std::nullopt;
        }
    };

    // This experimental ONNX checkpoint is a piano model. Do not reinterpret
    // a drum-pitch token as a pitched piano note; reject it atomically below.
    if (tokenName.rfind("PitchDrum_", 0) == 0) return std::nullopt;
    if (tokenName.rfind("Pitch_", 0) == 0) {
        const auto pitch = parseUnsigned(tokenName.substr(6), 127);
        if (!pitch.has_value()) return std::nullopt;
        return RemiNoteOnEvent{static_cast<std::uint8_t>(*pitch), 64, 0, 0};
    }
    if (tokenName == "Bar_None") return RemiBarEvent{std::nullopt};

    if (tokenName.rfind("Position_", 0) == 0) {
        const auto position = parseUnsigned(tokenName.substr(9),
            std::numeric_limits<std::uint32_t>::max());
        if (!position.has_value()) return std::nullopt;
        return RemiPositionEvent{*position};
    }
    if (tokenName.rfind("Velocity_", 0) == 0) {
        const auto velocity = parseUnsigned(tokenName.substr(9), 127);
        if (!velocity.has_value()) return std::nullopt;
        return RemiVelocityEvent{static_cast<std::uint8_t>(*velocity)};
    }
    if (tokenName.rfind("Tempo_", 0) == 0) {
        try {
            const std::string value = tokenName.substr(6);
            std::size_t used = 0;
            const double bpm = std::stod(value, &used);
            if (used != value.size() || !std::isfinite(bpm) || bpm <= 0.0 || bpm > 500.0) {
                return std::nullopt;
            }
            return RemiTempoEvent{bpm};
        } catch (...) {
            return std::nullopt;
        }
    }
    if (tokenName.rfind("Duration_", 0) == 0) {
        try {
            const std::string body = tokenName.substr(9);
            const std::size_t dot1 = body.find('.');
            const std::size_t dot2 = dot1 == std::string::npos
                ? std::string::npos : body.find('.', dot1 + 1);
            if (dot1 == std::string::npos || dot2 == std::string::npos) return std::nullopt;

            const std::string beatsText = body.substr(0, dot1);
            std::size_t beatsUsed = 0;
            const double beats = std::stod(beatsText, &beatsUsed);
            const auto subdivision = parseUnsigned(
                body.substr(dot1 + 1, dot2 - dot1 - 1),
                std::numeric_limits<std::uint32_t>::max());
            const auto resolution = parseUnsigned(body.substr(dot2 + 1),
                std::numeric_limits<std::uint32_t>::max());
            if (beatsUsed != beatsText.size() || !std::isfinite(beats) || beats < 0.0 ||
                !subdivision.has_value() || !resolution.has_value() ||
                *resolution == 0 || *subdivision >= *resolution) return std::nullopt;
            return RemiDurationEvent{beats, *subdivision, *resolution};
        } catch (...) {
            return std::nullopt;
        }
    }
    if (tokenName.rfind("TimeSig_", 0) == 0) {
        const std::string value = tokenName.substr(8);
        const auto slash = value.find('/');
        if (slash == std::string::npos) return std::nullopt;
        const auto numerator = parseUnsigned(value.substr(0, slash), 255);
        const auto denominator = parseUnsigned(value.substr(slash + 1), 255);
        if (!numerator.has_value() || !denominator.has_value() ||
            *numerator == 0 || *denominator == 0 ||
            ((*denominator & (*denominator - 1U)) != 0)) return std::nullopt;
        return RemiTimeSignatureEvent{
            static_cast<std::uint8_t>(*numerator),
            static_cast<std::uint8_t>(*denominator)
        };
    }
    if (tokenName.rfind("Program_", 0) == 0) {
        const std::string value = tokenName.substr(8);
        try {
            std::size_t used = 0;
            const long program = std::stol(value, &used, 10);
            if (used != value.size() || program < -1 || program > 127) return std::nullopt;
            return RemiProgramEvent{static_cast<std::int16_t>(program), 0};
        } catch (...) {
            return std::nullopt;
        }
    }
    if (tokenName.rfind("ControlChange_", 0) == 0) {
        const std::string value = tokenName.substr(14);
        const auto separator = value.find('-');
        if (separator == std::string::npos) return std::nullopt;
        const auto controller = parseUnsigned(value.substr(0, separator), 127);
        const auto ccValue = parseUnsigned(value.substr(separator + 1), 127);
        if (!controller.has_value() || !ccValue.has_value()) return std::nullopt;
        return RemiControlChangeEvent{
            static_cast<std::uint8_t>(*controller),
            static_cast<std::uint8_t>(*ccValue),
            0
        };
    }
    if (tokenName.rfind("Chord_", 0) == 0) {
        const std::string value = tokenName.substr(6);
        const auto separator = value.find(':');
        if (separator == std::string::npos) {
            if (value.empty()) return std::nullopt;
            return RemiChordEvent{"", value};
        }
        if (separator == 0 || separator + 1 >= value.size()) return std::nullopt;
        return RemiChordEvent{
            value.substr(0, separator), value.substr(separator + 1)
        };
    }

    // Unknown token types fail closed in decodeTokensToProposal.
    return std::nullopt;
}

} // namespace mozart::remi


