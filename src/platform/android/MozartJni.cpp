#include <jni.h>

#include <cstdint>
#include <memory>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

#include "core/MidiEndpoint.h"
#include "core/MidiTypes.h"
#include "core/MozartEngine.h"
#include "musical/KeyScale.h"
#include "platform/android/AndroidMidiOutput.h"
#include "runtime/MozartRuntime.h"

namespace {

mozart::platform::android::AndroidMidiOutput g_midiOutput;
std::unique_ptr<mozart::runtime::MozartRuntime> g_runtime;
std::mutex g_runtimeMutex;

mozart::runtime::MozartRuntime* runtime() {
    std::lock_guard<std::mutex> lock(g_runtimeMutex);
    if (!g_runtime) {
        g_runtime = std::make_unique<mozart::runtime::MozartRuntime>(g_midiOutput);
    }
    return g_runtime.get();
}

[[nodiscard]] std::string javaStringToUtf8(
        JNIEnv* env,
        jobjectArray values,
        jsize index) {
    if (values == nullptr) {
        return {};
    }

    const auto value =
            static_cast<jstring>(env->GetObjectArrayElement(values, index));
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

extern "C" JNIEXPORT jstring JNICALL
Java_com_miguelduval_mozart_MainActivity_nativeLinkSnapshot(
        JNIEnv* env,
        jobject) {
    const auto snapshot = runtime()->captureLinkSnapshot();

    const std::string text =
            std::string("enabled=") + (snapshot.enabled ? "true" : "false") +
            " playing=" + (snapshot.playing ? "true" : "false") +
            " inSession=" + (snapshot.inSession ? "true" : "false") +
            " startStopSync=" +
                    (snapshot.startStopSyncEnabled ? "true" : "false") +
            " peers=" + std::to_string(snapshot.peers) +
            " tempo=" + std::to_string(snapshot.tempoBpm) +
            " beat=" + std::to_string(snapshot.beat) +
            " phase=" + std::to_string(snapshot.phase) +
            " quantum=" + std::to_string(snapshot.quantum);

    return env->NewStringUTF(text.c_str());
}

extern "C" JNIEXPORT void JNICALL
Java_com_miguelduval_mozart_MainActivity_nativeStartAccompaniment(
        JNIEnv*,
        jobject) {
    auto* app = runtime();
    app->start();
    app->setKeyScale(
            mozart::musical::KeyScale{
                    6, mozart::musical::Scale::NaturalMinor});
    app->setLinkEnabled(true);
    app->setAccompanimentEnabled(true);
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_miguelduval_mozart_MainActivity_nativeTestMidiNote(
        JNIEnv*,
        jobject) {
    return runtime()->sendDiagnosticNote() ? JNI_TRUE : JNI_FALSE;
}

extern "C" JNIEXPORT void JNICALL
Java_com_miguelduval_mozart_MainActivity_nativeSetPatternAccent(
        JNIEnv*,
        jobject,
        jint accent) {
    switch (accent) {
        case 0:
            runtime()->setPatternAccent(
                    mozart::generation::PatternAccent::Off);
            break;
        case 1:
            runtime()->setPatternAccent(
                    mozart::generation::PatternAccent::Mild);
            break;
        case 2:
            runtime()->setPatternAccent(
                    mozart::generation::PatternAccent::Strong);
            break;
        default:
            return;
    }
}

extern "C" JNIEXPORT void JNICALL
Java_com_miguelduval_mozart_MainActivity_nativeSetPatternDensity(
        JNIEnv*,
        jobject,
        jint density) {
    switch (density) {
        case 0:
            runtime()->setPatternDensity(
                    mozart::generation::PatternDensity::Sparse);
            break;
        case 1:
            runtime()->setPatternDensity(
                    mozart::generation::PatternDensity::Normal);
            break;
        case 2:
            runtime()->setPatternDensity(
                    mozart::generation::PatternDensity::Full);
            break;
        default:
            return;
    }
}

extern "C" JNIEXPORT void JNICALL
Java_com_miguelduval_mozart_MainActivity_nativeSetAccompanimentRole(
        JNIEnv*,
        jobject,
        jint role) {
    switch (role) {
        case 0:
            runtime()->setAccompanimentRole(
                    mozart::scheduler::AccompanimentRole::Bass);
            break;
        case 1:
            runtime()->setAccompanimentRole(
                    mozart::scheduler::AccompanimentRole::Arpeggio);
            break;
        default:
            return;
    }
}

extern "C" JNIEXPORT void JNICALL
Java_com_miguelduval_mozart_MainActivity_nativeStopAccompaniment(
        JNIEnv*,
        jobject) {
    auto* app = runtime();
    app->setAccompanimentEnabled(false);
    app->setLinkEnabled(false);
}

extern "C" JNIEXPORT void JNICALL
Java_com_miguelduval_mozart_MainActivity_nativeSetManualKeyScale(
        JNIEnv*,
        jobject,
        jint rootPitchClass,
        jint scaleId) {
    if (rootPitchClass < 0 || rootPitchClass > 11 ||
        scaleId < 0 || scaleId > 2) {
        return;
    }

    runtime()->setKeyScale(
            mozart::musical::KeyScale{
                    static_cast<std::uint8_t>(rootPitchClass),
                    static_cast<mozart::musical::Scale>(scaleId)});
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
        candidate.deviceId =
                static_cast<std::uint32_t>(intAt(env, deviceIds, i));
        candidate.portNumber =
                static_cast<std::uint32_t>(intAt(env, portNumbers, i));
        candidate.direction =
                portDirectionFromAndroid(intAt(env, portTypes, i));
        candidate.transport =
                transportKindFromAndroid(intAt(env, transportTypes, i));
        candidate.name = javaStringToUtf8(env, names, i);
        candidate.manufacturer = javaStringToUtf8(env, manufacturers, i);
        candidate.product = javaStringToUtf8(env, products, i);
        candidates.push_back(std::move(candidate));
    }

    const auto selection =
            mozart::midi::MidiEndpointSelector::selectPreferredOutput(
                    candidates, "Arturia", "MicroFreak");

    return selection.selected()
            ? static_cast<jint>(*selection.candidateIndex)
            : static_cast<jint>(-1);
}

extern "C" JNIEXPORT jint JNICALL
Java_com_miguelduval_mozart_AndroidMidiTransport_nativeOpenMidiOutputDevice(
        JNIEnv* env,
        jclass,
        jobject midiDevice,
        jint portNumber) {
    return static_cast<jint>(
            g_midiOutput.open(env, midiDevice, static_cast<std::int32_t>(portNumber)));
}

extern "C" JNIEXPORT void JNICALL
Java_com_miguelduval_mozart_AndroidMidiTransport_nativeCloseMidiOutputDevice(
        JNIEnv*,
        jclass) {
    g_midiOutput.close();
}

extern "C" JNIEXPORT jint JNICALL
Java_com_miguelduval_mozart_AndroidMidiTransport_nativeSendShortMessage(
        JNIEnv*,
        jclass,
        jint status,
        jint data1,
        jint data2,
        jint size,
        jlong timestampNanos) {
    if (status < 0 || status > 255 ||
        data1 < 0 || data1 > 255 ||
        data2 < 0 || data2 > 255 ||
        size < 0 || size > 3 ||
        timestampNanos < 0) {
        return static_cast<jint>(
                mozart::midi::MidiTransportStatus::InvalidMessage);
    }

    const mozart::midi::MidiShortMessage message{
        static_cast<std::uint8_t>(status),
        static_cast<std::uint8_t>(data1),
        static_cast<std::uint8_t>(data2),
        static_cast<std::uint8_t>(size),
        static_cast<std::uint64_t>(timestampNanos),
        0
    };

    const auto result = g_midiOutput.send(message);
    return static_cast<jint>(result.status);
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_miguelduval_mozart_AndroidMidiTransport_nativeIsMidiOutputOpenInternal(
        JNIEnv*,
        jclass) {
    return g_midiOutput.isOpen() ? JNI_TRUE : JNI_FALSE;
}
