#include "GenerationTypes.h"

#include <algorithm>
#include <sstream>

namespace mozart::generation {

//----------------------------------------------------------------------
// PatternProposal implementation
//----------------------------------------------------------------------

bool PatternProposal::isValid() const noexcept {
    if (events.empty()) {
        return false;
    }
    if (totalTicks == 0) {
        return false;
    }
    for (const auto& event : events) {
        std::uint32_t pos = 0;
        std::visit([&pos](const auto& e) { pos = e.position; }, event);
        if (pos > totalTicks) {
            return false;
        }
    }
    return true;
}

std::optional<std::string> PatternProposal::validationError() const noexcept {
    if (events.empty()) {
        return "No events in proposal";
    }
    if (totalTicks == 0) {
        return "Total ticks is zero";
    }
    for (std::size_t i = 0; i < events.size(); ++i) {
        const auto& event = events[i];
        std::uint32_t pos = 0;
        std::visit([&pos](const auto& e) { pos = e.position; }, event);
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

} // namespace mozart::generation