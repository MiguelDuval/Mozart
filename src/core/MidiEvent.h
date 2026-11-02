#pragma once

#include <cstdint>
#include <optional>

namespace mozart {

/**
 * Одно MIDI-событие ноты внутри паттерна.
 * Использует музыкальные координаты (tick, note, velocity, duration и т.д.)
 * вместо сырых MIDI-байтов, согласно архитектурному правилу проекта.
 */
struct MidiEvent final {
    std::uint32_t id = 0;
    std::uint32_t trackId = 0;
    std::uint32_t patternId = 0;

    // Позиция в тиках внутри паттерна
    std::uint32_t tick = 0;
    // MIDI нота 0..127
    std::uint8_t note = 0;
    // Velocity 0..127
    std::uint8_t velocity = 100;
    // Длительность в тиках
    std::uint32_t durationTicks = 120;
    // Вероятность срабатывания 0..100
    std::uint8_t probability = 100;
    // Количество дополнительных ударов (ratchet)
    std::uint8_t ratchet = 1;
    // Микро-смещение в тиках (nudge)
    int32_t nudgeTicks = 0;

    [[nodiscard]] bool isValid() const noexcept {
        return note < 128 && velocity < 128 && probability <= 100;
    }
};

} // namespace mozart
