# MOZART — PROJECT MASTER PROMPT

## 1. Mission

Mozart is a personal Android **MIDI accompanist** for electronic music.

Its primary job is to listen to musical context and/or user control, generate useful rhythmic, bass, arpeggio and harmonic accompaniment, synchronize that accompaniment to an Ableton Link session, and send MIDI over USB to an external instrument.

The primary hardware target is the **Arturia MicroFreak**. Other MIDI synthesizers, grooveboxes and DAWs should be supported through the same transport-neutral MIDI architecture.

The application is intentionally not a general DAW.

The first useful instrument is:

**musical context / user control
→ accompaniment engine
→ deterministic musical pattern
→ Link-aligned scheduler
→ Android USB-MIDI
→ Arturia MicroFreak**

The product should feel immediate enough to use while performing electronic music.

The application is initially for personal use. Distribution, licensing, cloud accounts and commercial packaging are not first-order goals, but the codebase must still avoid unsafe credential handling and must preserve dependency license obligations.

## 2. Product goals

### 2.1 Primary goals

- generate useful rhythmic, bass, melodic and harmonic accompaniment material;
- respond predictably to user controls;
- synchronize to Ableton Link tempo and beat/phase;
- send MIDI with stable timing over USB to the Arturia MicroFreak and, later, other external MIDI instruments and DAWs;
- receive MIDI input when useful for triggering, transposition, chord detection and control;
- allow fast mutation of patterns without stopping the musical clock;
- remain functional with no network connection;
- make AI assistance optional rather than foundational.

### 2.2 Secondary goals

- Android low-latency audio preview/metronome;
- MIDI 1.0 first, MIDI 2.0/UMP-ready architecture;
- multiple MIDI endpoints;
- quantized launch;
- per-pattern variation, probability and ratchets;
- scales, chord vocabulary and voice-leading;
- deterministic randomization;
- project/session save;
- optional NVIDIA NIM-powered musical idea generation;
- future external controller mapping.

### 2.3 Non-goals for the first stages

Do not build a full DAW.

Do not begin with multitrack audio recording.

Do not make an LLM responsible for note-by-note realtime scheduling.

Do not couple the musical model to Android classes.

Do not couple the musical model directly to Ableton Link types.

Do not require internet access for basic playback/generation.

## 3. Technology baseline

### Android

- Android application;
- min SDK 24;
- target/compile SDK 36 for the first implementation baseline;
- Java/Kotlin platform layer may be used, but the timing-critical musical core is C++20;
- Android MIDI API / AMidi for transport;
- JNI only as a narrow boundary.

Android's MIDI API provides device enumeration, hot-plug callbacks, MIDI 1.0 transport, SysEx and timestamps; Android also exposes native MIDI access through AMidi. The architecture therefore treats Android MIDI as the platform transport rather than replacing it with a third-party MIDI stack. [Android Developers](https://developer.android.com/reference/android/media/midi/package-summary)

### Native and audio

- C++20;
- Oboe 1.10.2 for Android low-latency audio;
- JUCE 9.0.2 as the cross-platform application/audio utility layer where needed;
- Tracktion Engine 3.2.0 as the optional higher-level sequencing/audio foundation after the core MIDI instrument is stable.

Oboe 1.10.2 adds modern Android audio capabilities and bug fixes; the project should prefer Oboe's current callback APIs and avoid inventing another low-level audio abstraction prematurely. JUCE 9.0.2 is the current pinned JUCE baseline. Tracktion Engine 3.2.0 requires C++20 and supports Android. See `docs/DEPENDENCIES.md`.

### Timing

- Ableton Link 4.0;
- local monotonic host time for scheduling;
- Link beat/time conversion at scheduling boundaries;
- explicit quantum policy;
- look-ahead scheduling where required by Android MIDI transport.

Ableton Link synchronizes shared beat, tempo, phase and optional start/stop state across peers. It deliberately has no single master; peers independently participate in one musical session. Mozart therefore uses a "follow session" product policy rather than a technical master/slave assumption. [Ableton Link documentation](https://ableton.github.io/link/)

### AI

Optional provider interface for network or local AI generation.

Production direction is now fixed: Mozart's baseline local music generator is a compact 30–60M-parameter symbolic-MIDI Transformer, deployed in int8 form and executed off the realtime path. It is intended for 4–16 bar polyphonic generation with controlled genre/subgenre, mood/energy, key/scale, density, polyphony, pitch range and role conditioning.

Mozart should ship its own commercially usable model weights rather than relying on third-party pretrained checkpoints with non-commercial restrictions. Training-data provenance and redistribution permissions are part of the model release contract.

The first Android inference runtime target is LiteRT behind the provider interface; the exact pinned runtime revision is selected during implementation.

Initial supported concept: NVIDIA NIM-compatible OpenAI-style chat/completions endpoint selected by configuration.

No model name is hard-coded into the core. Model IDs, endpoint URLs and prompts live in provider configuration, because model availability changes.

NIM is allowed to produce:

- chord progressions;
- rhythmic descriptions;
- arrangement suggestions;
- mutation proposals;
- scale/key suggestions;
- textual or structured pattern requests.

NIM is not allowed to:

- block the realtime scheduler;
- run on the audio callback;
- hold the transport hostage;
- emit unsanitized MIDI directly to a hardware port;
- write credentials into source control.

## 4. Architecture

The mandatory conceptual layers are:

1. Android platform.
2. MIDI transport.
3. Clock/synchronization.
4. Musical domain.
5. Pattern/generation engine.
6. Scheduler.
7. Optional audio preview.
8. Persistence/session.
9. Presentation/UI.
10. Optional AI provider.

The principal data flow is:

**Android MIDI input
→ MidiTransport
→ semantic ControlEvent / NoteEvent
→ MusicalModel
→ PatternGenerator
→ Scheduler
→ MidiTransport output**

Timing enrichment is:

**Scheduler
↔ ClockService
↔ Ableton Link**

AI enrichment is:

**UI/request
→ AI Provider
→ validated PatternProposal
→ MusicalModel
→ deterministic local renderer
→ Scheduler**

The AI provider is therefore outside the timing loop.

## 5. Threading model

### UI thread

May handle:

- views;
- Android lifecycle;
- user requests;
- configuration;
- file/document selection;
- presentation.

Must not perform:

- long parsing;
- network generation;
- MIDI burst scheduling;
- blocking device scans on hot paths.

### MIDI transport thread/callback

May:

- receive platform MIDI messages;
- timestamp/copy into a transport queue;
- invoke lightweight transport callbacks.

It should not:

- decide harmony;
- run an LLM;
- mutate UI state directly.

### Musical worker

May:

- transform semantic commands;
- generate patterns;
- perform quantization;
- prepare scheduled MIDI events;
- manage session/persistence jobs.

This thread may allocate because it is not the realtime audio callback, but latency-sensitive operations should still be bounded.

### Realtime audio thread

When introduced:

- render audio only;
- use preallocated state;
- use lock-free or realtime-safe structures;
- no filesystem;
- no networking;
- no arbitrary heap allocation;
- no Android UI calls.

### Scheduler

The scheduler is the critical MIDI timing subsystem.

It should:

- work from a monotonic clock and Link session state;
- maintain a bounded look-ahead window;
- emit timestamped MIDI events where platform support allows it;
- avoid scheduling duplicates;
- support transport start/stop;
- quantize musical launches.

## 6. Musical timing model

Use beats as the primary musical coordinate.

The model must support:

- beat;
- bar;
- subdivision;
- tempo;
- quantum;
- phase;
- swing;
- humanize amount;
- probability;
- ratchet count;
- gate length.

Never store only wall-clock milliseconds for a musical event.

Store both:

- musical coordinate;
- resolved execution time when scheduled.

This allows the same pattern to survive tempo changes.

## 7. Ableton Link policy

Mozart initially behaves as a Link participant that follows a shared session.

Default behavior:

- start with a local tempo before joining a session;
- enabling Link must not destructively reset the local musical state;
- once connected, read the shared tempo and beat/phase;
- do not continuously propose tempo changes;
- user tempo changes may become session changes only through an explicit product policy later;
- support optional Start/Stop Sync later;
- quantify launch points according to a user-configurable quantum.

For a custom realtime callback, follow Ableton's guidance to use realtime-safe session-state capture on the realtime side and avoid main-thread state commits when they would create timing ambiguity. [Ableton Link documentation](https://ableton.github.io/link/)

## 8. MIDI architecture

MIDI 1.0 is the first protocol.

Represent transport-independent MIDI as semantic/native structures.

Minimum byte-level representation:

- status;
- data1;
- data2;
- timestamp;
- port identifier.

Support later:

- SysEx;
- MIDI Clock;
- Song Position Pointer;
- Start/Continue/Stop;
- UMP/MIDI 2.0.

The platform adapter owns Android `MidiManager`, `MidiDevice`, `MidiInputPort`, `MidiOutputPort` and AMidi details.

The domain never imports `android.media.midi.*`.

## 9. Generation architecture

The generator works from a musical request:

`GenerationRequest`

with concepts such as:

- style family;
- tempo;
- scale/key;
- chord progression;
- density;
- energy;
- syncopation;
- swing;
- seed;
- length in bars;
- instrument/voice role.

It produces:

`PatternProposal`

containing:

- note events;
- controller events when explicitly requested;
- metadata;
- confidence/diagnostic information;
- deterministic seed.

Local deterministic generators come first:

1. Euclidean rhythm;
2. seeded probability;
3. accent patterns;
4. scale/arpeggio;
5. chord voicing;
6. bassline constraints;
7. call/response;
8. variation/mutation.

AI can propose structure, but deterministic code turns it into safe musical events.

## 10. Musical safety

Every proposed note event must pass validation:

- channel range 0–15;
- note 0–127 for MIDI 1.0;
- velocity 0–127;
- valid timestamps;
- no impossible negative durations;
- bounded event count;
- bounded look-ahead horizon;
- no duplicate note-off storms unless explicitly generated.

Never let malformed external or AI data reach the MIDI output unchanged.

## 11. Persistence

The internal session model is owned by Mozart.

Initial persistence format should be versioned JSON or a compact binary equivalent only after the semantic model stabilizes.

Persist:

- tempo policy;
- Link settings;
- MIDI endpoint preferences;
- key/scale;
- patterns;
- generator seeds;
- user mappings;
- optional AI provider settings excluding secrets.

Secrets must be stored only in platform-secure storage and never serialized into project files.

## 12. UI product direction

The first UI is functional and deliberately small:

- transport state;
- BPM;
- Link enabled/connected state;
- MIDI input/output selection;
- pattern selection;
- generation controls;
- pattern variation/mutation;
- activity/diagnostic panel.

The primary layout is landscape.

Do not spend early effort on visual imitation of any commercial groovebox.

The UI should expose musical concepts, not raw MIDI bytes.

## 13. Testing strategy

Testing layers:

### Unit

- MIDI codec;
- event validation;
- quantization;
- phase/beat math;
- Euclidean patterns;
- scales;
- chord voicing;
- probability;
- deterministic seeds.

### Integration

- Android MIDI enumeration;
- virtual MIDI path where available;
- JNI boundary;
- Link session clock;
- scheduler;
- pattern-to-MIDI rendering.

### Emulator

Use GitHub Actions Android emulator for:

- app startup;
- landscape orientation;
- UI state transitions;
- MIDI-independent scheduler tests;
- deterministic generator scenarios;
- persistence round trips.

The emulator cannot prove USB hardware behavior or physical MIDI latency.

### Physical

For real hardware, test:

- device discovery;
- endpoint selection;
- MIDI input;
- MIDI output;
- jitter;
- note-on/off;
- controller behavior;
- reconnect after sleep/disconnect.

Record APK commit and Android version.

## 14. CI policy

Every meaningful branch runs:

1. native unit tests;
2. Android debug build;
3. emulator smoke/integration tests when applicable;
4. direct APK artifact using `actions/upload-artifact@v7` with `archive: false`.

A failing emulator infrastructure step must be distinguished from an application failure.

## 15. Performance gates

Do not optimize by guesswork.

Track:

- average scheduler lead time;
- late event count;
- MIDI send queue depth;
- dropped events;
- UI frame performance;
- audio callback CPU when enabled;
- Link session update latency.

Future performance acceptance targets will be defined from real-device measurements.

## 16. Security

- no secrets in git;
- no API key in APK resources;
- no network call from realtime threads;
- validate all AI/provider responses;
- cap response sizes;
- cap generated event counts;
- explicit user opt-in for network features;
- clear offline behavior.

## 17. Dependency policy

All important external dependencies must be pinned by immutable commit.

Do not track moving `main`/develop branches in the build.

Do not silently upgrade major versions.

Record:

- source repository;
- exact commit;
- reason;
- license;
- whether it is compiled/linked in the current stage.

See `docs/DEPENDENCIES.md`.

## 18. Development stages

### Execution order

The main implementation sequence is:

**Foundation → MIDI transport → Link clock → deterministic accompanist → harmony → basic performance → local AI music generation → persistence → hardening.**

Audio preview is intentionally not a prerequisite for local AI. It can be developed independently once the audio layer is ready.

Before the Local AI stage is allowed to alter the product, the following gates must be true:

- Link/scheduler timing is stable.
- Deterministic accompaniment works through the full MIDI path.
- Key/scale and basic harmonic context are stable enough to be passed into generation requests.
- There is a usable pattern/performance workflow that can consume generated patterns.
- The AI path remains completely outside realtime timing and can be disabled without affecting transport.


### Stage 0 — repository foundation

- Android shell;
- C++20 core;
- CI;
- unit testing;
- dependency policy;
- architecture documentation.

### Stage 1 — MIDI transport

- Android MIDI discovery;
- endpoint selection;
- receive/send;
- semantic event boundary;
- virtual test path.

### Stage 2 — musical clock

- Ableton Link integration;
- tempo/beat/phase;
- follower policy;
- quantized scheduler.

### Stage 3 — first accompanist

- deterministic rhythm/accompaniment generator;
- MIDI output to MicroFreak;
- start/stop;
- repeat;
- pattern variations;
- humanize;
- basic bass and arpeggio roles.

### Stage 4 — harmonic intelligence

- scales;
- chord recognition from MIDI input;
- chord progression generation;
- bass generation;
- arpeggio generation;
- voice leading;
- accompaniment role orchestration.

### Stage 5 — performance workflow

- pads/controls;
- scene/pattern switching;
- quantized launch;
- probability/ratchets;
- mappings.

### Stage 6 — audio preview

- Oboe;
- metronome;
- optional preview synth/sample engine;
- latency diagnostics.

### Stage 7 — AI assistance

- provider abstraction;
- NVIDIA NIM provider;
- structured generation;
- validation;
- offline fallback.

### Stage 8 — persistence and polish

- sessions;
- presets;
- mappings;
- import/export;
- performance diagnostics;
- robust recovery.

## 19. First acceptance milestone

The first meaningful acceptance is not "the app opens".

For the primary hardware scenario, it is:

**user controls or supplies musical context
→ Mozart generates accompaniment
→ accompaniment is quantized against Ableton Link
→ scheduler emits USB-MIDI
→ Arturia MicroFreak receives the notes in time
→ no network is required
→ the result is repeatable from the same seed**

Only after this is stable should the project become feature-heavy.

## 20. Agent behavior

Prefer the smallest complete slice.

Before writing code, determine:

- which layer owns the behavior;
- how it will be tested;
- how failure will be diagnosed;
- what existing stable behavior must not change.

After code:

- build;
- test;
- inspect CI;
- document evidence;
- then continue.

The purpose of Mozart is not to accumulate code.

The purpose is to create a reliable musical instrument.
