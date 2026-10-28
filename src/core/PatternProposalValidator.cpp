#include "GenerationTypes.h"

#include <algorithm>
#include <sstream>

namespace mozart::generation {

//----------------------------------------------------------------------
// ValidationReport implementation
//----------------------------------------------------------------------

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
    if (!message.empty()) {
        oss << " - " << message;
    }
    if (offendingEventIndex > 0) {
        oss << " (event index: " << offendingEventIndex << ")";
    }
    return oss.str();
}

//----------------------------------------------------------------------
// PatternProposalValidator::validate
//----------------------------------------------------------------------

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
    }
    
    return {ValidationResult::Ok, "Valid"};
}

} // namespace mozart::generation