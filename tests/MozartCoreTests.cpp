#include "core/MidiEndpoint.h"
#include "core/MidiTypes.h"
#include "core/TransportMath.h"
#include "generation/ArpeggioGenerator.h"
#include "generation/BassGenerator.h"
#include "generation/RhythmGenerator.h"
#include "midi/MidiTransport.h"
#include "musical/KeyScale.h"
#ifdef MOZART_ENABLE_LINK
#include "runtime/MozartRuntime.h"
#endif
#ifdef MOZART_ENABLE_LINK
#include "clock/LinkClock.h"
#endif

#include <cassert>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <condition_variable>
#include <mutex>
#include <thread>
#include <vector>

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
        assert(std::abs(mozart::timing::nextQuantizedBeat(3.2, 4.0) - 4.0) < 1.0e-12);
        assert(std::abs(mozart::timing::nextQuantizedBeat(4.0, 4.0) - 8.0) < 1.0e-12);
        assert(std::abs(mozart::timing::nextQuantizedBeat(7.999, 4.0) - 8.0) < 1.0e-12);
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

    {
        const mozart::musical::KeyScale fSharpMinor(
                6, mozart::musical::Scale::NaturalMinor);

        assert(fSharpMinor.isValid());
        assert(fSharpMinor.containsMidiNote(42));
        assert(fSharpMinor.containsMidiNote(45));
        assert(fSharpMinor.containsMidiNote(49));
        assert(!fSharpMinor.containsMidiNote(43));

        const auto a =
                mozart::generation::BassGenerator::generateBar(
                        fSharpMinor, 2, 1234);
        const auto b =
                mozart::generation::BassGenerator::generateBar(
                        fSharpMinor, 2, 1234);

        assert(a == b);
        assert(a.size() == 8);

        const auto arpA =
                mozart::generation::ArpeggioGenerator::generateBar(
                        fSharpMinor, 4, 1234);
        const auto arpB =
                mozart::generation::ArpeggioGenerator::generateBar(
                        fSharpMinor, 4, 1234);

        assert(arpA == arpB);
        assert(arpA.size() == 8);

        const auto sparseBass =
                mozart::generation::BassGenerator::generateBar(
                        fSharpMinor,
                        2,
                        1234,
                        0,
                        mozart::generation::PatternDensity::Sparse);
        const auto normalBass =
                mozart::generation::BassGenerator::generateBar(
                        fSharpMinor,
                        2,
                        1234,
                        0,
                        mozart::generation::PatternDensity::Normal);
        const auto sparseAgain =
                mozart::generation::BassGenerator::generateBar(
                        fSharpMinor,
                        2,
                        1234,
                        0,
                        mozart::generation::PatternDensity::Sparse);

        assert(sparseBass == sparseAgain);
        assert(!sparseBass.empty());
        assert(sparseBass.size() <= normalBass.size());
        assert(normalBass.size() <= a.size());

        const auto sparseArp =
                mozart::generation::ArpeggioGenerator::generateBar(
                        fSharpMinor,
                        4,
                        1234,
                        0,
                        mozart::generation::PatternDensity::Sparse);
        assert(!sparseArp.empty());
        assert(sparseArp.size() <= arpA.size());

        for (const auto& event : arpA) {
            assert(event.startBeat >= 0.0);
            assert(event.startBeat < 4.0);
            assert(event.durationBeats > 0.0);
            assert(event.note >= 60);
            assert(event.note < 96);
            assert(fSharpMinor.containsMidiNote(event.note));
            assert(event.velocity >= 76);
            assert(event.velocity <= 115);
            assert(event.channel == 0);
        }

        for (const auto& event : a) {
            assert(event.startBeat >= 0.0);
            assert(event.startBeat < 4.0);
            assert(event.durationBeats > 0.0);
            assert(event.note >= 36);
            assert(event.note < 60);
            assert(fSharpMinor.containsMidiNote(event.note));
            assert(event.velocity >= 88);
            assert(event.velocity <= 119);
            assert(event.channel == 0);
        }
    }

    {
        using mozart::midi::MidiEndpointDescriptor;
        using mozart::midi::MidiEndpointSelector;
        using mozart::midi::PortDirection;
        using mozart::midi::TransportKind;

        const std::vector<MidiEndpointDescriptor> candidates{
            MidiEndpointDescriptor{
                10, 0, PortDirection::Output, TransportKind::Usb,
                "Arturia MicroFreak output", "Arturia", "MicroFreak"
            },
            MidiEndpointDescriptor{
                11, 0, PortDirection::Input, TransportKind::Usb,
                "Generic USB MIDI", "Other", "Controller"
            },
            MidiEndpointDescriptor{
                12, 1, PortDirection::Input, TransportKind::Bluetooth,
                "Arturia MicroFreak", "Arturia", "MicroFreak"
            },
            MidiEndpointDescriptor{
                14, 2, PortDirection::Input, TransportKind::Usb,
                "Arturia MicroFreak", "Arturia", "MicroFreak"
            },
            MidiEndpointDescriptor{
                13, 1, PortDirection::Input, TransportKind::Usb,
                "Arturia MicroFreak", "Arturia", "MicroFreak"
            }
        };

        const auto selection =
                MidiEndpointSelector::selectPreferredOutput(
                        candidates, "Arturia", "MicroFreak");

        assert(selection.selected());
        assert(*selection.candidateIndex == 3);
        assert(candidates[*selection.candidateIndex].deviceId == 14);
        assert(candidates[*selection.candidateIndex].portNumber == 2);
        assert(candidates[*selection.candidateIndex].canReceiveFromMozart());

        const std::vector<MidiEndpointDescriptor> unrelated{
            MidiEndpointDescriptor{
                21, 0, PortDirection::Input, TransportKind::Usb,
                "Generic USB MIDI", "Other", "Controller"
            },
            MidiEndpointDescriptor{
                22, 0, PortDirection::Input, TransportKind::Usb,
                "Arturia KeyLab", "Arturia", "KeyLab"
            }
        };

        const auto noMatch =
                MidiEndpointSelector::selectPreferredOutput(
                        unrelated, "Arturia", "MicroFreak");
        assert(!noMatch.selected());
    }

    {
        class MockMidiOutput final : public mozart::midi::MidiOutputTransport {
        public:
            mozart::midi::MidiSendResult send(
                    const mozart::midi::MidiShortMessage& message) noexcept override {
                last = message;
                ++sendCount;
                return {
                    mozart::midi::MidiTransportStatus::Ok,
                    message.size
                };
            }

            void close() noexcept override {}

            mozart::midi::MidiShortMessage last{};
            std::size_t sendCount = 0;
        };

        MockMidiOutput output;
        const auto message =
                mozart::midi::noteOn(0, 64, 111, 987654321ULL, 42);

        assert(message.has_value());
        const auto result = output.send(*message);
        assert(result.ok());
        assert(result.bytesSent == 3);
        assert(output.sendCount == 1);
        assert(output.last.status == 0x90);
        assert(output.last.data1 == 64);
        assert(output.last.data2 == 111);
        assert(output.last.timestampNanos == 987654321ULL);
        assert(output.last.portId == 42);
    }

#ifdef MOZART_ENABLE_LINK
    {
        class RecordingMidiOutput final : public mozart::midi::MidiOutputTransport {
        public:
            mozart::midi::MidiSendResult send(
                    const mozart::midi::MidiShortMessage& message) noexcept override {
                {
                    std::lock_guard<std::mutex> lock(mutex);
                    messages.push_back(message);
                }
                condition.notify_all();
                return {
                    mozart::midi::MidiTransportStatus::Ok,
                    message.size
                };
            }

            void close() noexcept override {}

            bool waitForCount(const std::size_t expected) {
                std::unique_lock<std::mutex> lock(mutex);
                return condition.wait_for(
                        lock,
                        std::chrono::milliseconds(500),
                        [&] { return messages.size() >= expected; });
            }

            std::size_t count() const {
                std::lock_guard<std::mutex> lock(mutex);
                return messages.size();
            }

            mozart::midi::MidiShortMessage messageAt(const std::size_t index) const {
                std::lock_guard<std::mutex> lock(mutex);
                return messages.at(index);
            }

            std::vector<mozart::midi::MidiShortMessage> messagesCopy() const {
                std::lock_guard<std::mutex> lock(mutex);
                return messages;
            }

        private:
            mutable std::mutex mutex;
            std::condition_variable condition;
            std::vector<mozart::midi::MidiShortMessage> messages;
        };

        RecordingMidiOutput output;
        mozart::runtime::MozartRuntime runtime(output);
        runtime.start();

        // This mirrors the Android STOP path: accompaniment is stopped first,
        // then Link is disabled. Only one MIDI panic pair must be emitted.
        runtime.setAccompanimentEnabled(false);
        assert(output.waitForCount(2));
        assert(output.count() == 2);

        const auto allNotesOff = output.messageAt(0);
        const auto allSoundOff = output.messageAt(1);
        assert(allNotesOff.status == 0xB0);
        assert(allNotesOff.data1 == 123);
        assert(allNotesOff.data2 == 0);
        assert(allSoundOff.status == 0xB0);
        assert(allSoundOff.data1 == 120);
        assert(allSoundOff.data2 == 0);

        runtime.setLinkEnabled(false);
        assert(output.count() == 2);
    }

    {
        class CountingMidiOutput final : public mozart::midi::MidiOutputTransport {
        public:
            mozart::midi::MidiSendResult send(
                    const mozart::midi::MidiShortMessage& message) noexcept override {
                {
                    std::lock_guard<std::mutex> lock(mutex);
                    messages.push_back(message);
                }
                last = message;
                ++sendCount;
                condition.notify_all();
                return {
                    mozart::midi::MidiTransportStatus::Ok,
                    message.size
                };
            }

            void close() noexcept override {}

            std::vector<mozart::midi::MidiShortMessage> messagesCopy() const {
                std::lock_guard<std::mutex> lock(mutex);
                return messages;
            }

            mozart::midi::MidiShortMessage last{};
            std::atomic<std::size_t> sendCount{0};

        private:
            mutable std::mutex mutex;
            std::condition_variable condition;
            std::vector<mozart::midi::MidiShortMessage> messages;
        };

        CountingMidiOutput output;
        mozart::clock::LinkClock clock(120.0, 4.0);
        mozart::scheduler::MidiSendQueue queue(output);
        mozart::scheduler::AccompanimentScheduler scheduler(clock, queue);

        assert(
                scheduler.role() ==
                mozart::scheduler::AccompanimentRole::Bass);
        scheduler.setRole(
                mozart::scheduler::AccompanimentRole::Arpeggio);
        assert(
                scheduler.role() ==
                mozart::scheduler::AccompanimentRole::Arpeggio);
        scheduler.setRole(
                mozart::scheduler::AccompanimentRole::Bass);
        assert(
                scheduler.role() ==
                mozart::scheduler::AccompanimentRole::Bass);
        assert(
                scheduler.density() ==
                mozart::generation::PatternDensity::Full);
        scheduler.setDensity(
                mozart::generation::PatternDensity::Sparse);
        assert(
                scheduler.density() ==
                mozart::generation::PatternDensity::Sparse);
        scheduler.setDensity(
                mozart::generation::PatternDensity::Full);
        assert(
                scheduler.density() ==
                mozart::generation::PatternDensity::Full);

        clock.setEnabled(true);
        const auto beforeArm = clock.captureAppSnapshot();
        const auto expectedLaunchBeat =
                mozart::timing::nextQuantizedBeat(
                        beforeArm.beat,
                        beforeArm.quantum);
        const auto expectedLaunchHostTime =
                clock.hostTimeAtBeat(expectedLaunchBeat);

        queue.start();
        scheduler.start();
        scheduler.setArmed(true);

        bool generated = false;
        for (int attempt = 0; attempt < 800; ++attempt) {
            if (output.sendCount.load() > 0) {
                generated = true;
                break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }

        scheduler.setArmed(false);
        scheduler.stop();
        queue.stop();

        assert(generated);
        assert(output.last.size == 3);

        const auto messages = output.messagesCopy();
        assert(!messages.empty());
        for (const auto& message : messages) {
            assert(message.timestampNanos >=
                    static_cast<std::uint64_t>(
                            expectedLaunchHostTime.count()) * 1000ULL);
        }

        std::vector<std::uint64_t> noteOnTimestamps;
        for (const auto& message : messages) {
            if ((message.status & 0xF0) == 0x90 && message.data2 > 0) {
                noteOnTimestamps.push_back(message.timestampNanos);
            }
        }

        // The rolling scheduler should expose consecutive eighth-note bass
        // events instead of scheduling one whole bar and waiting for the next
        // bar boundary. At 120 BPM, the generated pattern is 250 ms apart.
        assert(noteOnTimestamps.size() >= 5);
        for (std::size_t i = 1; i < 5; ++i) {
            const auto deltaNanos =
                    noteOnTimestamps[i] - noteOnTimestamps[i - 1];
            assert(deltaNanos >= 120'000'000ULL);
            assert(deltaNanos <= 380'000'000ULL);
        }
    }

    {
        mozart::clock::LinkClock clock(120.0, 4.0);
        assert(!clock.isEnabled());
        assert(!clock.isStartStopSyncEnabled());

        const auto snapshot = clock.captureAppSnapshot();
        assert(!snapshot.enabled);
        assert(!snapshot.playing);
        assert(!snapshot.inSession);
        assert(!snapshot.startStopSyncEnabled);
        assert(snapshot.peers == 0);
        assert(std::abs(snapshot.tempoBpm - 120.0) < 1.0e-9);
        assert(std::abs(snapshot.quantum - 4.0) < 1.0e-12);
        assert(snapshot.phase >= 0.0);
        assert(snapshot.phase < snapshot.quantum);

        const auto targetBeat = 8.5;
        const auto targetTime = clock.hostTimeAtBeat(targetBeat);
        const auto roundTripBeat = clock.beatAtHostTime(targetTime);
        assert(std::abs(roundTripBeat - targetBeat) < 1.0e-9);

        clock.setEnabled(true);
        assert(clock.isEnabled());
        assert(!clock.isStartStopSyncEnabled());

        const auto enabledSnapshot = clock.captureAppSnapshot();
        assert(enabledSnapshot.enabled);
        assert(!enabledSnapshot.startStopSyncEnabled);
        assert(enabledSnapshot.peers == 0);
        assert(!enabledSnapshot.inSession);
        assert(std::abs(enabledSnapshot.tempoBpm - 120.0) < 1.0e-9);
        assert(std::abs(enabledSnapshot.quantum - 4.0) < 1.0e-12);
        assert(enabledSnapshot.phase >= 0.0);
        assert(enabledSnapshot.phase < enabledSnapshot.quantum);

        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        const auto advancedSnapshot = clock.captureAppSnapshot();
        assert(advancedSnapshot.enabled);
        assert(advancedSnapshot.beat > enabledSnapshot.beat + 0.05);
        assert(advancedSnapshot.phase >= 0.0);
        assert(advancedSnapshot.phase < advancedSnapshot.quantum);

        clock.setEnabled(false);
        assert(!clock.isEnabled());
        const auto disabledAgain = clock.captureAppSnapshot();
        assert(!disabledAgain.enabled);
        assert(!disabledAgain.startStopSyncEnabled);
    }
#endif

    return 0;
}
