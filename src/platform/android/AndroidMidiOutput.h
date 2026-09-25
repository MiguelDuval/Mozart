#pragma once

#include "midi/MidiTransport.h"

#include <cstdint>
#include <jni.h>

struct AMidiDevice;
struct AMidiInputPort;

namespace mozart::platform::android {

class AndroidMidiOutput final : public midi::MidiOutputTransport {
public:
    [[nodiscard]] std::int32_t open(
            JNIEnv* env,
            jobject javaMidiDevice,
            std::int32_t portNumber) noexcept;

    [[nodiscard]] bool isOpen() const noexcept;

    [[nodiscard]] midi::MidiSendResult send(
            const midi::MidiShortMessage& message) noexcept override;

    void close() noexcept override;

private:
    AMidiDevice* device_ = nullptr;
    AMidiInputPort* inputPort_ = nullptr;
};

} // namespace mozart::platform::android
