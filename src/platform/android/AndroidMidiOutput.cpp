#include "AndroidMidiOutput.h"

#include <AMidi/AMidi.h>

#include <array>
#include <limits>

namespace mozart::platform::android {

std::int32_t AndroidMidiOutput::open(
        JNIEnv* env,
        jobject javaMidiDevice,
        std::int32_t portNumber) noexcept {
    close();

    if (env == nullptr || javaMidiDevice == nullptr || portNumber < 0) {
        return static_cast<std::int32_t>(midi::MidiTransportStatus::PlatformError);
    }

    AMidiDevice* nativeDevice = nullptr;
    const media_status_t deviceStatus =
            AMidiDevice_fromJava(env, javaMidiDevice, &nativeDevice);

    if (deviceStatus != AMEDIA_OK || nativeDevice == nullptr) {
        return static_cast<std::int32_t>(midi::MidiTransportStatus::PlatformError);
    }

    const auto inputPortCount = AMidiDevice_getNumInputPorts(nativeDevice);
    if (inputPortCount < 1 || portNumber >= inputPortCount) {
        (void) AMidiDevice_release(nativeDevice);
        return static_cast<std::int32_t>(midi::MidiTransportStatus::InvalidMessage);
    }

    AMidiInputPort* inputPort = nullptr;
    const media_status_t portStatus =
            AMidiInputPort_open(nativeDevice, portNumber, &inputPort);

    if (portStatus != AMEDIA_OK || inputPort == nullptr) {
        (void) AMidiDevice_release(nativeDevice);
        return static_cast<std::int32_t>(midi::MidiTransportStatus::PlatformError);
    }

    device_ = nativeDevice;
    inputPort_ = inputPort;
    return static_cast<std::int32_t>(midi::MidiTransportStatus::Ok);
}

bool AndroidMidiOutput::isOpen() const noexcept {
    return device_ != nullptr && inputPort_ != nullptr;
}

midi::MidiSendResult AndroidMidiOutput::send(
        const midi::MidiShortMessage& message) noexcept {
    if (!isOpen()) {
        return {
            midi::MidiTransportStatus::NotOpen,
            0
        };
    }

    if (!message.isValid()) {
        return {
            midi::MidiTransportStatus::InvalidMessage,
            0
        };
    }

    if (message.timestampNanos >
        static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) {
        return {
            midi::MidiTransportStatus::InvalidMessage,
            0
        };
    }

    std::array<std::uint8_t, 3> bytes{
        message.status,
        message.data1,
        message.data2
    };

    const auto sent = AMidiInputPort_sendWithTimestamp(
            inputPort_,
            bytes.data(),
            message.size,
            static_cast<std::int64_t>(message.timestampNanos));

    if (sent < 0) {
        return {
            midi::MidiTransportStatus::PlatformError,
            0
        };
    }

    const auto expected = static_cast<std::size_t>(message.size);
    if (static_cast<std::size_t>(sent) != expected) {
        return {
            midi::MidiTransportStatus::PartialSend,
            sent > 0 ? static_cast<std::size_t>(sent) : 0
        };
    }

    return {
        midi::MidiTransportStatus::Ok,
        static_cast<std::size_t>(sent)
    };
}

void AndroidMidiOutput::close() noexcept {
    if (inputPort_ != nullptr) {
        AMidiInputPort_close(inputPort_);
        inputPort_ = nullptr;
    }

    if (device_ != nullptr) {
        (void) AMidiDevice_release(device_);
        device_ = nullptr;
    }
}

} // namespace mozart::platform::android
