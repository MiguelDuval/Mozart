#pragma once

#include "generation/NoteRepeat.h"
#include "generation/PatternAccent.h"
#include "generation/PatternDensity.h"
#include "generation/PatternSwing.h"

#include <cstdint>

namespace mozart::scheduler {

enum class MacroControl : std::uint8_t {
    Energy = 0,
    Motion = 1
};

struct MacroControlState final {
    generation::PatternDensity density = generation::PatternDensity::Full;
    generation::PatternAccent accent = generation::PatternAccent::Off;
    generation::PatternSwing swing = generation::PatternSwing::Off;
    generation::NoteRepeatRate noteRepeat = generation::NoteRepeatRate::Off;
};

class MacroControls final {
public:
    [[nodiscard]] static MacroControlState map(
            MacroControl control,
            std::uint8_t value) noexcept;
};

} // namespace mozart::scheduler
