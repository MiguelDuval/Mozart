#pragma once

#include <atomic>
#include <cstdint>
#include <string>

namespace mozart {

/**
 * Модель трека с параметрами уровня и панорамирования.
 * Параметры атомарны для безопасного чтения из realtime аудиопотока.
 */
class Track final {
public:
    explicit Track(std::uint32_t id, std::string name);

    [[nodiscard]] std::uint32_t id() const noexcept { return id_; }
    [[nodiscard]] const std::string& name() const noexcept { return name_; }

    // Уровень громкости: 0.0 (молчание) .. 1.0 (максимум)
    void setLevel(float level) noexcept;
    [[nodiscard]] float level() const noexcept;

    // Панорамирование: -1.0 (левый край) .. 0.0 (центр) .. 1.0 (правый край)
    void setPan(float pan) noexcept;
    [[nodiscard]] float pan() const noexcept;

    bool isMuted() const noexcept { return muted_.load(std::memory_order_relaxed); }
    void setMuted(bool muted) noexcept;

private:
    std::uint32_t id_;
    std::string name_;

    std::atomic<float> level_{1.0f};
    std::atomic<float> pan_{0.0f};
    std::atomic<bool> muted_{false};
};

} // namespace mozart
