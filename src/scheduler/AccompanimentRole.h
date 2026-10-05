#pragma once

#include <cstdint>

namespace mozart::scheduler {

enum class AccompanimentRole : std::uint8_t {
    Bass = 0,
    Arpeggio = 1,
    Drums = 2
};

} // namespace mozart::scheduler
