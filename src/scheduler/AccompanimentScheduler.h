#pragma once

#include "core/GenerationTypes.h"
#include "core/MidiTypes.h"
#include "core/TransportMath.h"
#include "scheduler/MidiSendQueue.h"

#include <cstdint>
#include <vector>

namespace mozart::scheduler {

struct SchedulerConfig {
    std::uint32_t ticksPerBeat = 480;
    double bpm = 120.0;
    std::uint64_t startHostTimeNanos = 0;
    std::uint32_t portId = 0;
};

class AccompanimentScheduler final {
public:
    explicit AccompanimentScheduler(MidiSendQueue& queue) noexcept;

    AccompanimentScheduler(const AccompanimentScheduler&) = delete;
    AccompanimentScheduler& operator=(const AccompanimentScheduler&) = delete;
    AccompanimentScheduler(AccompanimentScheduler&&) = default;
    AccompanimentScheduler& operator=(AccompanimentScheduler&&) = default;

    void configure(const SchedulerConfig& config) noexcept;
    [[nodiscard]] const SchedulerConfig& config() const noexcept { return config_; }
    void setStartHostTime(std::uint64_t nanos) noexcept;

    // Linear conversion at the configured base tempo. Proposal scheduling uses
    // the piecewise tempo map supplied by TempoEvent metadata.
    [[nodiscard]] std::uint64_t tickToHostTime(std::uint32_t tick) const noexcept;
    [[nodiscard]] bool schedule(const generation::PatternProposal& proposal) noexcept;

private:
    using TempoMap = std::vector<generation::TempoEvent>;

    [[nodiscard]] std::uint64_t tickToHostTime(
        std::uint32_t tick, const TempoMap& tempoMap) const noexcept;
    [[nodiscard]] bool scheduleNoteEvent(
        const generation::NoteEvent& event, const TempoMap& tempoMap) noexcept;
    [[nodiscard]] bool scheduleTempoEvent(const generation::TempoEvent& event) noexcept;
    [[nodiscard]] bool scheduleTimeSignatureEvent(
        const generation::TimeSignatureEvent& event) noexcept;
    [[nodiscard]] bool scheduleProgramChange(
        const generation::ProgramChangeEvent& event, const TempoMap& tempoMap) noexcept;
    [[nodiscard]] bool scheduleControlChange(
        const generation::ControlChangeEvent& event, const TempoMap& tempoMap) noexcept;

    MidiSendQueue& queue_;
    SchedulerConfig config_;
};

} // namespace mozart::scheduler
