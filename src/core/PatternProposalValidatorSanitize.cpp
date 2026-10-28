#include "GenerationTypes.h"

#include <algorithm>
#include <sstream>

namespace mozart::generation {

//----------------------------------------------------------------------
// PatternProposalValidator::sanitize
//----------------------------------------------------------------------

std::pair<PatternProposal, ValidationReport> PatternProposalValidator::sanitize(const PatternProposal& proposal) const noexcept {
    PatternProposal sanitized = proposal;
    sanitized.events.clear();
    sanitized.warnings.clear();
    sanitized.truncated = false;
    
    ValidationReport report = validate(proposal);
    if (report.isOk()) {
        // A valid proposal needs no filtering. Return its events intact; 'sanitized'
        // has its event list cleared above for the invalid-input filtering path.
        return {proposal, report};
    }
    
    // If too many events, truncate
    if (report.result == ValidationResult::TooManyEvents) {
        sanitized.events.assign(proposal.events.begin(), 
                               proposal.events.begin() + limits_.maxEvents);
        sanitized.truncated = true;
        sanitized.warnings.push_back("Truncated to " + std::to_string(limits_.maxEvents) + " events");
        return {sanitized, {ValidationResult::Ok, "Truncated to fit limits"}};
    }
    
    // If exceeds max ticks, clamp
    if (report.result == ValidationResult::ExceedsMaxTicks) {
        sanitized.totalTicks = limits_.maxTicks;
        for (const auto& event : proposal.events) {
            std::uint32_t pos = 0;
            std::visit([&pos](const auto& e) { pos = e.position; }, event);
            if (pos <= limits_.maxTicks) {
                sanitized.events.push_back(event);
            }
        }
        sanitized.truncated = true;
        sanitized.warnings.push_back("Clamped to " + std::to_string(limits_.maxTicks) + " ticks");
        return {sanitized, {ValidationResult::Ok, "Clamped to fit limits"}};
    }
    
    // For other errors, filter valid events
    for (std::size_t i = 0; i < proposal.events.size(); ++i) {
        const auto& event = proposal.events[i];
        bool valid = true;
        
        std::visit([&](const auto& e) {
            using T = std::decay_t<decltype(e)>;
            
            if constexpr (std::is_same_v<T, NoteEvent>) {
                if (e.pitch > 127 || e.velocity > 127 || e.position > limits_.maxTicks || 
                    e.duration == 0 || e.channel >= limits_.maxChannels || 
                    e.track >= limits_.maxTracks) {
                    valid = false;
                }
            } else if constexpr (std::is_same_v<T, TempoEvent>) {
                if (e.position > limits_.maxTicks || e.bpm <= 0.0 || e.bpm > 500.0) {
                    valid = false;
                }
            } else if constexpr (std::is_same_v<T, TimeSignatureEvent>) {
                if (e.position > limits_.maxTicks || e.denominator == 0 || 
                    (e.denominator & (e.denominator - 1)) != 0) {
                    valid = false;
                }
            } else if constexpr (std::is_same_v<T, ProgramChangeEvent>) {
                if (e.position > limits_.maxTicks || e.channel >= limits_.maxChannels || 
                    e.program > 127) {
                    valid = false;
                }
            } else if constexpr (std::is_same_v<T, ControlChangeEvent>) {
                if (e.position > limits_.maxTicks || e.channel >= limits_.maxChannels || 
                    e.controller > 127 || e.value > 127) {
                    valid = false;
                }
            }
        }, event);
        
        if (valid) {
            sanitized.events.push_back(event);
        } else {
            sanitized.warnings.push_back("Dropped invalid event at index " + std::to_string(i));
        }
    }
    
    if (sanitized.events.empty()) {
        return {sanitized, {ValidationResult::EmptyProposal, "All events were invalid"}};
    }
    
    // Recalculate totalTicks from events
    std::uint32_t maxPos = 0;
    for (const auto& event : sanitized.events) {
        std::uint32_t pos = 0;
        std::visit([&pos](const auto& e) { pos = e.position; }, event);
        maxPos = std::max(maxPos, pos);
    }
    sanitized.totalTicks = std::max(maxPos, std::uint32_t(480)); // At least 1 beat
    
    return {sanitized, {ValidationResult::Ok, "Sanitized with " + std::to_string(sanitized.warnings.size()) + " warnings"}};
}

} // namespace mozart::generation