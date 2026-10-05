#pragma once

#include "generation/TokenInferenceBackend.h"

#include <cstddef>
#include <cstdint>
#include <mutex>
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

struct ModelSelectionSnapshot final {
    std::string modelId{};
    TokenInferenceBackend* backend = nullptr;
    std::uint64_t selectionGeneration = 0;
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
            const std::string_view modelId) {
        std::lock_guard<std::mutex> lock(selectionMutex_);
        for (const auto& model : models_) {
            if (model.modelId != modelId || !model.enabled) {
                continue;
            }

            auto* backend = resolveBackend(model.modelId);
            if (backend == nullptr || !backend->isAvailable()) {
                return false;
            }

            selectedModelId_ = model.modelId;
            ++selectionGeneration_;
            return true;
        }
        return false;
    }

    void clearSelection() noexcept {
        std::lock_guard<std::mutex> lock(selectionMutex_);
        if (!selectedModelId_.empty()) {
            selectedModelId_.clear();
            ++selectionGeneration_;
        }
    }

    [[nodiscard]] std::uint64_t selectionGeneration() const noexcept {
        std::lock_guard<std::mutex> lock(selectionMutex_);
        return selectionGeneration_;
    }

    [[nodiscard]] const ModelCatalogEntry* selectedModel() const noexcept {
        std::lock_guard<std::mutex> lock(selectionMutex_);
        return findModel(selectedModelId_);
    }

    [[nodiscard]] const ModelCatalogEntry* modelAt(
            const std::size_t index) const noexcept {
        return index < models_.size() ? &models_[index] : nullptr;
    }

    [[nodiscard]] std::string selectedModelId() const {
        std::lock_guard<std::mutex> lock(selectionMutex_);
        return selectedModelId_;
    }

    [[nodiscard]] ModelSelectionSnapshot selectionSnapshot() const {
        std::lock_guard<std::mutex> lock(selectionMutex_);
        return {
                selectedModelId_,
                resolveBackend(selectedModelId_),
                selectionGeneration_
        };
    }

    [[nodiscard]] bool setEnabled(
            const std::string_view modelId,
            const bool enabled) noexcept {
        std::lock_guard<std::mutex> lock(selectionMutex_);
        for (auto& model : models_) {
            if (model.modelId == modelId) {
                model.enabled = enabled;
                if (!enabled && selectedModelId_ == model.modelId) {
                    selectedModelId_.clear();
                    ++selectionGeneration_;
                }
                return true;
            }
        }
        return false;
    }

    [[nodiscard]] TokenInferenceBackend* resolveSelectedBackend() const noexcept {
        std::lock_guard<std::mutex> lock(selectionMutex_);
        return resolveBackend(selectedModelId_);
    }

    [[nodiscard]] bool selectedBackendAvailable() const noexcept {
        std::lock_guard<std::mutex> lock(selectionMutex_);
        const auto* backend = resolveBackend(selectedModelId_);
        return backend != nullptr && backend->isAvailable();
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
        std::lock_guard<std::mutex> lock(selectionMutex_);
        models_.clear();
        backends_.clear();
        if (!selectedModelId_.empty()) {
            selectedModelId_.clear();
            ++selectionGeneration_;
        } else {
            selectedModelId_.clear();
        }
    }

private:
    mutable std::mutex selectionMutex_;
    std::vector<ModelCatalogEntry> models_{};
    std::vector<TokenInferenceBackend*> backends_{};
    std::string selectedModelId_{};
    std::uint64_t selectionGeneration_ = 0;
};

} // namespace mozart::generation
