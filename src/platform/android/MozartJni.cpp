#include <jni.h>

#include <cstdint>
#include <string>
#include <vector>

#include "core/MidiEndpoint.h"
#include "core/MozartEngine.h"

namespace {

[[nodiscard]] std::string javaStringToUtf8(
        JNIEnv* env,
        jobjectArray values,
        jsize index) {
    if (values == nullptr) {
        return {};
    }

    const auto value = static_cast<jstring>(env->GetObjectArrayElement(values, index));
    if (value == nullptr) {
        return {};
    }

    const char* utf = env->GetStringUTFChars(value, nullptr);
    if (utf == nullptr) {
        env->DeleteLocalRef(value);
        return {};
    }

    const std::string result(utf);
    env->ReleaseStringUTFChars(value, utf);
    env->DeleteLocalRef(value);
    return result;
}

[[nodiscard]] std::int32_t intAt(
        JNIEnv* env,
        jintArray values,
        jsize index) {
    jint value = 0;
    env->GetIntArrayRegion(values, index, 1, &value);
    return static_cast<std::int32_t>(value);
}

[[nodiscard]] mozart::midi::PortDirection portDirectionFromAndroid(
        std::int32_t value) noexcept {
    return value == 1
            ? mozart::midi::PortDirection::Input
            : mozart::midi::PortDirection::Output;
}

[[nodiscard]] mozart::midi::TransportKind transportKindFromAndroid(
        std::int32_t value) noexcept {
    switch (value) {
        case 1:
            return mozart::midi::TransportKind::Usb;
        case 2:
            return mozart::midi::TransportKind::Bluetooth;
        case 3:
            return mozart::midi::TransportKind::Virtual;
        default:
            return mozart::midi::TransportKind::Unknown;
    }
}

} // namespace

extern "C" JNIEXPORT jstring JNICALL
Java_com_miguelduval_mozart_MainActivity_nativeEngineInfo(
        JNIEnv* env,
        jobject) {
    const mozart::MozartEngine engine;
    const auto info = engine.info();

    return env->NewStringUTF(info.c_str());
}

extern "C" JNIEXPORT jint JNICALL
Java_com_miguelduval_mozart_AndroidMidiTransport_nativeSelectPreferredMidiOutput(
        JNIEnv* env,
        jclass,
        jintArray deviceIds,
        jintArray portNumbers,
        jintArray portTypes,
        jintArray transportTypes,
        jobjectArray names,
        jobjectArray manufacturers,
        jobjectArray products) {
    if (deviceIds == nullptr ||
        portNumbers == nullptr ||
        portTypes == nullptr ||
        transportTypes == nullptr ||
        names == nullptr ||
        manufacturers == nullptr ||
        products == nullptr) {
        return -1;
    }

    const jsize count = env->GetArrayLength(deviceIds);
    if (env->GetArrayLength(portNumbers) != count ||
        env->GetArrayLength(portTypes) != count ||
        env->GetArrayLength(transportTypes) != count ||
        env->GetArrayLength(names) != count ||
        env->GetArrayLength(manufacturers) != count ||
        env->GetArrayLength(products) != count) {
        return -1;
    }

    std::vector<mozart::midi::MidiEndpointDescriptor> candidates;
    candidates.reserve(static_cast<std::size_t>(count));

    for (jsize i = 0; i < count; ++i) {
        mozart::midi::MidiEndpointDescriptor candidate;
        candidate.deviceId = static_cast<std::uint32_t>(intAt(env, deviceIds, i));
        candidate.portNumber = static_cast<std::uint32_t>(intAt(env, portNumbers, i));
        candidate.direction =
                portDirectionFromAndroid(intAt(env, portTypes, i));
        candidate.transport =
                transportKindFromAndroid(intAt(env, transportTypes, i));
        candidate.name = javaStringToUtf8(env, names, i);
        candidate.manufacturer = javaStringToUtf8(env, manufacturers, i);
        candidate.product = javaStringToUtf8(env, products, i);
        candidates.push_back(std::move(candidate));
    }

    const auto selection = mozart::midi::MidiEndpointSelector::selectPreferredOutput(
            candidates, "Arturia", "MicroFreak");

    return selection.selected()
            ? static_cast<jint>(*selection.candidateIndex)
            : static_cast<jint>(-1);
}
