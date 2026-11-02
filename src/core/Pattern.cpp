#include "Pattern.h"

#include <algorithm>

namespace mozart {

Pattern::Pattern(std::uint32_t id, std::uint32_t trackId, std::string name)
    : id_(id), trackId_(trackId), name_(std::move(name)) {}

std::uint32_t Pattern::addEvent(const MidiEvent& event) {
    MidiEvent e = event;
    e.id = nextEventId_++;
    e.trackId = trackId_;
    e.patternId = id_;
    events_.push_back(e);
    return e.id;
}

bool Pattern::removeEvent(std::uint32_t eventId) {
    for (auto it = events_.begin(); it != events_.end(); ++it) {
        if (it->id == eventId) {
            events_.erase(it);
            return true;
        }
    }
    return false;
}

MidiEvent* Pattern::findEvent(std::uint32_t eventId) noexcept {
    for (auto& event : events_) {
        if (event.id == eventId) {
            return &event;
        }
    }
    return nullptr;
}

const MidiEvent* Pattern::findEvent(std::uint32_t eventId) const noexcept {
    for (const auto& event : events_) {
        if (event.id == eventId) {
            return &event;
        }
    }
    return nullptr;
}

bool Pattern::setEventTick(std::uint32_t eventId, std::uint32_t tick) {
    MidiEvent* event = findEvent(eventId);
    if (event == nullptr) {
        return false;
    }
    event->tick = tick;
    return true;
}

bool Pattern::setEventNote(std::uint32_t eventId, std::uint8_t note) {
    MidiEvent* event = findEvent(eventId);
    if (event == nullptr || note >= 128) {
        return false;
    }
    event->note = note;
    return true;
}

bool Pattern::setEventVelocity(std::uint32_t eventId, std::uint8_t velocity) {
    MidiEvent* event = findEvent(eventId);
    if (event == nullptr || velocity >= 128) {
        return false;
    }
    event->velocity = velocity;
    return true;
}

bool Pattern::setEventDuration(std::uint32_t eventId, std::uint32_t durationTicks) {
    MidiEvent* event = findEvent(eventId);
    if (event == nullptr) {
        return false;
    }
    event->durationTicks = durationTicks;
    return true;
}

bool Pattern::setEventProbability(std::uint32_t eventId, std::uint8_t probability) {
    MidiEvent* event = findEvent(eventId);
    if (event == nullptr || probability > 100) {
        return false;
    }
    event->probability = probability;
    return true;
}

bool Pattern::setEventRatchet(std::uint32_t eventId, std::uint8_t ratchet) {
    MidiEvent* event = findEvent(eventId);
    if (event == nullptr) {
        return false;
    }
    event->ratchet = ratchet;
    return true;
}

bool Pattern::setEventNudge(std::uint32_t eventId, int32_t nudgeTicks) {
    MidiEvent* event = findEvent(eventId);
    if (event == nullptr) {
        return false;
    }
    event->nudgeTicks = nudgeTicks;
    return true;
}

} // namespace mozart
