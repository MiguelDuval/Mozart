#pragma once

#include "generation/OnnxTokenInferenceBackend.h"
#include "generation/RemiBpeInferenceBackend.h"

#include <jni.h>

#include <cstddef>
#include <string>

namespace mozart::platform::android {

class OnnxRuntimeBridge final : public generation::OnnxInferenceBridge,
                                public generation::RemiBpeOnnxInferenceBridge {
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

    [[nodiscard]] generation::RemiBpeTokenInferenceResult inferRemiBpe(
            const std::string& artifactPath,
            const std::string& manifestPath,
            const std::string& tokenizerPath,
            std::size_t maxTokens) override;

    [[nodiscard]] bool isRuntimeAvailable() const noexcept override;

private:
    JavaVM* vm_ = nullptr;
    jclass bridgeClass_ = nullptr;
    jmethodID runtimeAvailableMethod_ = nullptr;
    jmethodID generateMethod_ = nullptr;
    jmethodID generateRemiBpeMethod_ = nullptr;
    bool runtimeAvailable_ = false;
};

} // namespace mozart::platform::android
