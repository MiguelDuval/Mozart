#pragma once

#include <string>

namespace mozart {

class MozartEngine final {
public:
    [[nodiscard]] std::string info() const;
};

} // namespace mozart
