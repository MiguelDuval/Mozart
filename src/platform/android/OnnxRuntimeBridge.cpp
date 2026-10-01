#include "platform/android/OnnxRuntimeBridge.h"

#include "generation/MidiEventVocabulary.h"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <sstream>
#include <string>
#include <vector>

namespace mozart::platform::android {

[[nodiscard]] std::string jsonForRequest(
        const generation::GenerationRequest& request) {
    std::ostringstream json;
    json << R"({"style":)" << static_cast<int>(request.style)
         << R"(,"substyle":)" << static_cast<int>(request.substyle)
         << R"(,"mood":)" << static_cast<int>(request.mood)
         << R"(,"rhythm":)" << static_cast<int>(request.rhythm)
         << R"(,"role":)" << static_cast<int>(request.role)
         << R"(,"root_pitch_class":)"
         << static_cast<int>(request.keyScale.rootPitchClass())
         << R"(,"scale":)"
         << static_cast<int>(request.keyScale.scale())
         << R"(,"tempo_bpm":)" << request.tempoBpm
         << R"(,"bars":)" << static_cast<int>(request.bars)
         << R"(,"polyphony":)" << static_cast<int>(request.polyphony)
         << R"(,"min_note":)" << static_cast<int>(request.minNote)
         << R"(,"max_note":)" << static_cast<int>(request.maxNote)
         << R"(,"density":)" << request.density
         << R"(,"probability":)" << request.probability
         << R"(,"ratchet":)" << static_cast<int>(request.ratchet)
         << R"(,"energy":)" << request.energy
         << R"(,"syncopation":)" << request.syncopation
         << R"(,"swing":)" << request.swing
         << R"(,"variation":)" << request.variation
         << R"(,"seed":)" << request.seed
         << "}";
    return json.str();
}

namespace {

void clearJniException(JNIEnv* env) noexcept {
    if (env != nullptr && env->ExceptionCheck()) {
        env->ExceptionClear();
    }
}

[[nodiscard]] std::string fromJavaString(
        JNIEnv* env,
        jstring value) {
    if (env == nullptr || value == nullptr) {
        return {};
    }

    const char* utf = env->GetStringUTFChars(value, nullptr);
    if (utf == nullptr) {
        clearJniException(env);
        return {};
    }

    const std::string result(utf);
    env->ReleaseStringUTFChars(value, utf);
    return result;
}

[[nodiscard]] generation::TokenInferenceResult parseResponse(
        const std::string& response) {
    std::istringstream stream(response);
    std::string status;
    std::string confidence;
    std::string generationMs;
    std::string tokens;
    std::string message;

    if (!std::getline(stream, status, '|') ||
        !std::getline(stream, confidence, '|') ||
        !std::getline(stream, generationMs, '|') ||
        !std::getline(stream, tokens, '|')) {
        return {
                generation::TokenInferenceStatus::Failed,
                {},
                0.0,
                0,
                "malformed ONNX bridge response"
        };
    }

    // An empty final message is valid and may be represented by a trailing
    // separator. Treat EOF with no message as an empty message, not as a
    // malformed response.
    if (!std::getline(stream, message) && !stream.eof()) {
        return {
                generation::TokenInferenceStatus::Failed,
                {},
                0.0,
                0,
                "malformed ONNX bridge response"
        };
    }

    std::uint64_t confidenceMicro = 0;
    std::uint64_t elapsedMs = 0;

    try {
        confidenceMicro = std::stoull(confidence);
        elapsedMs = std::stoull(generationMs);
    } catch (...) {
        return {
                generation::TokenInferenceStatus::Failed,
                {},
                0.0,
                0,
                "malformed ONNX bridge metadata"
        };
    }

    generation::TokenInferenceResult result;
    result.confidence =
            static_cast<double>(confidenceMicro) / 1'000'000.0;
    result.generationTimeMs =
            elapsedMs > 0xFFFFFFFFULL
                    ? 0xFFFFFFFFU
                    : static_cast<std::uint32_t>(elapsedMs);
    result.message = message;

    if (status == "UNAVAILABLE") {
        result.status = generation::TokenInferenceStatus::Unavailable;
        return result;
    }

    if (status == "FAILED") {
        result.status = generation::TokenInferenceStatus::Failed;
        return result;
    }

    if (status != "OK") {
        result.status = generation::TokenInferenceStatus::Failed;
        result.message = "unknown ONNX bridge response status";
        return result;
    }

    result.status = generation::TokenInferenceStatus::Ok;

    if (tokens.empty()) {
        result.message = "ONNX bridge returned no tokens";
        result.status = generation::TokenInferenceStatus::Failed;
        return result;
    }

    std::istringstream tokenStream(tokens);
    std::string value;
    while (std::getline(tokenStream, value, ',')) {
        if (value.empty()) {
            result.status = generation::TokenInferenceStatus::Failed;
            result.message = "ONNX bridge returned an empty token";
            result.tokens.clear();
            return result;
        }

        unsigned long long parsed = 0;
        try {
            parsed = std::stoull(value);
        } catch (...) {
            result.status = generation::TokenInferenceStatus::Failed;
            result.message = "ONNX bridge returned a non-integer token";
            result.tokens.clear();
            return result;
        }

        if (parsed > 0xFFFFULL) {
            result.status = generation::TokenInferenceStatus::Failed;
            result.message = "ONNX bridge returned an out-of-range token";
            result.tokens.clear();
            return result;
        }

        const auto token =
                static_cast<generation::MidiEventToken>(parsed);
        if (!generation::midi_event_vocabulary::isValidToken(token)) {
            result.status = generation::TokenInferenceStatus::Failed;
            result.message = "ONNX bridge returned a non-Mozart token";
            result.tokens.clear();
            return result;
        }

        result.tokens.push_back(token);
    }

    if (result.tokens.size() < 2 ||
        result.tokens.front() != generation::midi_event_vocabulary::kBos ||
        result.tokens.back() != generation::midi_event_vocabulary::kEos) {
        result.status = generation::TokenInferenceStatus::Failed;
        result.message = "ONNX bridge token stream is not BOS/EOS terminated";
        result.tokens.clear();
    }

    return result;
}

} // namespace

OnnxRuntimeBridge::OnnxRuntimeBridge(JNIEnv* env) noexcept {
    if (env == nullptr) {
        return;
    }

    if (env->GetJavaVM(&vm_) != JNI_OK || vm_ == nullptr) {
        vm_ = nullptr;
        return;
    }

    const auto localClass =
            env->FindClass("com/miguelduval/mozart/OnnxInferenceBridge");
    if (localClass == nullptr) {
        clearJniException(env);
        return;
    }

    bridgeClass_ =
            static_cast<jclass>(env->NewGlobalRef(localClass));
    env->DeleteLocalRef(localClass);
    if (bridgeClass_ == nullptr) {
        clearJniException(env);
        return;
    }

    runtimeAvailableMethod_ =
            env->GetStaticMethodID(
                    bridgeClass_,
                    "isRuntimeAvailable",
                    "()Z");
    generateMethod_ =
            env->GetStaticMethodID(
                    bridgeClass_,
                    "generate",
                    "(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;I)Ljava/lang/String;");
    if (runtimeAvailableMethod_ == nullptr ||
        generateMethod_ == nullptr) {
        clearJniException(env);
        return;
    }

    runtimeAvailable_ =
            env->CallStaticBooleanMethod(
                    bridgeClass_,
                    runtimeAvailableMethod_) == JNI_TRUE;
    if (env->ExceptionCheck()) {
        clearJniException(env);
        runtimeAvailable_ = false;
    }
}

OnnxRuntimeBridge::~OnnxRuntimeBridge() {
    if (vm_ == nullptr || bridgeClass_ == nullptr) {
        return;
    }

    JNIEnv* env = nullptr;
    bool attached = false;
    const auto status = vm_->GetEnv(
            reinterpret_cast<void**>(&env),
            JNI_VERSION_1_6);

    if (status == JNI_EDETACHED) {
        if (vm_->AttachCurrentThread(&env, nullptr) != JNI_OK) {
            return;
        }
        attached = true;
    } else if (status != JNI_OK || env == nullptr) {
        return;
    }

    env->DeleteGlobalRef(bridgeClass_);
    bridgeClass_ = nullptr;

    if (attached) {
        vm_->DetachCurrentThread();
    }
}

generation::TokenInferenceResult OnnxRuntimeBridge::infer(
        const std::string& artifactPath,
        const std::string& manifestPath,
        const generation::GenerationRequest& request,
        const std::size_t maxTokens) {
    if (!isRuntimeAvailable()) {
        return {
                generation::TokenInferenceStatus::Unavailable,
                {},
                0.0,
                0,
                "ONNX Runtime backend is unavailable"
        };
    }

    if (vm_ == nullptr || bridgeClass_ == nullptr ||
        generateMethod_ == nullptr) {
        return {
                generation::TokenInferenceStatus::Unavailable,
                {},
                0.0,
                0,
                "ONNX Runtime JNI bridge is unavailable"
        };
    }

    JNIEnv* env = nullptr;
    bool attached = false;

    const auto status = vm_->GetEnv(
            reinterpret_cast<void**>(&env),
            JNI_VERSION_1_6);

    if (status == JNI_EDETACHED) {
        if (vm_->AttachCurrentThread(&env, nullptr) != JNI_OK) {
            return {
                    generation::TokenInferenceStatus::Unavailable,
                    {},
                    0.0,
                    0,
                    "ONNX Runtime JNI thread attach failed"
            };
        }
        attached = true;
    } else if (status != JNI_OK || env == nullptr) {
        return {
                generation::TokenInferenceStatus::Unavailable,
                {},
                0.0,
                0,
                "ONNX Runtime JNI environment unavailable"
        };
    }

    generation::TokenInferenceResult result;

    const auto artifact = env->NewStringUTF(artifactPath.c_str());
    const auto manifest = env->NewStringUTF(manifestPath.c_str());
    const auto requestString =
            jsonForRequest(request);
    const auto requestJson =
            env->NewStringUTF(requestString.c_str());

    if (artifact == nullptr || manifest == nullptr || requestJson == nullptr) {
        clearJniException(env);
        result = {
                generation::TokenInferenceStatus::Failed,
                {},
                0.0,
                0,
                "ONNX Runtime JNI string allocation failed"
        };
    } else {
        const auto response = static_cast<jstring>(
                env->CallStaticObjectMethod(
                        bridgeClass_,
                        generateMethod_,
                        artifact,
                        manifest,
                        requestJson,
                        static_cast<jint>(
                                std::min<std::size_t>(
                                        maxTokens,
                                        static_cast<std::size_t>(0x7FFFFFFF)))));

        if (env->ExceptionCheck() || response == nullptr) {
            clearJniException(env);
            result = {
                    generation::TokenInferenceStatus::Failed,
                    {},
                    0.0,
                    0,
                    "ONNX Runtime bridge call failed"
            };
        } else {
            result = parseResponse(fromJavaString(env, response));
            env->DeleteLocalRef(response);
        }
    }

    if (artifact != nullptr) {
        env->DeleteLocalRef(artifact);
    }
    if (manifest != nullptr) {
        env->DeleteLocalRef(manifest);
    }
    if (requestJson != nullptr) {
        env->DeleteLocalRef(requestJson);
    }

    if (attached) {
        vm_->DetachCurrentThread();
    }

    return result;
}

bool OnnxRuntimeBridge::isRuntimeAvailable() const noexcept {
    return vm_ != nullptr &&
            bridgeClass_ != nullptr &&
            runtimeAvailable_;
}

} // namespace mozart::platform::android
