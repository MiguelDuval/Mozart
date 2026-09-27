#pragma once

#include "generation/MidiEventVocabulary.h"
#include "generation/PatternProposal.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <utility>
#include <vector>

namespace mozart::generation {

class MidiEventTokenizer final {
public:
    struct Options final {
        double beatGrid = midi_event_vocabulary::kBeatGrid;
        std::size_t maxTokens = 16384;
    };

    [[nodiscard]] static std::optional<std::vector<MidiEventToken>> encode(
            const PatternProposal& proposal,
            const Options& options = {}) {
        if (!proposal.isWellFormed() ||
            !std::isfinite(options.beatGrid) ||
            options.beatGrid <= 0.0 ||
            options.maxTokens < 2) {
            return std::nullopt;
        }

        struct Item final {
            std::int64_t startSteps = 0;
            std::size_t order = 0;
            bool isNote = true;
            const musical::MusicalNoteEvent* note = nullptr;
            const PatternControlEvent* control = nullptr;
        };

        const auto quantizeSteps =
                [grid = options.beatGrid](const double beat)
                -> std::optional<std::int64_t> {
            if (!std::isfinite(beat) || beat < 0.0) {
                return std::nullopt;
            }
            const double value = beat / grid;
            if (value > static_cast<double>(INT64_MAX)) {
                return std::nullopt;
            }
            return static_cast<std::int64_t>(
                    std::llround(value));
        };

        const auto durationSteps =
                [grid = options.beatGrid](const double duration)
                -> std::optional<std::size_t> {
            if (!std::isfinite(duration) || duration <= 0.0) {
                return std::nullopt;
            }
            const auto rounded =
                    static_cast<long long>(std::llround(duration / grid));
            if (rounded < 1 ||
                rounded > static_cast<long long>(
                                   midi_event_vocabulary::kMaxDurationSteps)) {
                return std::nullopt;
            }
            return static_cast<std::size_t>(rounded);
        };

        const auto quantizeBin32 =
                [](const std::uint8_t value) noexcept -> std::uint8_t {
            return static_cast<std::uint8_t>(
                    std::min<std::size_t>(
                            32,
                            (static_cast<std::size_t>(value) * 32U + 126U) /
                                    127U));
        };

        std::vector<Item> items;
        items.reserve(
                proposal.noteEvents.size() +
                proposal.controlEvents.size());

        std::size_t order = 0;
        for (const auto& event : proposal.noteEvents) {
            const auto start = quantizeSteps(event.startBeat);
            if (!start.has_value() || event.channel > 15) {
                return std::nullopt;
            }
            if (!durationSteps(event.durationBeats).has_value()) {
                return std::nullopt;
            }
            items.push_back(Item{
                    *start,
                    order++,
                    true,
                    &event,
                    nullptr});
        }

        for (const auto& event : proposal.controlEvents) {
            const auto start = quantizeSteps(event.startBeat);
            if (!start.has_value() || event.channel > 15 ||
                event.controller > 127) {
                return std::nullopt;
            }
            items.push_back(Item{
                    *start,
                    order++,
                    false,
                    nullptr,
                    &event});
        }

        std::stable_sort(
                items.begin(),
                items.end(),
                [](const Item& lhs, const Item& rhs) {
                    if (lhs.startSteps != rhs.startSteps) {
                        return lhs.startSteps < rhs.startSteps;
                    }
                    if (lhs.isNote != rhs.isNote) {
                        return lhs.isNote;
                    }
                    return lhs.order < rhs.order;
                });

        std::vector<MidiEventToken> tokens;
        tokens.reserve(
                std::min<std::size_t>(
                        options.maxTokens,
                        items.size() * 6U + 2U));
        tokens.push_back(midi_event_vocabulary::kBos);

        std::int64_t currentSteps = 0;
        std::uint8_t currentChannel = 0;
        bool channelInitialized = false;

        const auto push = [&](const MidiEventToken token) {
            tokens.push_back(token);
            return tokens.size() <= options.maxTokens;
        };

        const auto emitTimeShift = [&](std::int64_t deltaSteps) {
            while (deltaSteps > 0) {
                const auto chunk = static_cast<std::uint8_t>(
                        std::min<std::int64_t>(
                                deltaSteps,
                                static_cast<std::int64_t>(
                                        midi_event_vocabulary::kMaxTimeShiftSteps)));
                if (!push(midi_event_vocabulary::timeShiftToken(chunk))) {
                    return false;
                }
                deltaSteps -= chunk;
            }
            return true;
        };

        for (const auto& item : items) {
            if (item.startSteps < currentSteps) {
                return std::nullopt;
            }

            if (!emitTimeShift(item.startSteps - currentSteps)) {
                return std::nullopt;
            }
            currentSteps = item.startSteps;

            const auto channel =
                    item.isNote
                            ? item.note->channel
                            : item.control->channel;
            if (!channelInitialized || channel != currentChannel) {
                if (!push(midi_event_vocabulary::channelToken(channel))) {
                    return std::nullopt;
                }
                currentChannel = channel;
                channelInitialized = true;
            }

            if (item.isNote) {
                const auto& event = *item.note;
                const auto duration = durationSteps(event.durationBeats);
                if (!duration.has_value()) {
                    return std::nullopt;
                }

                if (!push(midi_event_vocabulary::noteToken(event.note)) ||
                    !push(midi_event_vocabulary::velocityToken(
                            quantizeBin32(event.velocity))) ||
                    !push(midi_event_vocabulary::durationToken(
                            static_cast<std::uint8_t>(*duration)))) {
                    return std::nullopt;
                }
            } else {
                const auto& event = *item.control;
                if (!push(
                            midi_event_vocabulary::controllerToken(
                                    event.controller)) ||
                    !push(
                            midi_event_vocabulary::controlValueToken(
                                    quantizeBin32(event.value)))) {
                    return std::nullopt;
                }
            }
        }

        if (!push(midi_event_vocabulary::kEos)) {
            return std::nullopt;
        }

        return tokens;
    }
};

} // namespace mozart::generation
