#include "generation/LocalNeuralPatternProvider.h"
#include "generation/TokenInferenceBackend.h"

#include <cassert>
#include <cstddef>
#include <string>
#include <utility>
#include <vector>

using namespace mozart::generation;

namespace {

constexpr MidiEventToken kValidTokens[] = {
        1,   // BOS
        16,  // channel 0
        86,  // note 54 (F#3)
        185, // velocity bin
        271, // duration: 16 grid steps = 1 beat
        2    // EOS
};

class FakeBackend final : public TokenInferenceBackend {
public:
    TokenInferenceStatus status = TokenInferenceStatus::Ok;
    std::vector<MidiEventToken> tokens{
            std::begin(kValidTokens),
            std::end(kValidTokens)
    };
    bool available = true;
    int calls = 0;
    std::size_t lastMaxTokens = 0;

    double confidence = 0.75;
    std::uint32_t generationTimeMs = 12;
    std::string message = "fake backend";

    [[nodiscard]] TokenInferenceResult generateTokens(
            const GenerationRequest&,
            const std::size_t maxTokens) override {
        ++calls;
        lastMaxTokens = maxTokens;
        return {
                status,
                tokens,
                confidence,
                generationTimeMs,
                message
        };
    }

    [[nodiscard]] bool isAvailable() const noexcept override {
        return available;
    }

    [[nodiscard]] std::string id() const override {
        return "test-backend";
    }
};

void testInvalidRequestDoesNotCallBackend() {
    FakeBackend backend;
    LocalNeuralPatternProvider provider(backend);

    auto request = GenerationRequest{};
    request.tempoBpm = 0.0;

    const auto result = provider.generate(request);

    assert(result.status == GenerationStatus::InvalidRequest);
    assert(backend.calls == 0);
}

void testUnavailableBackendIsReported() {
    FakeBackend backend;
    backend.available = false;
    LocalNeuralPatternProvider provider(backend);

    const auto result = provider.generate(GenerationRequest{});

    assert(result.status == GenerationStatus::Unavailable);
    assert(backend.calls == 0);
    assert(!provider.isAvailable());
}

void testBackendFailureIsNotAccepted() {
    FakeBackend backend;
    backend.status = TokenInferenceStatus::Failed;
    backend.message = "runtime failure";
    LocalNeuralPatternProvider provider(backend);

    const auto result = provider.generate(GenerationRequest{});

    assert(result.status == GenerationStatus::Failed);
    assert(result.message == "runtime failure");
    assert(backend.calls == 1);
}

void testMalformedTokenStreamIsRejected() {
    FakeBackend backend;
    backend.tokens = {1, 16, 86, 271, 2}; // Missing velocity token.
    LocalNeuralPatternProvider provider(backend);

    const auto result = provider.generate(GenerationRequest{});

    assert(result.status == GenerationStatus::Failed);
    assert(result.message ==
           "model token stream failed strict detokenization");
    assert(backend.calls == 1);
}

void testValidTokenStreamIsDetokenizedAndValidated() {
    FakeBackend backend;
    LocalNeuralPatternProvider provider(backend);

    auto request = GenerationRequest{};
    request.seed = 0x12345678u;

    const auto result = provider.generate(request);

    assert(result.status == GenerationStatus::Ok);
    assert(result.ok());
    assert(backend.calls == 1);
    assert(backend.lastMaxTokens == 16384);
    assert(result.proposal.noteEvents.size() == 1);
    assert(result.proposal.noteEvents[0].note == 54);
    assert(result.proposal.noteEvents[0].startBeat == 0.0);
    assert(result.proposal.noteEvents[0].durationBeats == 1.0);
    assert(result.proposal.metadata.seed == request.seed);
    assert(result.proposal.metadata.confidence == backend.confidence);
    assert(result.proposal.metadata.generationTimeMs == backend.generationTimeMs);
    assert(result.proposal.metadata.generatorId == "test-backend");
}

void testInvalidProposalNeverBypassesValidator() {
    FakeBackend backend;
    backend.tokens = {
            1,
            16,
            32 + 30, // C2, below default minNote and out of F# minor.
            185,
            271,
            2
    };
    LocalNeuralPatternProvider provider(backend);

    auto request = GenerationRequest{};
    request.minNote = 36;
    request.maxNote = 96;

    const auto result = provider.generate(request);

    assert(result.status == GenerationStatus::Ok);
    assert(result.proposal.noteEvents.size() == 1);
    assert(result.proposal.noteEvents[0].note >= request.minNote);
    assert(result.proposal.noteEvents[0].note <= request.maxNote);
}

} // namespace

int main() {
    testInvalidRequestDoesNotCallBackend();
    testUnavailableBackendIsReported();
    testBackendFailureIsNotAccepted();
    testMalformedTokenStreamIsRejected();
    testValidTokenStreamIsDetokenizedAndValidated();
    testInvalidProposalNeverBypassesValidator();
    return 0;
}
