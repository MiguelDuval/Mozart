#include "AccompanimentScheduler.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <type_traits>
#include <vector>

namespace mozart::scheduler {
namespace {

[[nodiscard]] std::uint32_t eventPosition(const generation::PatternEvent& event) noexcept {
    return std::visit([](const auto& e) noexcept { return e.position; }, event);
}

[[nodiscard]] bool isSchedulableEvent(const generation::PatternEvent& event) noexcept {
    return std::visit([](const auto& e) noexcept -> bool {
        using T = std::decay_t<decltype(e)>;
        if constexpr (std::is_same_v<T, generation::NoteEvent>) {
            return e.pitch <= 127 && e.velocity <= 127 && e.channel < 16 &&
                   e.duration > 0 &&
                   e.duration <= std::numeric_limits<std::uint32_t>::max() - e.position;
        } else if constexpr (std::is_same_v<T, generation::TempoEvent>) {
            return std::isfinite(e.bpm) && e.bpm > 0.0 && e.bpm <= 500.0;
        } else if constexpr (std::is_same_v<T, generation::TimeSignatureEvent>) {
            return e.numerator > 0 && e.denominator > 0 &&
                   (e.denominator & (e.denominator - 1)) == 0;
        } else if constexpr (std::is_same_v<T, generation::ProgramChangeEvent>) {
            return e.channel < 16 && e.program <= 127;
        } else if constexpr (std::is_same_v<T, generation::ControlChangeEvent>) {
            return e.channel < 16 && e.controller <= 127 && e.value <= 127;
        }
        return false;
    }, event);
}

} // namespace

AccompanimentScheduler::AccompanimentScheduler(MidiSendQueue& queue) noexcept
    : queue_(queue) {}

void AccompanimentScheduler::configure(const SchedulerConfig& config) noexcept {
    config_ = config;
}

void AccompanimentScheduler::setStartHostTime(std::uint64_t nanos) noexcept {
    config_.startHostTimeNanos = nanos;
}

std::uint64_t AccompanimentScheduler::tickToHostTime(std::uint32_t tick) const noexcept {
    const TempoMap noTempoChanges;
    return tickToHostTime(tick, noTempoChanges);
}

std::uint64_t AccompanimentScheduler::tickToHostTime(
    std::uint32_t tick, const TempoMap& tempoMap) const noexcept {
    if (config_.ticksPerBeat == 0 || !std::isfinite(config_.bpm) ||
        config_.bpm <= 0.0 || config_.bpm > 500.0) {
        return config_.startHostTimeNanos;
    }

    long double elapsedSeconds = 0.0L;
    std::uint32_t previousTick = 0;
    double activeBpm = config_.bpm;

    for (const auto& tempo : tempoMap) {
        if (tempo.position > tick) {
            break;
        }

        if (tempo.position > previousTick) {
            const long double ticks = static_cast<long double>(tempo.position - previousTick);
            elapsedSeconds += (ticks / static_cast<long double>(config_.ticksPerBeat)) *
                              (60.0L / static_cast<long double>(activeBpm));
            previousTick = tempo.position;
        }
        activeBpm = tempo.bpm;
    }

    if (tick > previousTick) {
        const long double ticks = static_cast<long double>(tick - previousTick);
        elapsedSeconds += (ticks / static_cast<long double>(config_.ticksPerBeat)) *
                          (60.0L / static_cast<long double>(activeBpm));
    }

    const long double nanosFromStart = elapsedSeconds * 1.0e9L;
    const std::uint64_t maxDelta =
        std::numeric_limits<std::uint64_t>::max() - config_.startHostTimeNanos;
    if (!std::isfinite(nanosFromStart) ||
        nanosFromStart >= static_cast<long double>(maxDelta)) {
        return std::numeric_limits<std::uint64_t>::max();
    }

    return config_.startHostTimeNanos + static_cast<std::uint64_t>(nanosFromStart);
}

bool AccompanimentScheduler::schedule(
    const generation::PatternProposal& proposal) noexcept {
    if (!proposal.isValid() || config_.ticksPerBeat == 0 ||
        !std::isfinite(config_.bpm) || config_.bpm <= 0.0 || config_.bpm > 500.0) {
        return false;
    }

    // Preflight every event before touching the shared output queue. PatternProposal::isValid()
    // checks only basic bounds, so scheduler-specific validation is required here.
    for (const auto& event : proposal.events) {
        if (eventPosition(event) > proposal.totalTicks || !isSchedulableEvent(event)) {
            return false;
        }
    }

    TempoMap tempoMap;
    for (const auto& event : proposal.events) {
        if (const auto* tempo = std::get_if<generation::TempoEvent>(&event)) {
            tempoMap.push_back(*tempo);
        }
    }
    std::stable_sort(tempoMap.begin(), tempoMap.end(),
        [](const auto& a, const auto& b) { return a.position < b.position; });

    // Process semantic events by musical position. Stable ordering plus the queue's
    // insertion-order tiebreak makes note-off precede a same-tick later note-on.
    std::vector<const generation::PatternEvent*> orderedEvents;
    orderedEvents.reserve(proposal.events.size());
    for (const auto& event : proposal.events) {
        orderedEvents.push_back(&event);
    }
    std::stable_sort(orderedEvents.begin(), orderedEvents.end(),
        [](const auto* a, const auto* b) { return eventPosition(*a) < eventPosition(*b); });

    for (const auto* event : orderedEvents) {
        const bool ok = std::visit(
            [this, &tempoMap](const auto& e) noexcept -> bool {
                using T = std::decay_t<decltype(e)>;
                if constexpr (std::is_same_v<T, generation::NoteEvent>) {
                    return scheduleNoteEvent(e, tempoMap);
                } else if constexpr (std::is_same_v<T, generation::TempoEvent>) {
                    return scheduleTempoEvent(e);
                } else if constexpr (std::is_same_v<T, generation::TimeSignatureEvent>) {
                    return scheduleTimeSignatureEvent(e);
                } else if constexpr (std::is_same_v<T, generation::ProgramChangeEvent>) {
                    return scheduleProgramChange(e, tempoMap);
                } else if constexpr (std::is_same_v<T, generation::ControlChangeEvent>) {
                    return scheduleControlChange(e, tempoMap);
                }
                return false;
            },
            *event);

        if (!ok) {
            return false;
        }
    }

    if (!tempoMap.empty()) {
        config_.bpm = tempoMap.back().bpm;
    }
    return true;
}

bool AccompanimentScheduler::scheduleNoteEvent(
    const generation::NoteEvent& event, const TempoMap& tempoMap) noexcept {
    const std::uint32_t offTick = event.position + event.duration;
    const std::uint64_t onTime = tickToHostTime(event.position, tempoMap);
    const std::uint64_t offTime = tickToHostTime(offTick, tempoMap);

    auto onMsg = midi::noteOn(event.channel, event.pitch, event.velocity, onTime, config_.portId);
    auto offMsg = midi::noteOff(event.channel, event.pitch, 0, offTime, config_.portId);

    if (!onMsg.has_value() || !offMsg.has_value()) {
        return false;
    }

    queue_.push(*onMsg);
    queue_.push(*offMsg);
    return true;
}

bool AccompanimentScheduler::scheduleTempoEvent(
    const generation::TempoEvent& event) noexcept {
    // The tempo map was prevalidated and is applied during tick-to-host-time conversion.
    // Update config_.bpm only after all events are scheduled, so insertion order is irrelevant.
    return std::isfinite(event.bpm) && event.bpm > 0.0 && event.bpm <= 500.0;
}

bool AccompanimentScheduler::scheduleTimeSignatureEvent(
    const generation::TimeSignatureEvent& event) noexcept {
    (void)event;
    return true;
}

bool AccompanimentScheduler::scheduleProgramChange(
    const generation::ProgramChangeEvent& event, const TempoMap& tempoMap) noexcept {
    const std::uint64_t time = tickToHostTime(event.position, tempoMap);

    midi::MidiShortMessage pcMsg{
        static_cast<std::uint8_t>(0xC0 | event.channel),
        static_cast<std::uint8_t>(event.program),
        0,
        2,
        time,
        config_.portId
    };

    if (!pcMsg.isValid()) {
        return false;
    }

    queue_.push(pcMsg);
    return true;
}

bool AccompanimentScheduler::scheduleControlChange(
    const generation::ControlChangeEvent& event, const TempoMap& tempoMap) noexcept {
    const std::uint64_t time = tickToHostTime(event.position, tempoMap);
    auto msg = midi::controlChange(
        event.channel, event.controller, event.value, time, config_.portId);
    if (!msg.has_value()) {
        return false;
    }

    queue_.push(*msg);
    return true;
}

} // namespace mozart::scheduler
