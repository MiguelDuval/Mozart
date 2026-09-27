#include "ControllerMapping.h"

#include <utility>

namespace mozart::midi {

ControllerMapping::ControllerMapping() {
    resetToDefaults();
}

void ControllerMapping::setBindings(
        std::vector<ControllerBinding> bindings) {
    bindings_ = std::move(bindings);
}

void ControllerMapping::resetToDefaults() {
    bindings_ = {
        ControllerBinding{0, 20, ControllerAction::Scene},
        ControllerBinding{0, 21, ControllerAction::Density},
        ControllerBinding{0, 22, ControllerAction::Accent},
        ControllerBinding{0, 23, ControllerAction::Swing},
        ControllerBinding{0, 24, ControllerAction::NoteRepeat},
        ControllerBinding{0, 25, ControllerAction::Mutation}
    };
}

ControllerCommand ControllerMapping::resolve(
        const MidiShortMessage& message) const noexcept {
    if (!message.isValid() ||
        (message.status & 0xF0u) != 0xB0u) {
        return {};
    }

    const auto channel =
            static_cast<std::uint8_t>(message.status & 0x0Fu);

    for (const auto& binding : bindings_) {
        if (binding.channel == channel &&
            binding.controller == message.data1 &&
            binding.action != ControllerAction::None) {
            return ControllerCommand{binding.action, message.data2};
        }
    }

    return {};
}

} // namespace mozart::midi
