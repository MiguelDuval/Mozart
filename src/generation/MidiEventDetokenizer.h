#pragma once

#include "generation/MidiEventVocabulary.h"
#include "generation/PatternProposal.h"

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <optional>
#include <vector>

namespace mozart::generation {

class MidiEventDetokenizer final {
public:
    struct Options final {
        double beatGrid = midi_event_vocabulary::kBeatGrid;
        std::size_t maxEvents = PatternProposal::kMaxNoteEvents;
        std::int64_t maxTimeShiftSteps = 4096;
    };

    [[nodiscard]] static std::optional<PatternProposal> decode(
            const std::vector<MidiEventToken>& tokens) {
        return decode(tokens, Options{});
    }

    [[nodiscard]] static std::optional<PatternProposal> decode(
            const std::vector<MidiEventToken>& tokens,
            const Options& options) {
        if (tokens.size() < 2 ||
            tokens.front() != midi_event_vocabulary::kBos ||
            tokens.back() != midi_event_vocabulary::kEos ||
            options.maxEvents == 0 ||
            options.maxTimeShiftSteps <= 0 ||
            options.maxTimeShiftSteps >
                    std::numeric_limits<std::int64_t>::max() ||
            !isFinitePositive(options.beatGrid)) {
            return std::nullopt;
        }

        PatternProposal proposal;
        std::int64_t timeSteps = 0;
        std::uint8_t channel = 0;
        bool channelInitialized = false;

        std::size_t index = 1;
        while (index + 1 < tokens.size()) {
            const auto token = tokens[index];

            if (!midi_event_vocabulary::isValidToken(token) ||
                token == midi_event_vocabulary::kPad ||
                token == midi_event_vocabulary::kBos ||
                token == midi_event_vocabulary::kEos) {
                return std::nullopt;
            }

            if (isChannelToken(token)) {
                channel = static_cast<std::uint8_t>(
                        token - midi_event_vocabulary::kChannelBase);
                channelInitialized = true;
                ++index;
                continue;
            }

            if (isTimeShiftToken(token)) {
                const auto steps = static_cast<std::int64_t>(
                        token - midi_event_vocabulary::kTimeShiftBase + 1);
                if (steps <= 0 ||
                    timeSteps >
                            options.maxTimeShiftSteps - steps) {
                    return std::nullopt;
                }
                timeSteps += steps;
                ++index;
                continue;
            }

            if (!channelInitialized) {
                return std::nullopt;
            }

            if (isNoteToken(token)) {
                if (index + 1 >= tokens.size()) {
                    return std::nullopt;
                }

                const auto velocityToken = tokens[index + 1];
                const auto durationToken = tokens[index + 2];
                if (!isVelocityToken(velocityToken) ||
                    !isDurationToken(durationToken)) {
                    return std::nullopt;
                }

                if (proposal.noteEvents.size() >= options.maxEvents) {
                    return std::nullopt;
                }

                const auto note = static_cast<std::uint8_t>(
                        token - midi_event_vocabulary::kNoteBase);
                const auto velocityBin = static_cast<std::uint8_t>(
                        velocityToken -
                        midi_event_vocabulary::kVelocityBase + 1);
                const auto durationSteps = static_cast<std::size_t>(
                        durationToken -
                        midi_event_vocabulary::kDurationBase + 1);

                proposal.noteEvents.push_back(
                        musical::MusicalNoteEvent{
                                static_cast<double>(timeSteps) *
                                        options.beatGrid,
                                static_cast<double>(durationSteps) *
                                        options.beatGrid,
                                note,
                                expandBin32(velocityBin),
                                channel});
                index += 3;
                continue;
            }

            if (isControllerToken(token)) {
                if (index + 2 >= tokens.size()) {
                    return std::nullopt;
                }

                const auto valueToken = tokens[index + 1];
                if (!isControlValueToken(valueToken)) {
                    return std::nullopt;
                }

                if (proposal.controlEvents.size() >=
                        PatternProposal::kMaxControlEvents) {
                    return std::nullopt;
                }

                const auto controller = static_cast<std::uint8_t>(
                        token - midi_event_vocabulary::kControllerBase);
                const auto valueBin = static_cast<std::uint8_t>(
                        valueToken -
                        midi_event_vocabulary::kControlValueBase + 1);

                proposal.controlEvents.push_back(
                        PatternControlEvent{
                                static_cast<double>(timeSteps) *
                                        options.beatGrid,
                                channel,
                                controller,
                                expandBin32(valueBin)});
                index += 2;
                continue;
            }

            return std::nullopt;
        }

        if (!proposal.isWellFormed() ||
            proposal.noteEvents.size() + proposal.controlEvents.size() >
                    options.maxEvents) {
            return std::nullopt;
        }

        return proposal;
    }

private:
    [[nodiscard]] static bool isFinitePositive(const double value) noexcept {
        return std::isfinite(value) && value > 0.0;
    }

    [[nodiscard]] static bool isChannelToken(
            const MidiEventToken token) noexcept {
        return token >= midi_event_vocabulary::kChannelBase &&
                token < midi_event_vocabulary::kNoteBase;
    }

    [[nodiscard]] static bool isNoteToken(
            const MidiEventToken token) noexcept {
        return token >= midi_event_vocabulary::kNoteBase &&
                token < midi_event_vocabulary::kVelocityBase;
    }

    [[nodiscard]] static bool isVelocityToken(
            const MidiEventToken token) noexcept {
        return token >= midi_event_vocabulary::kVelocityBase &&
                token < midi_event_vocabulary::kTimeShiftBase;
    }

    [[nodiscard]] static bool isTimeShiftToken(
            const MidiEventToken token) noexcept {
        return token >= midi_event_vocabulary::kTimeShiftBase &&
                token < midi_event_vocabulary::kDurationBase;
    }

    [[nodiscard]] static bool isDurationToken(
            const MidiEventToken token) noexcept {
        return token >= midi_event_vocabulary::kDurationBase &&
                token < midi_event_vocabulary::kControllerBase;
    }

    [[nodiscard]] static bool isControllerToken(
            const MidiEventToken token) noexcept {
        return token >= midi_event_vocabulary::kControllerBase &&
                token < midi_event_vocabulary::kControlValueBase;
    }

    [[nodiscard]] static bool isControlValueToken(
            const MidiEventToken token) noexcept {
        return token >= midi_event_vocabulary::kControlValueBase &&
                token < midi_event_vocabulary::kVocabularySize;
    }

    [[nodiscard]] static std::uint8_t expandBin32(
            const std::uint8_t bin) noexcept {
        if (bin <= 1) {
            return 0;
        }
        if (bin >= 32) {
            return 127;
        }
        return static_cast<std::uint8_t>(
                ((static_cast<unsigned int>(bin) - 1U) * 127U + 16U) /
                32U);
    }
};

} // namespace mozart::generation
