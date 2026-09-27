#pragma once

#include "generation/PatternAccent.h"
#include "generation/PatternDensity.h"
#include "generation/PatternSwing.h"
#include "scheduler/AccompanimentScheduler.h"

#include <cstdint>

namespace mozart::scheduler {

struct PerformanceScene final {
    static constexpr std::uint8_t kSceneCount = 4;

    std::uint8_t index = 0;
    AccompanimentRole role = AccompanimentRole::Bass;
    generation::PatternDensity density = generation::PatternDensity::Full;
    generation::PatternAccent accent = generation::PatternAccent::Off;
    generation::PatternSwing swing = generation::PatternSwing::Off;
    std::uint32_t seed = 0x4D4F5A41u;

    [[nodiscard]] static PerformanceScene preset(
            std::uint8_t index) noexcept;
};

} // namespace mozart::scheduler
