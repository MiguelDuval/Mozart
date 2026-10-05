#pragma once

namespace mozart::timing {

[[nodiscard]] double beatAtTime(
        double referenceBeat,
        double referenceTimeSeconds,
        double tempoBpm,
        double timeSeconds) noexcept;

[[nodiscard]] double quantizeBeat(
        double beat,
        double quantumBeats) noexcept;

[[nodiscard]] double nextQuantizedBeat(
        double beat,
        double quantumBeats) noexcept;

} // namespace mozart::timing
