#pragma once

#include <cstdint>
#include <vector>
#include <string>
#include <optional>
#include <variant>
#include <chrono>

namespace mozart::remi {

// Forward declarations
class PatternProposal;
class GenerationRequest;

//----------------------------------------------------------------------
// Musical event types for remi::PatternProposal (Mozart ABI - 512 token space)
//----------------------------------------------------------------------

struct NoteEvent {
    std::uint8_t pitch = 0;           // 0-127
    std::uint8_t velocity = 64;       // 0-127
    std::uint32_t position = 0;       // Position in ticks (1 beat = 480 ticks)
    std::uint32_t duration = 480;     // Duration in ticks
    std::uint8_t channel = 0;         // 0-15
    std::uint8_t track = 0;           // Track index
};

struct TempoEvent {
    std::uint32_t position = 0;       // Position in ticks
    double bpm = 120.0;               // Beats per minute
};

struct TimeSignatureEvent {
    std::uint32_t position = 0;       // Position in ticks
    std::uint8_t numerator = 4;       // Time signature numerator
    std::uint8_t denominator = 4;     // Time signature denominator (power of 2)
};

struct ProgramChangeEvent {
    std::uint32_t position = 0;       // Position in ticks
    std::uint8_t channel = 0;         // 0-15
    std::uint8_t program = 0;         // 0-127 (GM program number)
};

struct ControlChangeEvent {
    std::uint32_t position = 0;       // Position in ticks
    std::uint8_t channel = 0;         // 0-15
    std::uint8_t controller = 0;      // Controller number
    std::uint8_t value = 0;           // Controller value
};

// Variant type for all supported events in PatternProposal
using PatternEvent = std::variant<
    NoteEvent,
    TempoEvent,
    TimeSignatureEvent,
    ProgramChangeEvent,
    ControlChangeEvent
>;

//----------------------------------------------------------------------
// PatternProposal - structured output from REMI/BPE adapter
//----------------------------------------------------------------------

class PatternProposal final {
public:
    // Metadata
    std::string providerId;
    std::string modelId;
    std::uint32_t seed = 0;
    std::chrono::nanoseconds generationTime{};

    // Musical content
    std::vector<PatternEvent> events;

    // Bounds
    std::uint32_t totalTicks = 0;     // Total pattern length in ticks
    std::uint8_t trackCount = 1;      // Number of tracks used

    // Diagnostics
    std::vector<std::string> warnings;
    bool truncated = false;           // True if events were truncated to fit limits

    // Validation
    [[nodiscard]] bool isValid() const noexcept;
    [[nodiscard]] std::optional<std::string> validationError() const noexcept;

    // Utility
    [[nodiscard]] std::vector<NoteEvent> notes() const noexcept;
    [[nodiscard]] std::optional<TempoEvent> firstTempo() const noexcept;
    [[nodiscard]] std::optional<TimeSignatureEvent> firstTimeSignature() const noexcept;

    void clear() noexcept;
};

//----------------------------------------------------------------------
// GenerationRequest - input to AI provider
//----------------------------------------------------------------------

class GenerationRequest final {
public:
    // Style/genre hint (free text, provider-specific)
    std::string style;

    // Optional tempo constraint
    std::optional<double> targetBpm;
    std::optional<double> minBpm;
    std::optional<double> maxBpm;

    // Optional bar count
    std::optional<std::uint32_t> barCount;

    // Deterministic seed
    std::optional<std::uint32_t> seed;

    [[nodiscard]] bool hasTempoConstraint() const noexcept {
        return targetBpm.has_value() || minBpm.has_value() || maxBpm.has_value();
    }
};

//----------------------------------------------------------------------
// Validation result
//----------------------------------------------------------------------

enum class ValidationResult {
    Ok,
    EmptyProposal,
    TooManyEvents,
    InvalidPitch,
    InvalidVelocity,
    InvalidPosition,
    InvalidDuration,
    InvalidChannel,
    UnsupportedEvent,
    ExceedsMaxTicks,
    ProviderError
};

struct ValidationReport {
    ValidationResult result = ValidationResult::Ok;
    std::string message;
    std::size_t offendingEventIndex = 0;

    [[nodiscard]] bool isOk() const noexcept { return result == ValidationResult::Ok; }
    [[nodiscard]] std::string toString() const noexcept;
};

//----------------------------------------------------------------------
// PatternProposalValidator - validates proposals before conversion
//----------------------------------------------------------------------

class PatternProposalValidator final {
public:
    struct Limits {
        std::uint32_t maxEvents;
        std::uint32_t maxTicks;  // 32 bars at 480 ticks/beat
        std::uint8_t maxTracks;
        std::uint8_t maxChannels;

        constexpr Limits(std::uint32_t maxEvents_ = 1024,
                         std::uint32_t maxTicks_ = 480 * 32,
                         std::uint8_t maxTracks_ = 8,
                         std::uint8_t maxChannels_ = 16) noexcept
            : maxEvents(maxEvents_), maxTicks(maxTicks_),
              maxTracks(maxTracks_), maxChannels(maxChannels_) {}
    };

    explicit PatternProposalValidator(Limits limits = {}) noexcept : limits_(limits) {}

    [[nodiscard]] ValidationReport validate(const PatternProposal& proposal) const noexcept;

    // Sanitize proposal - clamp values, remove invalid events
    // Returns sanitized proposal and report of changes
    [[nodiscard]] std::pair<PatternProposal, ValidationReport> sanitize(const PatternProposal& proposal) const noexcept;

private:
    Limits limits_;
};

} // namespace mozart::remi
