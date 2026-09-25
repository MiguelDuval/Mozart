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
The Android setup sequence is:

**MidiManager discovery → MidiDevice open → selected device INPUT port → AMidiDevice → AMidiInputPort**

The selected input port belongs to the destination MIDI device. For Mozart's primary USB-MicroFreak path, automatic selection is restricted to USB endpoints whose product/name matches MicroFreak.

Prefer Android/AMidi timestamps for scheduled sends when the selected transport supports them.

The transport-neutral boundary accepts `MidiShortMessage`; platform adapters own byte packing, platform handles and port lifecycle.

`AMidiInputPort_sendWithTimestamp()` may block during the actual write. It is therefore not an audio-callback API and must not be called directly from the realtime scheduler/audio callback. A dedicated MIDI transport/send context owns the blocking write path.

No successful AMidi open or physical MIDI delivery is claimed without Android/physical test evidence.

## MIDI 2.0 readiness

Keep an independent abstraction so a future UMP transport can coexist with MIDI 1.0.

Do not force the current instrument to use UMP until a real device/use case requires it.
