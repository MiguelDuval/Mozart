#include "AndroidMidiOutput.h"

#include <amidi/AMidi.h>

#include <array>
#include <dlfcn.h>
#include <limits>
#include <mutex>
#include <sys/types.h>

namespace mozart::platform::android {
namespace {

struct AndroidMidiApi {
    using FromJava = media_status_t (*)(JNIEnv*, jobject, AMidiDevice**);
    using GetNumInputPorts = ssize_t (*)(const AMidiDevice*);
    using InputPortOpen = media_status_t (*)(const AMidiDevice*, int32_t, AMidiInputPort**);
    using InputPortSendWithTimestamp =
            ssize_t (*)(const AMidiInputPort*, const uint8_t*, size_t, int64_t);
    using InputPortClose = void (*)(const AMidiInputPort*);
    using DeviceRelease = media_status_t (*)(const AMidiDevice*);

    void* handle = nullptr;
    FromJava fromJava = nullptr;
    GetNumInputPorts getNumInputPorts = nullptr;
    InputPortOpen inputPortOpen = nullptr;
    InputPortSendWithTimestamp inputPortSendWithTimestamp = nullptr;
    InputPortClose inputPortClose = nullptr;
    DeviceRelease deviceRelease = nullptr;

    bool isReady() const noexcept {
        return handle != nullptr &&
               fromJava != nullptr &&
               getNumInputPorts != nullptr &&
               inputPortOpen != nullptr &&
               inputPortSendWithTimestamp != nullptr &&
               inputPortClose != nullptr &&
               deviceRelease != nullptr;
    }
};

template <typename Function>
Function loadSymbol(void* handle, const char* name) noexcept {
    return reinterpret_cast<Function>(dlsym(handle, name));
}

const AndroidMidiApi* getAndroidMidiApi() noexcept {
    static std::once_flag once;
    static AndroidMidiApi api;

    std::call_once(once, [] {
        // AMidi is an API 29 feature. Dynamic loading keeps the APK compatible
        // with the project's minSdk while allowing a graceful "unsupported"
        // result on older Android versions.
        api.handle = dlopen("libamidi.so", RTLD_NOW | RTLD_LOCAL);
        if (api.handle == nullptr) {
            return;
        }

        api.fromJava =
                loadSymbol<AndroidMidiApi::FromJava>(api.handle, "AMidiDevice_fromJava");
        api.getNumInputPorts =
                loadSymbol<AndroidMidiApi::GetNumInputPorts>(
                        api.handle, "AMidiDevice_getNumInputPorts");
        api.inputPortOpen =
                loadSymbol<AndroidMidiApi::InputPortOpen>(
                        api.handle, "AMidiInputPort_open");
        api.inputPortSendWithTimestamp =
                loadSymbol<AndroidMidiApi::InputPortSendWithTimestamp>(
                        api.handle, "AMidiInputPort_sendWithTimestamp");
        api.inputPortClose =
                loadSymbol<AndroidMidiApi::InputPortClose>(
                        api.handle, "AMidiInputPort_close");
        api.deviceRelease =
                loadSymbol<AndroidMidiApi::DeviceRelease>(
                        api.handle, "AMidiDevice_release");

        if (!api.isReady()) {
            dlclose(api.handle);
            api = {};
        }
    });

    return api.isReady() ? &api : nullptr;
}

} // namespace

std::int32_t AndroidMidiOutput::open(
        JNIEnv* env,
        jobject javaMidiDevice,
        std::int32_t portNumber) noexcept {
    if (env == nullptr || javaMidiDevice == nullptr || portNumber < 0) {
        return static_cast<std::int32_t>(midi::MidiTransportStatus::PlatformError);
    }

    std::lock_guard<std::mutex> lock(mutex_);

    if (inputPort_ != nullptr) {
        // getAndroidMidiApi() must have succeeded while this object was open.
        if (const auto* api = getAndroidMidiApi(); api != nullptr) {
            api->inputPortClose(inputPort_);
        }
        inputPort_ = nullptr;
    }

    if (device_ != nullptr) {
        if (const auto* api = getAndroidMidiApi(); api != nullptr) {
            (void) api->deviceRelease(device_);
        }
        device_ = nullptr;
    }

    const auto* api = getAndroidMidiApi();
    if (api == nullptr) {
        return static_cast<std::int32_t>(midi::MidiTransportStatus::Unsupported);
    }

    AMidiDevice* nativeDevice = nullptr;
    const media_status_t deviceStatus =
            api->fromJava(env, javaMidiDevice, &nativeDevice);

    if (deviceStatus != AMEDIA_OK || nativeDevice == nullptr) {
        return static_cast<std::int32_t>(midi::MidiTransportStatus::PlatformError);
    }

    const auto inputPortCount = api->getNumInputPorts(nativeDevice);
    if (inputPortCount < 1 || portNumber >= inputPortCount) {
        (void) api->deviceRelease(nativeDevice);
        return static_cast<std::int32_t>(midi::MidiTransportStatus::InvalidMessage);
    }

    AMidiInputPort* inputPort = nullptr;
    const media_status_t portStatus =
            api->inputPortOpen(nativeDevice, portNumber, &inputPort);

    if (portStatus != AMEDIA_OK || inputPort == nullptr) {
        (void) api->deviceRelease(nativeDevice);
        return static_cast<std::int32_t>(midi::MidiTransportStatus::PlatformError);
    }

    device_ = nativeDevice;
    inputPort_ = inputPort;
    return static_cast<std::int32_t>(midi::MidiTransportStatus::Ok);
}

bool AndroidMidiOutput::isOpen() const noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    return device_ != nullptr && inputPort_ != nullptr;
}

midi::MidiSendResult AndroidMidiOutput::send(
        const midi::MidiShortMessage& message) noexcept {
    std::lock_guard<std::mutex> lock(mutex_);

    if (device_ == nullptr || inputPort_ == nullptr) {
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

    const auto* api = getAndroidMidiApi();
    if (api == nullptr) {
        return {
            midi::MidiTransportStatus::Unsupported,
            0
        };
    }

    std::array<std::uint8_t, 3> bytes{
        message.status,
        message.data1,
        message.data2
    };

    const auto sent = api->inputPortSendWithTimestamp(
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
    std::lock_guard<std::mutex> lock(mutex_);
    const auto* api = getAndroidMidiApi();

    if (inputPort_ != nullptr) {
        if (api != nullptr) {
            api->inputPortClose(inputPort_);
        }
        inputPort_ = nullptr;
    }

    if (device_ != nullptr) {
        if (api != nullptr) {
            (void) api->deviceRelease(device_);
        }
        device_ = nullptr;
    }
}

} // namespace mozart::platform::android
