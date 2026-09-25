# MIDI Contract

## Purpose

Keep all platform MIDI implementation details below one narrow boundary.

## Native representation

A transport-neutral MIDI 1.0 short message is:

```
struct MidiShortMessage {
    uint8_t status;
    uint8_t data1;
    uint8_t data2;
    uint8_t size;
    uint64_t timestampNanos;
    uint32_t portId;
};
```

Validation rules:

- status must be 0x80..0xEF for channel voice messages;
- data bytes must be 0..127;
- size must match the status class;
- timestamp uses monotonic host time;
- portId is assigned by the transport layer.

System realtime and SysEx are separate message classes.

## Android mapping

The Android adapter owns:

- MidiManager;
- MidiDevice;
- MidiInputPort;
- MidiOutputPort;
- MidiReceiver;
- AMidi.

Android documentation states that incoming data may contain multiple messages or partial messages and realtime messages can be interleaved. The parser therefore cannot assume one callback equals one complete MIDI message.

## Output policy

Prefer Android MIDI timestamps for scheduled sends when the selected transport supports them.

Never let the domain send byte arrays directly.

## MIDI 2.0 readiness

Keep an independent abstraction so a future UMP transport can coexist with MIDI 1.0.

Do not force the current instrument to use UMP until a real device/use case requires it.
