#pragma once

#include <cstdint>
#include <vector>
#include <string>
#include <optional>
#include <variant>
#include <chrono>

namespace mozart::generation {

// Forward declarations
class PatternProposal;
class GenerationRequest;

//----------------------------------------------------------------------
// Musical event types for PatternProposal (Mozart ABI - 512 token space)
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
// PatternProposal - structured output from AI provider
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
    
    // Tempo constraints
    std::optional<double> minBpm;
    std::optional<double> maxBpm;
    std::optional<double> targetBpm;
    
    // Key/scale hint
    std::optional<std::string> key;        // e.g., "C major", "A minor"
    std::optional<std::string> scale;      // e.g., "major", "minor", "dorian"
    
    // Chord progression (Roman numerals or chord symbols)
    std::vector<std::string> chordProgression;
    
    // Structural constraints
    std::optional<std::uint32_t> barCount;      // Number of bars
    std::optional<std::uint32_t> maxEvents;     // Maximum events in proposal
    std::optional<std::uint32_t> maxTicks;      // Maximum pattern length in ticks
    
    // Density/energy hints (0.0 - 1.0)
    std::optional<double> density;       // Note density
    std::optional<double> energy;        // Overall energy level
    std::optional<double> syncopation;   // Syncopation amount
    
    // Instrument role hints
    std::vector<std::string> roles;      // e.g., "lead", "bass", "drums", "pad"
    
    // Reproducibility
    std::optional<std::uint32_t> seed;
    
    // Provider-specific parameters (opaque)
    std::vector<std::pair<std::string, std::string>> providerParams;
    
    [[nodiscard]] bool hasTempoConstraint() const noexcept {
        return minBpm.has_value() || maxBpm.has_value() || targetBpm.has_value();
    }
};

//----------------------------------------------------------------------
// Provider interface
//----------------------------------------------------------------------

class MusicGenerationProvider {
public:
    virtual ~MusicGenerationProvider() = default;
    
    // Provider identification
    [[nodiscard]] virtual std::string providerId() const noexcept = 0;
    [[nodiscard]] virtual std::string modelId() const noexcept = 0;
    [[nodiscard]] virtual std::string version() const noexcept = 0;
    
    // Generation
    [[nodiscard]] virtual std::optional<PatternProposal> generate(const GenerationRequest& request) = 0;
    
    // Capabilities
    [[nodiscard]] virtual bool supportsStyle(const std::string& style) const noexcept { return true; }
    [[nodiscard]] virtual bool supportsRoles(const std::vector<std::string>& roles) const noexcept { return true; }
    [[nodiscard]] virtual std::vector<std::string> supportedStyles() const noexcept { return {}; }
    [[nodiscard]] virtual std::vector<std::string> supportedRoles() const noexcept { return {}; }
    
    // Health check
    [[nodiscard]] virtual bool isAvailable() const noexcept = 0;
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
// PatternProposalValidator - validates proposals before musical model
//----------------------------------------------------------------------

class PatternProposalValidator final {
public:
    struct Limits {
        std::uint32_t maxEvents = 1024;
        std::uint32_t maxTicks = 480 * 32;  // 32 bars at 480 ticks/beat
        std::uint8_t maxTracks = 8;
        std::uint8_t maxChannels = 16;
        
        constexpr Limits() noexcept = default;
        constexpr Limits(std::uint32_t maxEvents_, std::uint32_t maxTicks_, std::uint8_t maxTracks_, std::uint8_t maxChannels_) noexcept
            : maxEvents(maxEvents_), maxTicks(maxTicks_), maxTracks(maxTracks_), maxChannels(maxChannels_) {}
    };
    
    explicit PatternProposalValidator(Limits limits = {}) noexcept : limits_(limits) {}
    
    [[nodiscard]] ValidationReport validate(const PatternProposal& proposal) const noexcept;
    
    // Sanitize proposal - clamp values, remove invalid events
    // Returns sanitized proposal and report of changes
    [[nodiscard]] std::pair<PatternProposal, ValidationReport> sanitize(const PatternProposal& proposal) const noexcept;
    
private:
    Limits limits_;
};

} // namespace mozart::generation