#pragma once

#include "MidiEvent.h"

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

namespace mozart {

/**
 * ПатTERN — контейнер MIDI-событий, принадлежащий треку.
 * События идентифицируются по уникальному id в рамках паттерна.
 * ПатTERN привязан к треку через trackId.
 */
class Pattern final {
public:
    Pattern(std::uint32_t id, std::uint32_t trackId, std::string name);

    [[nodiscard]] std::uint32_t id() const noexcept { return id_; }
    [[nodiscard]] std::uint32_t trackId() const noexcept { return trackId_; }
    [[nodiscard]] const std::string& name() const noexcept { return name_; }

    // Добавляет событие в патTERN. Назначает новый уникальный id события.
    std::uint32_t addEvent(const MidiEvent& event);

    // Удаляет событие по id. Возвращает true, если событие было удалено.
    bool removeEvent(std::uint32_t eventId);

    // Находит событие по id. Возвращает nullptr, если не найдено.
    MidiEvent* findEvent(std::uint32_t eventId) noexcept;
    [[nodiscard]] const MidiEvent* findEvent(std::uint32_t eventId) const noexcept;

    // Возвращает все события паттерна
    [[nodiscard]] const std::vector<MidiEvent>& events() const noexcept { return events_; }

    // Обновляет поле события. Возвращает false, если событие не найдено или значение невалидно.
    bool setEventTick(std::uint32_t eventId, std::uint32_t tick);
    bool setEventNote(std::uint32_t eventId, std::uint8_t note);
    bool setEventVelocity(std::uint32_t eventId, std::uint8_t velocity);
    bool setEventDuration(std::uint32_t eventId, std::uint32_t durationTicks);
    bool setEventProbability(std::uint32_t eventId, std::uint8_t probability);
    bool setEventRatchet(std::uint32_t eventId, std::uint8_t ratchet);
    bool setEventNudge(std::uint32_t eventId, int32_t nudgeTicks);

private:
    std::uint32_t id_;
    std::uint32_t trackId_;
    std::string name_;
    std::vector<MidiEvent> events_;
    std::uint32_t nextEventId_{1};
};

} // namespace mozart
