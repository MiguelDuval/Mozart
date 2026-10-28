#pragma once

#include "core/GenerationTypes.h"
#include "core/MidiTypes.h"
#include "core/TransportMath.h"
#include "scheduler/MidiSendQueue.h"

#include <cstdint>
#include <optional>

namespace mozart::scheduler {

//----------------------------------------------------------------------
// SchedulerConfig - configuration for AccompanimentScheduler
//----------------------------------------------------------------------

struct SchedulerConfig {
    std::uint32_t ticksPerBeat = 480;   // PPQN resolution
    double bpm = 120.0;                 // Tempo in beats per minute
    std::uint64_t startHostTimeNanos = 0; // Host time when playback starts
    std::uint32_t portId = 0;           // MIDI output port identifier
};

//----------------------------------------------------------------------
// AccompanimentScheduler - converts PatternProposal events to timestamped
// MIDI messages and pushes them into a MidiSendQueue.
//
// Converts musical tick coordinates to absolute host time using the current
// tempo. Produces note-on/note-off pairs, program changes, and control
// changes. Tempo and time-signature events update internal state but do not
// produce MIDI messages (they are meta-events for the scheduler itself).
//
// Pure C++20 — no Android, Link, or audio dependencies. Fully deterministic
// given a fixed config and proposal.
//----------------------------------------------------------------------

class AccompanimentScheduler final {
public:
    explicit AccompanimentScheduler(MidiSendQueue& queue) noexcept;

    AccompanimentScheduler(const AccompanimentScheduler&) = delete;
    AccompanimentScheduler& operator=(const AccompanimentScheduler&) = delete;
    AccompanimentScheduler(AccompanimentScheduler&&) = default;
    AccompanimentScheduler& operator=(AccompanimentScheduler&&) = default;

    // Configure timing parameters. Safe to call at any time.
    void configure(const SchedulerConfig& config) noexcept;

    [[nodiscard]] const SchedulerConfig& config() const noexcept { return config_; }

    // Set the absolute host time (nanoseconds) corresponding to tick 0.
    // Call this when playback starts to anchor the schedule.
    void setStartHostTime(std::uint64_t nanos) noexcept;

    // Convert a musical tick position to absolute host time.
    // Returns startHostTimeNanos + (tick / ticksPerBeat) * (60 / bpm) * 1e9.
    [[nodiscard]] std::uint64_t tickToHostTime(std::uint32_t tick) const noexcept;

    // Schedule all events from a validated PatternProposal into the queue.
    // Returns false if the proposal is invalid or scheduling fails.
    // Each NoteEvent produces a note-on at its position and a note-off at
    // position + duration. ProgramChange and ControlChange events produce
    // corresponding MIDI messages. Tempo events update internal tempo.
    [[nodiscard]] bool schedule(const generation::PatternProposal& proposal) noexcept;

private:
    [[nodiscard]] bool scheduleNoteEvent(const generation::NoteEvent& event) noexcept;
    [[nodiscard]] bool scheduleTempoEvent(const generation::TempoEvent& event) noexcept;
    [[nodiscard]] bool scheduleTimeSignatureEvent(const generation::TimeSignatureEvent& event) noexcept;
    [[nodiscard]] bool scheduleProgramChange(const generation::ProgramChangeEvent& event) noexcept;
    [[nodiscard]] bool scheduleControlChange(const generation::ControlChangeEvent& event) noexcept;

    MidiSendQueue& queue_;
    SchedulerConfig config_;
};

} // namespace mozart::scheduler
