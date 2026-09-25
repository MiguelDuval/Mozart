#include "core/MidiEndpoint.h"
#include "core/MidiTypes.h"
#include "core/TransportMath.h"
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
        mozart::clock::LinkClock clock(120.0, 4.0);
        assert(!clock.isEnabled());
        assert(!clock.isStartStopSyncEnabled());

        const auto snapshot = clock.captureAppSnapshot();
        assert(!snapshot.enabled);
        assert(!snapshot.playing);
        assert(!snapshot.inSession);
        assert(snapshot.peers == 0);
        assert(std::abs(snapshot.tempoBpm - 120.0) < 1.0e-9);
        assert(std::abs(snapshot.quantum - 4.0) < 1.0e-12);
        assert(snapshot.phase >= 0.0);
        assert(snapshot.phase < snapshot.quantum);

        const auto targetBeat = 8.5;
        const auto targetTime = clock.hostTimeAtBeat(targetBeat);
        const auto roundTripBeat = clock.beatAtHostTime(targetTime);
        assert(std::abs(roundTripBeat - targetBeat) < 1.0e-9);
    }
#endif

    return 0;
}
