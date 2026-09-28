#pragma once

#include "generation/TokenInferenceBackend.h"

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace mozart::generation {

enum class ModelDistributionClass : std::uint8_t {
    Commercial = 0,
    PrivateExperimental = 1
};

struct ModelCatalogEntry final {
    std::string modelId{};
    std::string displayName{};
    std::string backendId{};
    std::string artifactPath{};
    std::string manifestPath{};
    ModelDistributionClass distributionClass =
            ModelDistributionClass::PrivateExperimental;
    bool enabled = true;
};

class ModelCatalog final {
public:
    // The catalog does not own backends. Their lifetime must exceed the catalog.
    // Backend calls remain worker-thread-only and must never reach realtime code.
    [[nodiscard]] bool registerBackend(
            TokenInferenceBackend& backend) {
        if (backend.id().empty()) {
            return false;
        }

        for (auto* existing : backends_) {
            if (existing != nullptr && existing->id() == backend.id()) {
                return false;
            }
        }

        backends_.push_back(&backend);
        return true;
    }

    [[nodiscard]] bool registerModel(ModelCatalogEntry entry) {
        if (entry.modelId.empty() ||
                entry.backendId.empty() ||
                entry.displayName.empty()) {
            return false;
        }

        if (findModel(entry.modelId) != nullptr) {
            return false;
        }

        models_.push_back(std::move(entry));
        return true;
    }

    [[nodiscard]] const ModelCatalogEntry* findModel(
            const std::string_view modelId) const noexcept {
        for (const auto& model : models_) {
            if (model.modelId == modelId) {
                return &model;
            }
        }
        return nullptr;
    }

    [[nodiscard]] bool selectModel(
            const std::string_view modelId) noexcept {
        for (const auto& model : models_) {
            if (model.modelId == modelId && model.enabled) {
                selectedModelId_ = model.modelId;
                return true;
            }
        }
        return false;
    }

    void clearSelection() noexcept {
        selectedModelId_.clear();
    }

    [[nodiscard]] const ModelCatalogEntry* selectedModel() const noexcept {
        return findModel(selectedModelId_);
    }

    [[nodiscard]] std::string selectedModelId() const {
        return selectedModelId_;
    }

    [[nodiscard]] bool setEnabled(
            const std::string_view modelId,
            const bool enabled) noexcept {
        for (auto& model : models_) {
            if (model.modelId == modelId) {
                model.enabled = enabled;
                return true;
            }
        }
        return false;
    }

    [[nodiscard]] TokenInferenceBackend* resolveBackend(
            const std::string_view modelId) const noexcept {
        const auto* model = findModel(modelId);
        if (model == nullptr || !model->enabled) {
            return nullptr;
        }

        for (auto* backend : backends_) {
            if (backend != nullptr && backend->id() == model->backendId) {
                return backend;
            }
        }
        return nullptr;
    }

    [[nodiscard]] bool isPrivateExperimental(
            const std::string_view modelId) const noexcept {
        const auto* model = findModel(modelId);
        return model != nullptr &&
                model->distributionClass ==
                        ModelDistributionClass::PrivateExperimental;
    }

    [[nodiscard]] std::size_t modelCount() const noexcept {
        return models_.size();
    }

    [[nodiscard]] std::size_t backendCount() const noexcept {
        return backends_.size();
    }

    void clear() noexcept {
        models_.clear();
        backends_.clear();
        selectedModelId_.clear();
    }

private:
    std::vector<ModelCatalogEntry> models_{};
    std::vector<TokenInferenceBackend*> backends_{};
    std::string selectedModelId_{};
};

} // namespace mozart::generation
