#include "GenerationTypes.h"

#include <algorithm>
#include <sstream>

namespace mozart::remi {

bool PatternProposal::isValid() const noexcept {
    if (events.empty()) return false;
    if (totalTicks == 0) return false;
    for (const auto& event : events) {
        std::uint32_t pos = 0;
        std::visit([&pos](const auto& e) { pos = e.position; }, event);
        if (pos > totalTicks) return false;
    }
    return true;
}

std::optional<std::string> PatternProposal::validationError() const noexcept {
    if (events.empty()) return "No events in proposal";
    if (totalTicks == 0) return "Total ticks is zero";
    for (std::size_t i = 0; i < events.size(); ++i) {
        std::uint32_t pos = 0;
        std::visit([&pos](const auto& e) { pos = e.position; }, events[i]);
        if (pos > totalTicks) {
            return "Event at index " + std::to_string(i) + " exceeds totalTicks";
        }
    }
    return std::nullopt;
}

std::vector<NoteEvent> PatternProposal::notes() const noexcept {
    std::vector<NoteEvent> result;
    result.reserve(events.size());
    for (const auto& event : events) {
        if (std::holds_alternative<NoteEvent>(event)) {
            result.push_back(std::get<NoteEvent>(event));
        }
    }
    return result;
}

std::optional<TempoEvent> PatternProposal::firstTempo() const noexcept {
    for (const auto& event : events) {
        if (std::holds_alternative<TempoEvent>(event)) {
            return std::get<TempoEvent>(event);
        }
    }
    return std::nullopt;
}

std::optional<TimeSignatureEvent> PatternProposal::firstTimeSignature() const noexcept {
    for (const auto& event : events) {
        if (std::holds_alternative<TimeSignatureEvent>(event)) {
std::string ValidationReport::toString() const noexcept {
    std::ostringstream oss;
    oss << "ValidationResult: ";
    switch (result) {
        case ValidationResult::Ok: oss << "Ok"; break;
        case ValidationResult::EmptyProposal: oss << "EmptyProposal"; break;
        case ValidationResult::TooManyEvents: oss << "TooManyEvents"; break;
        case ValidationResult::InvalidPitch: oss << "InvalidPitch"; break;
        case ValidationResult::InvalidVelocity: oss << "InvalidVelocity"; break;
        case ValidationResult::InvalidPosition: oss << "InvalidPosition"; break;
        case ValidationResult::InvalidDuration: oss << "InvalidDuration"; break;
        case ValidationResult::InvalidChannel: oss << "InvalidChannel"; break;
        case ValidationResult::UnsupportedEvent: oss << "UnsupportedEvent"; break;
        case ValidationResult::ExceedsMaxTicks: oss << "ExceedsMaxTicks"; break;
        case ValidationResult::ProviderError: oss << "ProviderError"; break;
    }
    if (!message.empty()) oss << " - " << message;
    if (offendingEventIndex > 0) oss << " (event index: " << offendingEventIndex << ")";
    return oss.str();
}

ValidationReport PatternProposalValidator::validate(const PatternProposal& proposal) const noexcept {
    if (proposal.events.empty()) {
        return {ValidationResult::EmptyProposal, "Proposal has no events"};
    }
    if (proposal.events.size() > limits_.maxEvents) {
        return {ValidationResult::TooManyEvents,
                "Proposal has " + std::to_string(proposal.events.size()) +
                " events, max is " + std::to_string(limits_.maxEvents),
                limits_.maxEvents};
    }
    if (proposal.totalTicks > limits_.maxTicks) {
        return {ValidationResult::ExceedsMaxTicks,
                "Proposal length " + std::to_string(proposal.totalTicks) +
                " ticks exceeds max " + std::to_string(limits_.maxTicks),
                0};
    }
    for (std::size_t i = 0; i < proposal.events.size(); ++i) {
        const auto& event = proposal.events[i];
        try {
            std::visit([&](const auto& e) {
                using T = std::decay_t<decltype(e)>;
                if constexpr (std::is_same_v<T, NoteEvent>) {
                    if (e.pitch > 127) throw ValidationResult::InvalidPitch;
                    if (e.velocity > 127) throw ValidationResult::InvalidVelocity;
                    if (e.position > proposal.totalTicks) throw ValidationResult::InvalidPosition;
                    if (e.duration == 0) throw ValidationResult::InvalidDuration;
                    if (e.channel >= limits_.maxChannels) throw ValidationResult::InvalidChannel;
                    if (e.track >= limits_.maxTracks) throw ValidationResult::UnsupportedEvent;
                } else if constexpr (std::is_same_v<T, TempoEvent>) {
                    if (e.position > proposal.totalTicks) throw ValidationResult::InvalidPosition;
                    if (e.bpm <= 0.0 || e.bpm > 500.0) throw ValidationResult::UnsupportedEvent;
                } else if constexpr (std::is_same_v<T, TimeSignatureEvent>) {
                    if (e.position > proposal.totalTicks) throw ValidationResult::InvalidPosition;
                    if (e.denominator == 0 || (e.denominator & (e.denominator - 1)) != 0) {
                        throw ValidationResult::UnsupportedEvent;
                    }
                } else if constexpr (std::is_same_v<T, ProgramChangeEvent>) {
                    if (e.position > proposal.totalTicks) throw ValidationResult::InvalidPosition;
                    if (e.channel >= limits_.maxChannels) throw ValidationResult::InvalidChannel;
                    if (e.program > 127) throw ValidationResult::UnsupportedEvent;
                } else if constexpr (std::is_same_v<T, ControlChangeEvent>) {
                    if (e.position > proposal.totalTicks) throw ValidationResult::InvalidPosition;
                    if (e.channel >= limits_.maxChannels) throw ValidationResult::InvalidChannel;
                    if (e.controller > 127 || e.value > 127) throw ValidationResult::UnsupportedEvent;
                }
            }, event);
        } catch (ValidationResult err) {
            return {err, "Validation failed at event index " + std::to_string(i), i};
        }
std::pair<PatternProposal, ValidationReport> PatternProposalValidator::sanitize(
        const PatternProposal& proposal) const noexcept {
    PatternProposal sanitized = proposal;
    sanitized.events.clear();
    sanitized.warnings.clear();
    sanitized.truncated = false;

    ValidationReport report = validate(proposal);
    if (report.isOk()) return {proposal, report};

    if (report.result == ValidationResult::TooManyEvents) {
        sanitized.events.assign(proposal.events.begin(),
                               proposal.events.begin() + limits_.maxEvents);
        sanitized.truncated = true;
        sanitized.warnings.push_back("Truncated to " + std::to_string(limits_.maxEvents) + " events");
        return {sanitized, {ValidationResult::Ok, "Truncated to fit limits"}};
    }

    if (report.result == ValidationResult::ExceedsMaxTicks) {
        sanitized.totalTicks = limits_.maxTicks;
        for (const auto& event : proposal.events) {
            std::uint32_t pos = 0;
            std::visit([&pos](const auto& e) { pos = e.position; }, event);
            if (pos <= limits_.maxTicks) sanitized.events.push_back(event);
        }
        sanitized.truncated = true;
        sanitized.warnings.push_back("Clamped to " + std::to_string(limits_.maxTicks) + " ticks");
        return {sanitized, {ValidationResult::Ok, "Clamped to fit limits"}};
    }

    for (std::size_t i = 0; i < proposal.events.size(); ++i) {
        const auto& event = proposal.events[i];
        bool valid = true;
        std::visit([&](const auto& e) {
            using T = std::decay_t<decltype(e)>;
            if constexpr (std::is_same_v<T, NoteEvent>) {
                if (e.pitch > 127 || e.velocity > 127 || e.position > limits_.maxTicks ||
                    e.duration == 0 || e.channel >= limits_.maxChannels ||
                    e.track >= limits_.maxTracks) valid = false;
            } else if constexpr (std::is_same_v<T, TempoEvent>) {
                if (e.position > limits_.maxTicks || e.bpm <= 0.0 || e.bpm > 500.0) valid = false;
            } else if constexpr (std::is_same_v<T, TimeSignatureEvent>) {
                if (e.position > limits_.maxTicks || e.denominator == 0 ||
                    (e.denominator & (e.denominator - 1)) != 0) valid = false;
            } else if constexpr (std::is_same_v<T, ProgramChangeEvent>) {
                if (e.position > limits_.maxTicks || e.channel >= limits_.maxChannels ||
                    e.program > 127) valid = false;
            } else if constexpr (std::is_same_v<T, ControlChangeEvent>) {
                if (e.position > limits_.maxTicks || e.channel >= limits_.maxChannels ||
                    e.controller > 127 || e.value > 127) valid = false;
            }
        }, event);
        if (valid) sanitized.events.push_back(event);
        else sanitized.warnings.push_back("Dropped invalid event at index " + std::to_string(i));
    }

    if (sanitized.events.empty()) {
        return {sanitized, {ValidationResult::EmptyProposal, "All events were invalid"}};
    }

    std::uint32_t maxPos = 0;
    for (const auto& event : sanitized.events) {
        std::uint32_t pos = 0;
        std::visit([&pos](const auto& e) { pos = e.position; }, event);
        maxPos = std::max(maxPos, pos);
    }
    sanitized.totalTicks = std::max(maxPos, std::uint32_t(480));
    return {sanitized, {ValidationResult::Ok, "Sanitized with " +
                        std::to_string(sanitized.warnings.size()) + " warnings"}};
}

    }
    return {ValidationResult::Ok, "Valid"};
}

            return std::get<TimeSignatureEvent>(event);
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
