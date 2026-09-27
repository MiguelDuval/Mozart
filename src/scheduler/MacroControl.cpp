#include "scheduler/MacroControl.h"

namespace mozart::scheduler {

MacroControlState MacroControls::map(
        const MacroControl control,
        const std::uint8_t value) noexcept {
    MacroControlState state{};

    switch (control) {
        case MacroControl::Energy:
            if (value < 32) {
                state.density = generation::PatternDensity::Sparse;
                state.accent = generation::PatternAccent::Off;
            } else if (value < 64) {
                state.density = generation::PatternDensity::Normal;
                state.accent = generation::PatternAccent::Mild;
            } else if (value < 96) {
                state.density = generation::PatternDensity::Full;
                state.accent = generation::PatternAccent::Mild;
            } else {
                state.density = generation::PatternDensity::Full;
                state.accent = generation::PatternAccent::Strong;
            }
            break;
        case MacroControl::Motion:
            if (value < 32) {
                state.swing = generation::PatternSwing::Off;
                state.noteRepeat = generation::NoteRepeatRate::Off;
            } else if (value < 64) {
                state.swing = generation::PatternSwing::Light;
                state.noteRepeat = generation::NoteRepeatRate::Double;
            } else if (value < 96) {
                state.swing = generation::PatternSwing::Full;
                state.noteRepeat = generation::NoteRepeatRate::Triple;
            } else {
                state.swing = generation::PatternSwing::Full;
                state.noteRepeat = generation::NoteRepeatRate::Quadruple;
            }
            break;
    }

    return state;
}

} // namespace mozart::scheduler
