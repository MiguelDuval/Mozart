#include "core/MidiTypes.h"
#include "core/TransportMath.h"
#include "core/Track.h"
#include "core/MidiEvent.h"
#include "core/Pattern.h"
#include "core/Project.h"
#include "core/ChannelMixer.h"
#include "core/Metronome.h"
#include "generation/RhythmGenerator.h"

#include <cassert>
#include <cmath>
#include <cstdint>

int main() {
    {
        const auto message = mozart::midi::noteOn(0, 60, 100, 1234, 7);
        assert(message.has_value());
        assert(message->status == 0x90);
        assert(message->data1 == 60);
        assert(message->data2 == 100);
        assert(message->size == 3);
        assert(message->timestampNanos == 1234);
        assert(message->portId == 7);
        assert(message->isValid());
    }

    {
        assert(!mozart::midi::noteOn(16, 60, 100).has_value());
        assert(!mozart::midi::noteOn(0, 128, 100).has_value());
        assert(!mozart::midi::controlChange(0, 0, 128).has_value());
    }

    {
        const auto beat = mozart::timing::beatAtTime(0.0, 0.0, 120.0, 1.0);
        assert(std::abs(beat - 2.0) < 1.0e-12);
        assert(std::abs(mozart::timing::quantizeBeat(3.2, 4.0) - 4.0) < 1.0e-12);
    }

    {
        const auto pattern = mozart::generation::RhythmGenerator::euclidean(16, 4);
        assert(pattern.size() == 16);
        assert(pattern[0] && pattern[4] && pattern[8] && pattern[12]);
    }

    {
        const auto a = mozart::generation::RhythmGenerator::seededVelocityPattern(32, 42);
        const auto b = mozart::generation::RhythmGenerator::seededVelocityPattern(32, 42);
        assert(a == b);
        assert(a.size() == 32);
    }

    // --- Track tests ---

    {
        mozart::Track track(1, "Test Track");
        assert(track.id() == 1);
        assert(track.name() == "Test Track");
        assert(std::abs(track.level() - 1.0f) < 1.0e-6);
        assert(std::abs(track.pan() - 0.0f) < 1.0e-6);
        assert(!track.isMuted());
    }

    {
        mozart::Track track(2, "Level Test");
        track.setLevel(0.5f);
        assert(std::abs(track.level() - 0.5f) < 1.0e-6);
        track.setLevel(0.0f);
        assert(std::abs(track.level() - 0.0f) < 1.0e-6);
        track.setLevel(1.0f);
        assert(std::abs(track.level() - 1.0f) < 1.0e-6);
        track.setLevel(2.0f);
        assert(std::abs(track.level() - 1.0f) < 1.0e-6);
        track.setLevel(-1.0f);
        assert(std::abs(track.level() - 0.0f) < 1.0e-6);
    }

    {
        mozart::Track track(3, "Pan Test");
        track.setPan(0.0f);
        assert(std::abs(track.pan() - 0.0f) < 1.0e-6);
        track.setPan(-1.0f);
        assert(std::abs(track.pan() - (-1.0f)) < 1.0e-6);
        track.setPan(1.0f);
        assert(std::abs(track.pan() - 1.0f) < 1.0e-6);
        track.setPan(2.0f);
        assert(std::abs(track.pan() - 1.0f) < 1.0e-6);
        track.setPan(-2.0f);
        assert(std::abs(track.pan() - (-1.0f)) < 1.0e-6);
    }

    {
        mozart::Track track(4, "Mute Test");
        assert(!track.isMuted());
        track.setMuted(true);
        assert(track.isMuted());
        track.setMuted(false);
        assert(!track.isMuted());
    }

    // --- ChannelMixer tests ---

    {
        mozart::ChannelMixer mixer;

        mozart::Track track1(10, "Track 1");
        mozart::Track track2(20, "Track 2");

        mixer.addTrack(&track1);
        mixer.addTrack(&track2);

        const float in[4] = {1.0f, 1.0f, 1.0f, 1.0f};
        float out[8] = {0};

        track1.setLevel(1.0f);
        track1.setPan(0.0f);
        track2.setLevel(1.0f);
        track2.setPan(0.0f);

        mixer.process(in, out, 4);

        const float expected = 2.0f * 0.70710678f;
        assert(std::abs(out[0] - expected) < 0.01f);
        assert(std::abs(out[1] - expected) < 0.01f);
    }

    {
        mozart::ChannelMixer mixer;
        mozart::Track track(30, "Level Track");
        mixer.addTrack(&track);

        const float in[2] = {1.0f, 1.0f};
        float out[4] = {0};

        track.setLevel(0.0f);
        mixer.process(in, out, 2);
        assert(std::abs(out[0]) < 1.0e-6);
        assert(std::abs(out[1]) < 1.0e-6);

        track.setLevel(0.5f);
        mixer.process(in, out, 2);
        const float halfGain = 0.5f * 0.70710678f;
        assert(std::abs(out[0] - halfGain) < 0.01f);
        assert(std::abs(out[1] - halfGain) < 0.01f);
    }

    {
        mozart::ChannelMixer mixer;
        mozart::Track track1(40, "Pan Left");
        mozart::Track track2(50, "Pan Right");
        mixer.addTrack(&track1);
        mixer.addTrack(&track2);

        const float in[2] = {1.0f, 1.0f};
        float out[4] = {0};

        track1.setLevel(1.0f);
        track1.setPan(-1.0f);
        track2.setLevel(1.0f);
        track2.setPan(1.0f);

        mixer.process(in, out, 2);

        assert(std::abs(out[0] - 1.0f) < 0.05f);
        assert(std::abs(out[1] - 1.0f) < 0.05f);
    }

    {
        mozart::ChannelMixer mixer;
        mozart::Track track(60, "Muted Track");
        mixer.addTrack(&track);

        const float in[2] = {1.0f, 1.0f};
        float out[4] = {0};

        track.setLevel(1.0f);
        track.setMuted(true);
        mixer.process(in, out, 2);
        assert(std::abs(out[0]) < 1.0e-6);
        assert(std::abs(out[1]) < 1.0e-6);

        track.setMuted(false);
        mixer.process(in, out, 2);
        assert(std::abs(out[0]) > 0.01f);
        assert(std::abs(out[1]) > 0.01f);
    }

    // --- Metronome tests ---

    {
        mozart::Metronome metro;
        assert(!metro.enabled());
        assert(metro.sound() == mozart::MetronomeSound::Click);
        assert(std::abs(metro.bpm() - 120.0f) < 0.001f);
        assert(metro.timeSignatureNumerator() == 4);
        assert(metro.timeSignatureDenominator() == 4);
    }

    {
        mozart::Metronome metro;
        metro.setEnabled(true);
        metro.setSound(mozart::MetronomeSound::Click);
        metro.setVolume(1.0f);

        float l = 0.0f, r = 0.0f;
        bool pulsed = metro.process(44100.0f, 0.5, l, r);
        assert(pulsed);
        assert(std::abs(l) > 0.01f);
        assert(std::abs(r) > 0.01f);
        assert(std::abs(l - r) < 0.001f);
    }

    {
        mozart::Metronome metro;
        metro.setEnabled(true);
        metro.setSound(mozart::MetronomeSound::Click);
        metro.setVolume(0.0f);

        float l = 0.0f, r = 0.0f;
        bool pulsed = metro.process(44100.0f, 0.5, l, r);
        assert(!pulsed || (std::abs(l) < 1.0e-6 && std::abs(r) < 1.0e-6));
    }

    {
        mozart::Metronome metro;
        metro.setEnabled(false);
        metro.setSound(mozart::MetronomeSound::Click);
        metro.setVolume(1.0f);

        float l = 0.0f, r = 0.0f;
        bool pulsed = metro.process(44100.0f, 0.5, l, r);
        assert(!pulsed);
        assert(std::abs(l) < 1.0e-6);
        assert(std::abs(r) < 1.0e-6);
    }

    {
        mozart::Metronome metro;
        metro.setSound(mozart::MetronomeSound::None);
        metro.setEnabled(true);
        metro.setVolume(1.0f);

        float l = 0.0f, r = 0.0f;
        bool pulsed = metro.process(44100.0f, 0.5, l, r);
        assert(!pulsed);
        assert(std::abs(l) < 1.0e-6);
        assert(std::abs(r) < 1.0e-6);
    }

    {
        mozart::Metronome metro;
        metro.setEnabled(true);
        metro.setBpm(60.0f);
        metro.setSound(mozart::MetronomeSound::Click);
        metro.setVolume(1.0f);

        float l = 0.0f, r = 0.0f;
        bool pulsed = metro.process(44100.0f, 0.5, l, r);
        assert(!pulsed);
        pulsed = metro.process(44100.0f, 0.5, l, r);
        assert(pulsed);
    }

    {
        mozart::Metronome metro;
        metro.setEnabled(true);
        metro.setSound(mozart::MetronomeSound::Click);
        metro.setVolume(1.0f);
        metro.setTimeSignature(4, 4);

        float l1 = 0.0f, r1 = 0.0f;
        metro.process(44100.0f, 0.5, l1, r1);
        float accentLevel = std::abs(l1);

        float l2 = 0.0f, r2 = 0.0f;
        metro.process(44100.0f, 0.5, l2, r2);
        float noAccentLevel = std::abs(l2);

        assert(accentLevel > noAccentLevel * 1.2f);
    }

    {
        mozart::Metronome metro;
        metro.setEnabled(true);
        metro.setSound(mozart::MetronomeSound::Click);
        metro.setVolume(1.0f);

        float l = 0.0f, r = 0.0f;
        metro.process(44100.0f, 0.5, l, r);
        metro.reset();
        l = 0.0f; r = 0.0f;
        bool pulsed = metro.process(44100.0f, 0.1, l, r);
        assert(!pulsed);
    }

    // --- MidiEvent tests ---

    {
        mozart::MidiEvent event;
        event.id = 1;
        event.trackId = 10;
        event.patternId = 20;
        event.tick = 480;
        event.note = 60;
        event.velocity = 100;
        event.durationTicks = 240;
        event.probability = 80;
        event.ratchet = 2;
        event.nudgeTicks = 5;

        assert(event.id == 1);
        assert(event.trackId == 10);
        assert(event.patternId == 20);
        assert(event.tick == 480);
        assert(event.note == 60);
        assert(event.velocity == 100);
        assert(event.durationTicks == 240);
        assert(event.probability == 80);
        assert(event.ratchet == 2);
        assert(event.nudgeTicks == 5);
        assert(event.isValid());
    }

    {
        mozart::MidiEvent event;
        event.note = 128; // invalid
        assert(!event.isValid());

        event.note = 60;
        event.velocity = 128; // invalid
        assert(!event.isValid());

        event.velocity = 100;
        event.probability = 101; // invalid
        assert(!event.isValid());
    }

    // --- Pattern tests ---

    {
        mozart::Pattern pattern(1, 10, "Pattern 1");

        assert(pattern.id() == 1);
        assert(pattern.trackId() == 10);
        assert(pattern.name() == "Pattern 1");
        assert(pattern.events().empty());

        mozart::MidiEvent event;
        event.tick = 0;
        event.note = 60;
        event.velocity = 100;
        std::uint32_t eventId = pattern.addEvent(event);
        assert(eventId == 1);
        assert(pattern.events().size() == 1);
        assert(pattern.findEvent(eventId) != nullptr);
        assert(pattern.findEvent(eventId)->note == 60);
        assert(pattern.findEvent(999) == nullptr);
    }

    {
        mozart::Pattern pattern(2, 20, "Pattern 2");

        mozart::MidiEvent e1;
        e1.tick = 0;
        e1.note = 60;
        e1.velocity = 100;
        std::uint32_t id1 = pattern.addEvent(e1);

        mozart::MidiEvent e2;
        e2.tick = 120;
        e2.note = 64;
        e2.velocity = 80;
        std::uint32_t id2 = pattern.addEvent(e2);

        assert(pattern.events().size() == 2);

        // Edit note
        assert(pattern.setEventNote(id1, 67));
        assert(pattern.findEvent(id1)->note == 67);

        // Edit velocity
        assert(pattern.setEventVelocity(id2, 110));
        assert(pattern.findEvent(id2)->velocity == 110);

        // Edit tick
        assert(pattern.setEventTick(id1, 240));
        assert(pattern.findEvent(id1)->tick == 240);

        // Edit duration
        assert(pattern.setEventDuration(id2, 480));
        assert(pattern.findEvent(id2)->durationTicks == 480);

        // Edit probability
        assert(pattern.setEventProbability(id1, 50));
        assert(pattern.findEvent(id1)->probability == 50);

        // Edit ratchet
        assert(pattern.setEventRatchet(id2, 3));
        assert(pattern.findEvent(id2)->ratchet == 3);

        // Edit nudge
        assert(pattern.setEventNudge(id1, -10));
        assert(pattern.findEvent(id1)->nudgeTicks == -10);

        // Invalid edits
        assert(!pattern.setEventNote(999, 60)); // non-existent event
        assert(!pattern.setEventNote(id1, 128)); // invalid note
        assert(!pattern.setEventVelocity(id1, 128)); // invalid velocity
        assert(!pattern.setEventProbability(id1, 101)); // invalid probability

        // Remove event
        assert(pattern.removeEvent(id1));
        assert(pattern.findEvent(id1) == nullptr);
        assert(pattern.events().size() == 1);

        assert(!pattern.removeEvent(999)); // non-existent
    }

    // --- Project tests ---

    {
        mozart::Project project;

        // Add tracks
        std::uint32_t trackId1 = project.addTrack("Track 1");
        std::uint32_t trackId2 = project.addTrack("Track 2");
        assert(trackId1 == 1);
        assert(trackId2 == 2);
        assert(project.trackCount() == 2);
        assert(project.track(trackId1) != nullptr);
        assert(project.track(trackId1)->name() == "Track 1");

        // Add patterns to tracks
        std::uint32_t patternId1 = project.addPattern(trackId1, "Pattern A");
        std::uint32_t patternId2 = project.addPattern(trackId1, "Pattern B");
        std::uint32_t patternId3 = project.addPattern(trackId2, "Pattern C");
        assert(patternId1 == 1);
        assert(patternId2 == 2);
        assert(patternId3 == 3);

        // Patterns for track
        auto patterns1 = project.patternsForTrack(trackId1);
        assert(patterns1.size() == 2);
        auto patterns2 = project.patternsForTrack(trackId2);
        assert(patterns2.size() == 1);

        // Invalid pattern (non-existent track)
        std::uint32_t badPatternId = project.addPattern(999, "Bad");
        assert(badPatternId == 0);

        // Find event across tracks/patterns
        mozart::MidiEvent event;
        event.tick = 0;
        event.note = 60;
        event.velocity = 100;
        project.pattern(patternId1)->addEvent(event);
        std::uint32_t eventId = project.pattern(patternId1)->events()[0].id;

        mozart::MidiEvent* found = project.findEvent(trackId1, patternId1, eventId);
        assert(found != nullptr);
        assert(found->note == 60);

        // Wrong track should not find event
        assert(project.findEvent(trackId2, patternId1, eventId) == nullptr);

        // Wrong pattern should not find event
        assert(project.findEvent(trackId1, patternId2, eventId) == nullptr);

        // Remove track cascades to patterns
        project.removeTrack(trackId1);
        assert(project.trackCount() == 1);
        assert(project.track(trackId1) == nullptr);
        assert(project.patternsForTrack(trackId1).empty());
        assert(project.findEvent(trackId1, patternId1, eventId) == nullptr);
    }

    return 0;
}
