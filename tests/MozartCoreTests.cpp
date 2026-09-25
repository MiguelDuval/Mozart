#include "core/MidiEndpoint.h"
#include "core/MidiTypes.h"
#include "core/TransportMath.h"
#include "generation/RhythmGenerator.h"
#include "midi/MidiTransport.h"
#ifdef MOZART_ENABLE_LINK
#include "clock/LinkClock.h"
#endif

#include <cassert>
#include <cmath>
#include <cstdint>
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
    }
#endif

    return 0;
}
