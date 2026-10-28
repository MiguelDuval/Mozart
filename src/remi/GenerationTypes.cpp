#include "GenerationTypes.h"

#include <algorithm>
#include <cmath>
#include <sstream>
#include <type_traits>
#include <utility>

namespace mozart::remi {

bool PatternProposal::isValid() const noexcept {
    return PatternProposalValidator{}.validate(*this).isOk();
}

std::optional<std::string> PatternProposal::validationError() const noexcept {
    const auto report = PatternProposalValidator{}.validate(*this);
    if (report.isOk()) {
        return std::nullopt;
    }
    return report.message;
}

std::vector<NoteEvent> PatternProposal::notes() const noexcept {
    std::vector<NoteEvent> result;
    for (const auto& event : events) {
        if (const auto* note = std::get_if<NoteEvent>(&event)) {
            result.push_back(*note);
        }
    }
    return result;
}

std::optional<TempoEvent> PatternProposal::firstTempo() const noexcept {
    for (const auto& event : events) {
        if (const auto* tempo = std::get_if<TempoEvent>(&event)) {
            return *tempo;
        }
    }
    return std::nullopt;
}

std::optional<TimeSignatureEvent> PatternProposal::firstTimeSignature() const noexcept {
    for (const auto& event : events) {
        if (const auto* signature = std::get_if<TimeSignatureEvent>(&event)) {
            return *signature;
        }
    }
    return std::nullopt;
}

void PatternProposal::clear() noexcept {
    providerId.clear();
    modelId.clear();
    seed = 0;
    generationTime = std::chrono::nanoseconds{0};
    events.clear();
    totalTicks = 0;
    trackCount = 1;
    warnings.clear();
    truncated = false;
}

std::string ValidationReport::toString() const noexcept {
    std::ostringstream out;
    out << "ValidationResult: ";
    switch (result) {
        case ValidationResult::Ok: out << "Ok"; break;
        case ValidationResult::EmptyProposal: out << "EmptyProposal"; break;
        case ValidationResult::TooManyEvents: out << "TooManyEvents"; break;
        case ValidationResult::InvalidPitch: out << "InvalidPitch"; break;
        case ValidationResult::InvalidVelocity: out << "InvalidVelocity"; break;
        case ValidationResult::InvalidPosition: out << "InvalidPosition"; break;
        case ValidationResult::InvalidDuration: out << "InvalidDuration"; break;
        case ValidationResult::InvalidChannel: out << "InvalidChannel"; break;
        case ValidationResult::UnsupportedEvent: out << "UnsupportedEvent"; break;
        case ValidationResult::ExceedsMaxTicks: out << "ExceedsMaxTicks"; break;
        case ValidationResult::ProviderError: out << "ProviderError"; break;
    }
    if (!message.empty()) {
        out << " - " << message;
    }
    if (offendingEventIndex > 0) {
        out << " (event index: " << offendingEventIndex << ")";
    }
    return out.str();
}

ValidationReport PatternProposalValidator::validate(
        const PatternProposal& proposal) const noexcept {
    if (proposal.events.empty()) {
        return {ValidationResult::EmptyProposal, "Proposal has no events"};
    }
    if (proposal.events.size() > limits_.maxEvents) {
        return {
            ValidationResult::TooManyEvents,
            "Proposal event count exceeds configured maximum",
            limits_.maxEvents
        };
    }
    if (proposal.totalTicks == 0) {
        return {ValidationResult::InvalidPosition, "Proposal totalTicks is zero"};
    }
    if (proposal.totalTicks > limits_.maxTicks) {
        return {
            ValidationResult::ExceedsMaxTicks,
            "Proposal length exceeds configured maximum"
        };
    }
    if (proposal.trackCount == 0 || proposal.trackCount > limits_.maxTracks) {
        return {ValidationResult::UnsupportedEvent, "Proposal track count is out of range"};
    }

    for (std::size_t i = 0; i < proposal.events.size(); ++i) {
        const auto& event = proposal.events[i];
        ValidationResult error = ValidationResult::Ok;
        const char* detail = "Valid";

        std::visit([&](const auto& item) {
            using T = std::decay_t<decltype(item)>;

            if (item.position > proposal.totalTicks) {
                error = ValidationResult::InvalidPosition;
                detail = "Event position exceeds proposal length";
                return;
            }

            if constexpr (std::is_same_v<T, NoteEvent>) {
                if (item.pitch > 127) {
                    error = ValidationResult::InvalidPitch;
                    detail = "Note pitch is outside MIDI range";
                } else if (item.velocity > 127) {
                    error = ValidationResult::InvalidVelocity;
                    detail = "Note velocity is outside MIDI range";
                } else if (item.duration == 0 ||
                           static_cast<std::uint64_t>(item.position) + item.duration >
                               proposal.totalTicks) {
                    error = ValidationResult::InvalidDuration;
                    detail = "Note duration is zero or extends beyond proposal length";
                } else if (item.channel >= limits_.maxChannels) {
                    error = ValidationResult::InvalidChannel;
                    detail = "Note channel is outside configured range";
                } else if (item.track >= limits_.maxTracks) {
                    error = ValidationResult::UnsupportedEvent;
                    detail = "Note track is outside configured range";
                }
            } else if constexpr (std::is_same_v<T, TempoEvent>) {
                if (!std::isfinite(item.bpm) || item.bpm <= 0.0 || item.bpm > 500.0) {
                    error = ValidationResult::UnsupportedEvent;
                    detail = "Tempo is outside supported range";
                }
            } else if constexpr (std::is_same_v<T, TimeSignatureEvent>) {
                if (item.numerator == 0 || item.denominator == 0 ||
                    (item.denominator & (item.denominator - 1)) != 0) {
                    error = ValidationResult::UnsupportedEvent;
                    detail = "Time signature is invalid";
                }
            } else if constexpr (std::is_same_v<T, ProgramChangeEvent>) {
                if (item.channel >= limits_.maxChannels || item.program > 127) {
                    error = ValidationResult::UnsupportedEvent;
                    detail = "Program change is outside supported MIDI range";
                }
            } else if constexpr (std::is_same_v<T, ControlChangeEvent>) {
                if (item.channel >= limits_.maxChannels ||
                    item.controller > 127 || item.value > 127) {
                    error = ValidationResult::UnsupportedEvent;
                    detail = "Control change is outside supported MIDI range";
                }
            }
        }, event);

        if (error != ValidationResult::Ok) {
            return {
                error,
                std::string(detail) + " at event index " + std::to_string(i),
                i
            };
        }
    }

    return {ValidationResult::Ok, "Valid"};
}

std::pair<PatternProposal, ValidationReport> PatternProposalValidator::sanitize(
        const PatternProposal& proposal) const noexcept {
    PatternProposal sanitized = proposal;
    sanitized.warnings.clear();

    if (sanitized.events.size() > limits_.maxEvents) {
        sanitized.events.resize(limits_.maxEvents);
        sanitized.truncated = true;
        sanitized.warnings.push_back("Truncated to configured maximum event count");
    }

    if (limits_.maxTicks == 0) {
        sanitized.clear();
        return {sanitized, {
            ValidationResult::ExceedsMaxTicks,
            "Configured maximum pattern length is zero"
        }};
    }

    if (sanitized.totalTicks == 0) {
        sanitized.totalTicks = std::min<std::uint32_t>(480, limits_.maxTicks);
        sanitized.warnings.push_back("Set missing pattern length to a safe minimum");
    } else if (sanitized.totalTicks > limits_.maxTicks) {
        sanitized.totalTicks = limits_.maxTicks;
        sanitized.truncated = true;
        sanitized.warnings.push_back("Clamped pattern length to configured maximum");
    }

    std::vector<PatternEvent> accepted;
    accepted.reserve(sanitized.events.size());
    for (std::size_t i = 0; i < sanitized.events.size(); ++i) {
        PatternProposal candidate = sanitized;
        candidate.events.assign(1, sanitized.events[i]);
        const auto report = validate(candidate);
        if (report.isOk()) {
            accepted.push_back(sanitized.events[i]);
        } else {
            sanitized.warnings.push_back(
                "Dropped invalid event at index " + std::to_string(i) +
                ": " + report.message
            );
        }
    }
    sanitized.events = std::move(accepted);

    if (sanitized.events.empty()) {
        return {sanitized, {
            ValidationResult::EmptyProposal,
            "No valid events remained after sanitization"
        }};
    }

    const auto finalReport = validate(sanitized);
    if (!finalReport.isOk()) {
        return {sanitized, finalReport};
    }
    return {sanitized, {
        ValidationResult::Ok,
        "Sanitized with " + std::to_string(sanitized.warnings.size()) + " warning(s)"
    }};
}

} // namespace mozart::remi
