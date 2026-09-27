# MIDI transport

The transport layer separates platform MIDI plumbing from the musical domain.

## Output

`MidiOutputTransport` carries validated MIDI 1.0 short messages toward the destination device. The Android path uses `MidiManager` to discover the destination INPUT port and AMidi for timestamped writes.

## Input

`MidiInputParser` accepts arbitrary MIDI byte fragments and reconstructs MIDI 1.0 channel-voice short messages. It deliberately does not treat an Android `MidiReceiver.onSend()` callback as a message boundary.

The parser handles:

- multiple messages in one callback;
- one message split across callbacks;
- MIDI running status;
- interleaved system-realtime bytes;
- SysEx/system-common data being ignored by the channel-voice queue.

Parsed messages enter `MidiReceiveQueue`, a bounded queue shared by transport adapters and future musical-domain consumers. The queue drops the oldest event when full so stale input cannot accumulate indefinitely.

The Android ingress adapter is `AndroidMidiInput`. It opens an explicitly selected device OUTPUT port and connects a `MidiReceiver`; source selection is intentionally separate from the MicroFreak MIDI OUT auto-selection.

The input queue is intentionally independent of key/scale detection. Future consumers may use it for:

- MIDI-driven key/scale hints;
- controller mappings;
- performance gestures;
- diagnostics.

No input event is allowed to alter Link timing or bypass the existing scheduler.
