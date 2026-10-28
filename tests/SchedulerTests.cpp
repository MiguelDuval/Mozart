#include "core/GenerationTypes.h"
#include "core/MidiTypes.h"
#include "core/TransportMath.h"
#include "scheduler/AccompanimentScheduler.h"
#include "scheduler/MidiSendQueue.h"

#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>

using namespace mozart::generation;
using namespace mozart::midi;
using namespace mozart::scheduler;
using namespace mozart::timing;

void testMidiSendQueuePushPopOrdering() {
    std::cout << "Testing MidiSendQueue push/pop ordering..." << std::endl;

    MidiSendQueue queue;
    assert(queue.empty());
    assert(queue.size() == 0);

    MidiShortMessage m3{0x90, 60, 100, 3, 3000, 0};
    MidiShortMessage m1{0x90, 60, 100, 3, 1000, 0};
    MidiShortMessage m2{0x90, 60, 100, 3, 2000, 0};

    queue.push(m3);
    queue.push(m1);
    queue.push(m2);

    assert(!queue.empty());
    assert(queue.size() == 3);

    MidiShortMessage popped;
    assert(queue.tryPop(popped));
    assert(popped.timestampNanos == 1000);

    assert(queue.tryPop(popped));
    assert(popped.timestampNanos == 2000);

    assert(queue.tryPop(popped));
    assert(popped.timestampNanos == 3000);

    assert(queue.empty());
    assert(queue.size() == 0);
    assert(!queue.tryPop(popped));

    std::cout << "  MidiSendQueue push/pop ordering: PASSED" << std::endl;
}

void testMidiSendQueueClear() {
    std::cout << "Testing MidiSendQueue clear..." << std::endl;

    MidiSendQueue queue;
    queue.push(MidiShortMessage{0x90, 60, 100, 3, 100, 0});
    queue.push(MidiShortMessage{0x90, 61, 100, 3, 200, 0});
    assert(queue.size() == 2);

    queue.clear();
    assert(queue.empty());
    assert(queue.size() == 0);

    std::cout << "  MidiSendQueue clear: PASSED" << std::endl;
}

void testTickToHostTime() {
    std::cout << "Testing AccompanimentScheduler tickToHostTime..." << std::endl;

    MidiSendQueue queue;
    AccompanimentScheduler scheduler(queue);

    SchedulerConfig config;
    config.ticksPerBeat = 480;
    config.bpm = 120.0;
    config.startHostTimeNanos = 1000000000ULL;
    config.portId = 0;
    scheduler.configure(config);

    assert(scheduler.tickToHostTime(0) == 1000000000ULL);
    assert(scheduler.tickToHostTime(480) == 1500000000ULL);
    assert(scheduler.tickToHostTime(240) == 1250000000ULL);

    SchedulerConfig config2 = config;
    config2.bpm = 60.0;
    scheduler.configure(config2);

    assert(scheduler.tickToHostTime(0) == 1000000000ULL);
    assert(scheduler.tickToHostTime(480) == 2000000000ULL);

    std::cout << "  AccompanimentScheduler tickToHostTime: PASSED" << std::endl;
}

void testScheduleNoteEvent() {
    std::cout << "Testing AccompanimentScheduler note scheduling..." << std::endl;
    MidiSendQueue queue;
    AccompanimentScheduler scheduler(queue);
    SchedulerConfig config;
    config.ticksPerBeat = 480;
    config.bpm = 120.0;
    config.startHostTimeNanos = 0;
    config.portId = 7;
    scheduler.configure(config);
    PatternProposal proposal;
    proposal.providerId = "test";
    proposal.modelId = "test";
    proposal.totalTicks = 1920;
    proposal.trackCount = 1;
    NoteEvent note1{60, 100, 0, 480, 0, 0};
    proposal.events.push_back(note1);
    NoteEvent note2{64, 80, 480, 240, 0, 0};
    proposal.events.push_back(note2);
    assert(scheduler.schedule(proposal));
    assert(queue.size() == 4);
    MidiShortMessage msg;
    assert(queue.tryPop(msg));
    assert(msg.status == 0x90 && msg.data1 == 60 && msg.data2 == 100);
    assert(msg.timestampNanos == 0 && msg.portId == 7);
    assert(queue.tryPop(msg));
    assert(msg.status == 0x80 && msg.data1 == 60 && msg.data2 == 0);
    assert(msg.timestampNanos == 500000000ULL && msg.portId == 7);
    assert(queue.tryPop(msg));
    assert(msg.status == 0x90 && msg.data1 == 64 && msg.data2 == 80);
    assert(msg.timestampNanos == 500000000ULL && msg.portId == 7);
    assert(queue.tryPop(msg));
    assert(msg.status == 0x80 && msg.data1 == 64 && msg.data2 == 0);
    assert(msg.timestampNanos == 750000000ULL && msg.portId == 7);
    assert(queue.empty());
    std::cout << "  AccompanimentScheduler note scheduling: PASSED" << std::endl;
}
void testScheduleInvalidProposal() {
    std::cout << "Testing AccompanimentScheduler rejects invalid proposals..." << std::endl;
    MidiSendQueue queue;
    AccompanimentScheduler scheduler(queue);
    SchedulerConfig config;
    config.ticksPerBeat = 480;
    config.bpm = 120.0;
    config.startHostTimeNanos = 0;
    config.portId = 0;
    scheduler.configure(config);
    PatternProposal empty;
    assert(!scheduler.schedule(empty));
    PatternProposal zeroTicks;
    zeroTicks.providerId = "test";
    zeroTicks.modelId = "test";
    zeroTicks.totalTicks = 0;
    zeroTicks.trackCount = 1;
    zeroTicks.events.push_back(NoteEvent{60, 100, 0, 480, 0, 0});
    assert(!scheduler.schedule(zeroTicks));
    assert(queue.empty());
    std::cout << "  AccompanimentScheduler rejects invalid proposals: PASSED" << std::endl;
}
void testScheduleTempoEvent() {
    std::cout << "Testing AccompanimentScheduler tempo event handling..." << std::endl;
    MidiSendQueue queue;
    AccompanimentScheduler scheduler(queue);
    SchedulerConfig config;
    config.ticksPerBeat = 480;
    config.bpm = 120.0;
    config.startHostTimeNanos = 0;
    config.portId = 0;
    scheduler.configure(config);
    PatternProposal proposal;
    proposal.providerId = "test";
    proposal.modelId = "test";
    proposal.totalTicks = 1920;
    proposal.trackCount = 1;
    TempoEvent tempo{0, 100.0};
    proposal.events.push_back(tempo);
    NoteEvent note{60, 100, 480, 480, 0, 0};
    proposal.events.push_back(note);
    assert(scheduler.schedule(proposal));
    assert(queue.size() == 2);
    MidiShortMessage msg;
    assert(queue.tryPop(msg));
    assert(msg.timestampNanos == 600000000ULL);
    assert(queue.tryPop(msg));
    assert(msg.timestampNanos == 1200000000ULL);
    std::cout << "  AccompanimentScheduler tempo event handling: PASSED" << std::endl;
}
void testScheduleProgramChange() {
    std::cout << "Testing AccompanimentScheduler program change..." << std::endl;
    MidiSendQueue queue;
    AccompanimentScheduler scheduler(queue);
    SchedulerConfig config;
    config.ticksPerBeat = 480;
    config.bpm = 120.0;
    config.startHostTimeNanos = 1000000000ULL;
    config.portId = 3;
    scheduler.configure(config);
    PatternProposal proposal;
    proposal.providerId = "test";
    proposal.modelId = "test";
    proposal.totalTicks = 1920;
    proposal.trackCount = 1;
    ProgramChangeEvent pc{0, 2, 42};
    proposal.events.push_back(pc);
    assert(scheduler.schedule(proposal));
    assert(queue.size() == 1);
    MidiShortMessage msg;
    assert(queue.tryPop(msg));
    assert(msg.status == 0xC2);
    assert(msg.data1 == 42);
    assert(msg.data2 == 0);
    assert(msg.size == 2);
    assert(msg.timestampNanos == 1000000000ULL);
    assert(msg.portId == 3);
    std::cout << "  AccompanimentScheduler program change: PASSED" << std::endl;
}
void testScheduleControlChange() {
    std::cout << "Testing AccompanimentScheduler control change..." << std::endl;
    MidiSendQueue queue;
    AccompanimentScheduler scheduler(queue);
    SchedulerConfig config;
    config.ticksPerBeat = 480;
    config.bpm = 120.0;
    config.startHostTimeNanos = 0;
    config.portId = 1;
    scheduler.configure(config);
    PatternProposal proposal;
    proposal.providerId = "test";
    proposal.modelId = "test";
    proposal.totalTicks = 1920;
    proposal.trackCount = 1;
    ControlChangeEvent cc{960, 1, 64, 127};
    proposal.events.push_back(cc);
    assert(scheduler.schedule(proposal));
    assert(queue.size() == 1);
    MidiShortMessage msg;
    assert(queue.tryPop(msg));
    assert(msg.status == 0xB1);
    assert(msg.data1 == 64);
    assert(msg.data2 == 127);
    assert(msg.timestampNanos == 1000000000ULL);
    assert(msg.portId == 1);
    std::cout << "  AccompanimentScheduler control change: PASSED" << std::endl;
}
void testSetStartHostTime() {
    std::cout << "Testing AccompanimentScheduler setStartHostTime..." << std::endl;
    MidiSendQueue queue;
    AccompanimentScheduler scheduler(queue);
    SchedulerConfig config;
    config.ticksPerBeat = 480;
    config.bpm = 120.0;
    config.startHostTimeNanos = 0;
    config.portId = 0;
    scheduler.configure(config);
    assert(scheduler.tickToHostTime(480) == 500000000ULL);
    scheduler.setStartHostTime(2000000000ULL);
    assert(scheduler.tickToHostTime(480) == 2500000000ULL);
    std::cout << "  AccompanimentScheduler setStartHostTime: PASSED" << std::endl;
}
int main() {
    try {
        testMidiSendQueuePushPopOrdering();
        testMidiSendQueueClear();
        testTickToHostTime();
        testScheduleNoteEvent();
        testScheduleInvalidProposal();
        testScheduleTempoEvent();
        testScheduleProgramChange();
        testScheduleControlChange();
        testSetStartHostTime();

        std::cout << "\n=== ALL SCHEDULER TESTS PASSED ===" << std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "TEST FAILED: " << e.what() << std::endl;
        return 1;
    } catch (...) {
        std::cerr << "TEST FAILED: Unknown exception" << std::endl;
        return 1;
    }
}
