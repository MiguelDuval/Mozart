#include "generation/DeterministicPatternProvider.h"

#include <cassert>
#include <cstddef>
#include <cstdint>

int main() {
    mozart::generation::GenerationRequest request;
    request.role = mozart::generation::GenerationRole::Bass;
    request.bars = 2;
    request.density = 1.0;
    request.probability = 1.0;
    request.ratchet = 1;
    request.seed = 12345;

    mozart::generation::DeterministicPatternProvider provider;

    const auto baseline = provider.generate(request);
    assert(baseline.ok());
    assert(!baseline.proposal.noteEvents.empty());

    request.probability = 0.0;
    const auto muted = provider.generate(request);
    assert(muted.ok());
    assert(muted.proposal.noteEvents.empty());

    request.probability = 0.5;
    const auto half = provider.generate(request);
    assert(half.ok());
    assert(half.proposal.noteEvents.size() < baseline.proposal.noteEvents.size());
    assert(half.proposal.noteEvents.size() > 0);

    request.probability = 1.0;
    request.ratchet = 4;
    const auto ratcheted = provider.generate(request);
    assert(ratcheted.ok());
    assert(
            ratcheted.proposal.noteEvents.size() ==
            baseline.proposal.noteEvents.size() * 4U);

    for (const auto& event : ratcheted.proposal.noteEvents) {
        assert(event.durationBeats > 0.0);
    }

    const auto repeat = provider.generate(request);
    assert(repeat.ok());
    assert(repeat.proposal == ratcheted.proposal);

    return 0;
}
