#pragma once

#include "generation/MidiEventVocabulary.h"

#include <span>

namespace mozart::generation::midi_event_grammar {

[[nodiscard]] inline bool hasChannelToken(
        const std::span<const MidiEventToken> tokens) noexcept {
    for (const auto token : tokens) {
        if (token >= midi_event_vocabulary::kChannelBase &&
            token < midi_event_vocabulary::kNoteBase) {
            return true;
        }
    }
    return false;
}

[[nodiscard]] inline bool isAllowedNextToken(
        const std::span<const MidiEventToken> tokens,
        const MidiEventToken nextToken) noexcept {
    if (tokens.empty() ||
        !midi_event_vocabulary::isValidToken(nextToken)) {
        return false;
    }

    const auto last = tokens.back();

    if (last == midi_event_vocabulary::kBos) {
        return (
                nextToken >= midi_event_vocabulary::kChannelBase &&
                nextToken < midi_event_vocabulary::kNoteBase) ||
                (
                nextToken >= midi_event_vocabulary::kTimeShiftBase &&
                nextToken < midi_event_vocabulary::kDurationBase);
    }

    if (last >= midi_event_vocabulary::kNoteBase &&
        last < midi_event_vocabulary::kVelocityBase) {
        return nextToken >= midi_event_vocabulary::kVelocityBase &&
                nextToken < midi_event_vocabulary::kTimeShiftBase;
    }

    if (last >= midi_event_vocabulary::kVelocityBase &&
        last < midi_event_vocabulary::kTimeShiftBase) {
        return nextToken >= midi_event_vocabulary::kDurationBase &&
                nextToken < midi_event_vocabulary::kControllerBase;
    }

    if (last >= midi_event_vocabulary::kControllerBase &&
        last < midi_event_vocabulary::kControlValueBase) {
        return nextToken >= midi_event_vocabulary::kControlValueBase &&
                nextToken < midi_event_vocabulary::kVocabularySize;
    }

    const bool eventCanFollow =
            nextToken == midi_event_vocabulary::kEos ||
            (nextToken >= midi_event_vocabulary::kChannelBase &&
             nextToken < midi_event_vocabulary::kNoteBase) ||
            (nextToken >= midi_event_vocabulary::kTimeShiftBase &&
             nextToken < midi_event_vocabulary::kDurationBase) ||
            (nextToken >= midi_event_vocabulary::kNoteBase &&
             nextToken < midi_event_vocabulary::kVelocityBase) ||
            (nextToken >= midi_event_vocabulary::kControllerBase &&
             nextToken < midi_event_vocabulary::kControlValueBase);

    if (last >= midi_event_vocabulary::kDurationBase &&
        last < midi_event_vocabulary::kControllerBase) {
        return eventCanFollow;
    }

    if (last >= midi_event_vocabulary::kControlValueBase &&
        last < midi_event_vocabulary::kVocabularySize) {
        return eventCanFollow;
    }

    if (last >= midi_event_vocabulary::kTimeShiftBase &&
        last < midi_event_vocabulary::kDurationBase) {
        if (!hasChannelToken(tokens)) {
            return (
                    nextToken >= midi_event_vocabulary::kChannelBase &&
                    nextToken < midi_event_vocabulary::kNoteBase) ||
                    (
                    nextToken >= midi_event_vocabulary::kTimeShiftBase &&
                    nextToken < midi_event_vocabulary::kDurationBase);
        }

        return (
                nextToken >= midi_event_vocabulary::kChannelBase &&
                nextToken < midi_event_vocabulary::kNoteBase) ||
                (
                nextToken >= midi_event_vocabulary::kTimeShiftBase &&
                nextToken < midi_event_vocabulary::kDurationBase) ||
                (
                nextToken >= midi_event_vocabulary::kNoteBase &&
                nextToken < midi_event_vocabulary::kVelocityBase) ||
                (
                nextToken >= midi_event_vocabulary::kControllerBase &&
                nextToken < midi_event_vocabulary::kControlValueBase);
    }

    if (last >= midi_event_vocabulary::kChannelBase &&
        last < midi_event_vocabulary::kNoteBase) {
        return (
                nextToken >= midi_event_vocabulary::kNoteBase &&
                nextToken < midi_event_vocabulary::kVelocityBase) ||
                (
                nextToken >= midi_event_vocabulary::kControllerBase &&
                nextToken < midi_event_vocabulary::kControlValueBase);
    }

    return false;
}

} // namespace mozart::generation::midi_event_grammar
