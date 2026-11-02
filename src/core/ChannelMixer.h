#pragma once

#include "Track.h"

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace mozart {

/**
 * Применяет уровень (level) и панорамирование (pan) треков к стерео аудиопотоку.
 * Работает в realtime-безопасном режиме: только атомарные чтения, без аллокаций и блокировок.
 */
class ChannelMixer final {
public:
    ChannelMixer();

    /**
     * Добавляет трек в микшер. Трек не копируется — хранится указатель.
     * Вызывается вне realtime потока.
     */
    void addTrack(Track* track);

    /**
     * Удаляет трек из микшера. Вызывается вне realtime потока.
     */
    void removeTrack(Track* track);

    /**
     * Обрабатывает один фрейм стерео аудио.
     * samples_in — входные сэмплы (может быть моно или стерео, interleaved L,R).
     * samples_out — выходные сэмплы (всегда стерео, interleaved L,R).
     * frameCount — количество фреймов.
     * Вызывается из realtime аудиоколбэка — без аллокаций и блокировок.
     */
    void process(const float* samples_in, float* samples_out, std::size_t frameCount) noexcept;

    /**
     * Снимок всех уровней иパン треков для отладки/UI.
     * Безопасен для вызова из любого потока.
     */
    struct TrackSnapshot {
        std::uint32_t id;
        float level;
        float pan;
    };
    std::vector<TrackSnapshot> captureSnapshots() const noexcept;

private:
    // Список указателей на треки (не владеем памятью)
    Track** tracks_{nullptr};
    std::size_t trackCount_{0};
    std::size_t trackCapacity_{0};

    // Коэффициенты стереобаланса для панорамирования (Equal Power панорамирование)
    static void panCoefficients(float pan, float& leftGain, float& rightGain) noexcept;
};

} // namespace mozart
