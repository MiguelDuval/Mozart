#include "RemiEventAdapter.h"
#include "GenerationTypes.h"

#include <algorithm>
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

std::uint8_t RemiEventAdapter::velocityBinToMidi(std::uint8_t bin) const noexcept {
    if (config_.numVelocities <= 1) return 64;
    return static_cast<std::uint8_t>(
        1 + (static_cast<std::uint32_t>(bin) * 126) / (config_.numVelocities - 1));
}

std::uint32_t RemiEventAdapter::positionBinToTicks(std::uint32_t bin) const noexcept {
    return bin * (config_.ticksPerBeat / 16);
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
    std::uint32_t currentBar = 0;
    std::uint8_t currentVelocity = 64;
    bool hasTempo = false;
    bool hasTimeSignature = false;
    std::vector<PatternEvent> events_out;
    std::size_t droppedTokens = 0;
    std::vector<std::string> warnings;

    std::uint32_t pendingDurationTicks = 0;
    bool hasPendingDuration = false;

    for (std::size_t i = 0; i < events.size(); ++i) {
        if (events_out.size() >= config_.maxEvents) {
            warnings.push_back("Truncated at max events: " + std::to_string(config_.maxEvents));
            droppedTokens += events.size() - i;
            break;
        }

        if (currentBar >= config_.maxBars) {
            warnings.push_back("Truncated at max bars: " + std::to_string(config_.maxBars));
            droppedTokens += events.size() - i;
            break;
        }

        const auto& event = events[i];

        std::visit([&](const auto& e) {
            using T = std::decay_t<decltype(e)>;

            if constexpr (std::is_same_v<T, RemiNoteOnEvent>) {
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

                std::uint32_t noteDuration = config_.ticksPerBeat / 4;
                if (hasPendingDuration) {
                    noteDuration = pendingDurationTicks;
                    hasPendingDuration = false;
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
                note.duration = noteDuration;
                note.channel = 0;
                note.track = e.track;

                events_out.push_back(note);
                currentTick = static_cast<std::uint32_t>(absolutePosition);
            }
            else if constexpr (std::is_same_v<T, RemiPositionEvent>) {
                currentTick = e.position;
            }
            else if constexpr (std::is_same_v<T, RemiBarEvent>) {
                currentBar = e.barNumber;
                currentTick = currentBar * config_.ticksPerBar;
            }
            else if constexpr (std::is_same_v<T, RemiTempoEvent>) {
                if (!hasTempo) {
                    TempoEvent te;
                    te.position = currentTick;
                    te.bpm = e.bpm;
                    events_out.insert(events_out.begin(), te);
                    hasTempo = true;
                }
            }
            else if constexpr (std::is_same_v<T, RemiTimeSignatureEvent>) {
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
                if (e.track < config_.maxTracks) {
                    ProgramChangeEvent pce;
                    pce.position = currentTick;
                    pce.channel = e.track % 16;
                    pce.program = e.program;
                    events_out.push_back(pce);
                }
            }
            else if constexpr (std::is_same_v<T, RemiVelocityEvent>) {
                currentVelocity = e.velocity;
            }
        }, event);
    }

    proposal.events = std::move(events_out);

    std::uint32_t maxPos = 0;
    for (const auto& event : proposal.events) {
        std::uint32_t pos = 0;
        std::visit([&pos](const auto& e) { pos = e.position; }, event);
        if (std::holds_alternative<NoteEvent>(event)) {
            pos += std::get<NoteEvent>(event).duration;
        }
        maxPos = std::max(maxPos, pos);
    }
    proposal.totalTicks = std::max(maxPos, std::uint32_t(480));
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
        return RemiBarEvent{0};
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
    return std::nullopt;
}

} // namespace mozart::remi


