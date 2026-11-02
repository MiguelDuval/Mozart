#pragma once

#include <atomic>
#include <cstdint>
#include <string>

namespace mozart {

/**
 * Режимы звука метронома.
 */
enum class MetronomeSound {
    None,
    Click,
    Beep,
    Wood,
};

/**
 * Генератор метронома для realtime аудиоколбэка.
 * Генерирует звуковые импульсы с корректной длительностью, огибающей и акцентом.
 * Безопасен для realtime: только атомарные чтения, без аллокаций и блокировок.
 */
class Metronome final {
public:
    Metronome();

    // --- Настройка (вызывается из UI потока, безопасно для atomic) ---

    void setBpm(float bpm) noexcept;
    [[nodiscard]] float bpm() const noexcept;

    void setTimeSignature(int numerator, int denominator) noexcept;
    [[nodiscard]] int timeSignatureNumerator() const noexcept;
    [[nodiscard]] int timeSignatureDenominator() const noexcept;

    void setSound(MetronomeSound sound) noexcept;
    [[nodiscard]] MetronomeSound sound() const noexcept;

    void setVolume(float volume) noexcept; // 0.0 .. 1.0
    [[nodiscard]] float volume() const noexcept;

    void setAccentVolume(float volume) noexcept; // 0.0 .. 1.0,relative to base
    [[nodiscard]] float accentVolume() const noexcept;

    void setEnabled(bool enabled) noexcept;
    [[nodiscard]] bool enabled() const noexcept;

    // --- Синхронизация с транспортным временем ---

    /**
     * Устанавливает текущую позицию в тактах (beat position) из транспортного времени.
     * Вызывается из UI/планировщика потока.
     */
    void setBeatPosition(double beatPosition) noexcept;

    /**
     * Сбрасывает внутреннее состояние метронома (фазу, счетчик такта).
     */
    void reset() noexcept;

    // --- Генерация аудио (вызывается из realtime колбэка) ---

    /**
     * Генерирует стерео сэмплы метронома для одного фрейма.
     * sampleRate — частота дискретизации в Гц.
     * deltaSeconds — время, прошедшее с последнего вызова (в секундах).
     * left, right — выходные сэмплы.
     * Возвращает true, если был сгенерирован импульс.
     */
    bool process(float sampleRate, double deltaSeconds, float& left, float& right) noexcept;

private:
    // Настройки
    std::atomic<float> bpm_{120.0f};
    std::atomic<int> timeSigNum_{4};
    std::atomic<int> timeSigDen_{4};
    std::atomic<MetronomeSound> sound_{MetronomeSound::Click};
    std::atomic<float> volume_{0.5f};
    std::atomic<float> accentVolume_{1.0f};
    std::atomic<bool> enabled_{false};

    // Транспортное время
    std::atomic<double> beatPosition_{0.0};

    // Внутреннее состояние (только realtime поток)
    double phase_ = 0.0;        // Фаза внутри текущего щелчка (0.0 .. 1.0)
    double clickDuration_ = 0.0; // Оставшаяся длина импульса в секундах
    int beatInBar_ = 0;         // Текущий удар в такте (0 .. num-1)
    double secondsPerBeat_ = 0.5; // Длительность одного удара в секундах

    // Вспомогательные функции генерации звука
    float generateClick(float t) noexcept;
    float generateBeep(float t) noexcept;
    float generateWood(float t) noexcept;
};

} // namespace mozart
