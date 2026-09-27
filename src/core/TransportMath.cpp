#include "TransportMath.h"

#include <cmath>

namespace mozart::timing {

double beatAtTime(
        double referenceBeat,
        double referenceTimeSeconds,
        double tempoBpm,
        double timeSeconds) noexcept {
    if (!(tempoBpm > 0.0)) {
        return referenceBeat;
    }

    return referenceBeat + (timeSeconds - referenceTimeSeconds) * tempoBpm / 60.0;
}

double quantizeBeat(double beat, double quantumBeats) noexcept {
    if (!(quantumBeats > 0.0)) {
        return beat;
    }

    return std::ceil((beat - 1.0e-12) / quantumBeats) * quantumBeats;
}

double nextQuantizedBeat(double beat, double quantumBeats) noexcept {
    if (!(quantumBeats > 0.0)) {
        return beat;
    }

    const auto current = quantizeBeat(beat, quantumBeats);
    if (current > beat + 1.0e-9) {
        return current;
    }

    return current + quantumBeats;
}

} // namespace mozart::timing
