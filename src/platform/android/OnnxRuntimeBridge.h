#pragma once

#include "generation/OnnxTokenInferenceBackend.h"

#include <jni.h>

#include <cstddef>
#include <string>

namespace mozart::platform::android {

class OnnxRuntimeBridge final : public generation::OnnxInferenceBridge {
public:
    explicit OnnxRuntimeBridge(JNIEnv* env) noexcept;
    ~OnnxRuntimeBridge() override;

    OnnxRuntimeBridge(const OnnxRuntimeBridge&) = delete;
    OnnxRuntimeBridge& operator=(const OnnxRuntimeBridge&) = delete;

    [[nodiscard]] generation::TokenInferenceResult infer(
            const std::string& artifactPath,
            const std::string& manifestPath,
            const generation::GenerationRequest& request,
            std::size_t maxTokens) override;

    [[nodiscard]] bool isRuntimeAvailable() const noexcept override;

private:
    JavaVM* vm_ = nullptr;
    jclass bridgeClass_ = nullptr;
    jmethodID runtimeAvailableMethod_ = nullptr;
    jmethodID generateMethod_ = nullptr;
    bool runtimeAvailable_ = false;
};

} // namespace mozart::platform::android
