# MIDI Layer

This directory will contain the transport abstraction and Android MIDI adapter.

Ownership:

- Android MidiManager/device/port details stay in the platform adapter.
- The native boundary receives transport-neutral MIDI events.
- Musical interpretation belongs above this layer.

First implementation target: deterministic Android MIDI device discovery and endpoint selection.
