#pragma once

#include "core/MidiTypes.h"

#include <cstddef>
#include <cstdint>
#include <vector>

namespace mozart::midi {

enum class ControllerAction : std::uint8_t {
    None = 0,
    Scene = 1,
    Density = 2,
    Accent = 3,
    Swing = 4,
    NoteRepeat = 5,
    Mutation = 6
};

struct ControllerBinding final {
    std::uint8_t channel = 0;
    std::uint8_t controller = 0;
    ControllerAction action = ControllerAction::None;
};

struct ControllerCommand final {
    ControllerAction action = ControllerAction::None;
    std::uint8_t value = 0;
};

class ControllerMapping final {
public:
    ControllerMapping();

    void setBindings(std::vector<ControllerBinding> bindings);
    void resetToDefaults();

    [[nodiscard]] ControllerCommand resolve(
            const MidiShortMessage& message) const noexcept;

private:
    std::vector<ControllerBinding> bindings_;
};

} // namespace mozart::midi
