#include "AccompanimentScheduler.h"

#include <algorithm>

namespace mozart::scheduler {

AccompanimentScheduler::AccompanimentScheduler(MidiSendQueue& queue) noexcept
    : queue_(queue) {}

void AccompanimentScheduler::configure(const SchedulerConfig& config) noexcept {
    config_ = config;
}

void AccompanimentScheduler::setStartHostTime(std::uint64_t nanos) noexcept {
    config_.startHostTimeNanos = nanos;
}

std::uint64_t AccompanimentScheduler::tickToHostTime(std::uint32_t tick) const noexcept {
    if (!(config_.bpm > 0.0) || config_.ticksPerBeat == 0) {
        return config_.startHostTimeNanos;
    }

    // Beats = tick / ticksPerBeat
    // Seconds per beat = 60.0 / bpm
    // Seconds from start = beats * secondsPerBeat
    const double beats = static_cast<double>(tick) / static_cast<double>(config_.ticksPerBeat);
    const double secondsPerBeat = 60.0 / config_.bpm;
    const double secondsFromStart = beats * secondsPerBeat;

    const std::uint64_t nanosFromStart =
        static_cast<std::uint64_t>(secondsFromStart * 1.0e9);

    return config_.startHostTimeNanos + nanosFromStart;
}

bool AccompanimentScheduler::schedule(const generation::PatternProposal& proposal) noexcept {
    if (!proposal.isValid()) {
        return false;
    }

    for (const auto& event : proposal.events) {
        bool ok = std::visit(
            [this](const auto& e) -> bool {
                using T = std::decay_t<decltype(e)>;

                if constexpr (std::is_same_v<T, generation::NoteEvent>) {
                    return scheduleNoteEvent(e);
                } else if constexpr (std::is_same_v<T, generation::TempoEvent>) {
                    return scheduleTempoEvent(e);
                } else if constexpr (std::is_same_v<T, generation::TimeSignatureEvent>) {
                    return scheduleTimeSignatureEvent(e);
                } else if constexpr (std::is_same_v<T, generation::ProgramChangeEvent>) {
                    return scheduleProgramChange(e);
                } else if constexpr (std::is_same_v<T, generation::ControlChangeEvent>) {
                    return scheduleControlChange(e);
                }
                return true;
            },
            event);

        if (!ok) {
            return false;
        }
    }

    return true;
}

bool AccompanimentScheduler::scheduleNoteEvent(const generation::NoteEvent& event) noexcept {
    if (event.pitch > 127 || event.velocity > 127 || event.channel >= 16) {
        return false;
    }

    const std::uint64_t onTime = tickToHostTime(event.position);
    const std::uint32_t offTick = event.position + event.duration;
    const std::uint64_t offTime = tickToHostTime(offTick);

    auto onMsg = midi::noteOn(event.channel, event.pitch, event.velocity, onTime, config_.portId);
    auto offMsg = midi::noteOff(event.channel, event.pitch, 0, offTime, config_.portId);

    if (!onMsg.has_value() || !offMsg.has_value()) {
        return false;
    }

    queue_.push(*onMsg);
    queue_.push(*offMsg);
    return true;
}

bool AccompanimentScheduler::scheduleTempoEvent(const generation::TempoEvent& event) noexcept {
    if (event.bpm <= 0.0 || event.bpm > 500.0) {
        return false;
    }

    // Tempo events are meta-events for the scheduler; they update internal tempo
    // but do not produce MIDI bytes. The host time anchor changes implicitly
    // because subsequent tickToHostTime() calls use the new bpm.
    config_.bpm = event.bpm;
    return true;
}

bool AccompanimentScheduler::scheduleTimeSignatureEvent(
    const generation::TimeSignatureEvent& event) noexcept {
    // Time-signature events are metadata for the scheduler. No MIDI output.
    // Denominator validity is already checked by the validator.
    (void)event;
    return true;
}

bool AccompanimentScheduler::scheduleProgramChange(
    const generation::ProgramChangeEvent& event) noexcept {
    if (event.channel >= 16 || event.program > 127) {
        return false;
    }

    const std::uint64_t time = tickToHostTime(event.position);

    // Program change: status 0xC0 | channel, one data byte (program)
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
    const generation::ControlChangeEvent& event) noexcept {
    if (event.channel >= 16 || event.controller > 127 || event.value > 127) {
        return false;
    }

    const std::uint64_t time = tickToHostTime(event.position);
    auto msg = midi::controlChange(event.channel, event.controller, event.value, time, config_.portId);
    return msg.has_value() && (queue_.push(*msg), true);
}

} // namespace mozart::scheduler
