#include "core/MidiTypes.h"
#include "core/MozartEngine.h"
#include "core/TransportMath.h"
#include "generation/RhythmGenerator.h"

#include <cassert>
#include <cmath>
#include <cstdint>

int main() {
    {
        const auto message = mozart::midi::noteOn(0, 60, 100, 1234, 7);
        assert(message.has_value());
        assert(message->status == 0x90);
        assert(message->data1 == 60);
        assert(message->data2 == 100);
        assert(message->size == 3);
        assert(message->timestampNanos == 1234);
        assert(message->portId == 7);
        assert(message->isValid());
    }

    {
        assert(!mozart::midi::noteOn(16, 60, 100).has_value());
        assert(!mozart::midi::noteOn(0, 128, 100).has_value());
        assert(!mozart::midi::controlChange(0, 0, 128).has_value());
    }

    {
        const auto beat = mozart::timing::beatAtTime(0.0, 0.0, 120.0, 1.0);
        assert(std::abs(beat - 2.0) < 1.0e-12);
        assert(std::abs(mozart::timing::quantizeBeat(3.2, 4.0) - 4.0) < 1.0e-12);
    }

    {
        // beatAtTime with zero tempo returns reference beat unchanged.
        const auto refBeat = 7.5;
        const auto t0 = 10.0;
        const auto b0 = mozart::timing::beatAtTime(refBeat, t0, 0.0, t0 + 5.0);
        assert(std::abs(b0 - refBeat) < 1.0e-12);

        // Negative tempo also returns reference beat unchanged (guard clause).
        const auto b1 = mozart::timing::beatAtTime(refBeat, t0, -60.0, t0 + 5.0);
        assert(std::abs(b1 - refBeat) < 1.0e-12);

        // Non-zero tempo: 60 BPM = 1 beat/sec; 3 seconds later = +3 beats.
        const auto b2 = mozart::timing::beatAtTime(1.0, 0.0, 60.0, 3.0);
        assert(std::abs(b2 - 4.0) < 1.0e-12);

        // Time before reference: negative delta.
        const auto b3 = mozart::timing::beatAtTime(5.0, 10.0, 120.0, 8.0);
        assert(std::abs(b3 - 3.0) < 1.0e-9); // 2 seconds earlier at 120 BPM = -2 beats
    }

    {
        // quantizeBeat guards.
        assert(std::abs(mozart::timing::quantizeBeat(5.0, 0.0) - 5.0) < 1.0e-12);
        assert(std::abs(mozart::timing::quantizeBeat(-2.5, 1.0) - (-2.0)) < 1.0e-12);
        // Exact quantum boundary.
        assert(std::abs(mozart::timing::quantizeBeat(8.0, 4.0) - 8.0) < 1.0e-12);
        // Just above boundary rounds up.
        assert(std::abs(mozart::timing::quantizeBeat(8.000001, 4.0) - 12.0) < 1.0e-6);
        // Just below boundary rounds down (to the boundary).
        assert(std::abs(mozart::timing::quantizeBeat(7.999999, 4.0) - 8.0) < 1.0e-6);
    }

    {
        const auto pattern = mozart::generation::RhythmGenerator::euclidean(16, 4);
        assert(pattern.size() == 16);
        assert(pattern[0] && pattern[4] && pattern[8] && pattern[12]);
    }

    {
        const auto a = mozart::generation::RhythmGenerator::seededVelocityPattern(32, 42);
        const auto b = mozart::generation::RhythmGenerator::seededVelocityPattern(32, 42);
        assert(a == b);
        assert(a.size() == 32);
    }

    {
        const mozart::MozartEngine engine;
        const auto info = engine.info();
        assert(!info.empty());
        assert(info.find("C++20 core ready") != std::string::npos);
        assert(info.find("MIDI foundation") != std::string::npos);
    }

    return 0;
}
