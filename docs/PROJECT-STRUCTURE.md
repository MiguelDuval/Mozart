# Mozart Project Structure

```
Mozart/
├── android/
│   └── app/
│       └── src/main/
│           ├── java/                  Android lifecycle/platform
│           ├── res/                   Android resources
│           └── AndroidManifest.xml
├── cmake/
│   └── Dependencies.cmake             immutable dependency pins
├── docs/
│   ├── PROJECT_MASTER_PROMPT.md       canonical project contract
│   ├── ARCHITECTURE.md                layer boundaries
│   ├── ROADMAP.md                     implementation stages
│   ├── TESTING.md                     test strategy
│   ├── DEPENDENCIES.md                version/licensing record
│   ├── MIDI-CONTRACT.md               transport contract
│   ├── LINK-TIMING.md                 shared clock contract
│   ├── AI-GENERATION.md               non-realtime AI boundary
│   ├── SECURITY.md                    secret/network policy
│   └── ADR-0001-foundation.md         architecture decision
├── src/
│   ├── core/                          transport-neutral primitives
│   ├── generation/                    deterministic generators
│   ├── midi/                          future platform MIDI adapter
│   ├── scheduler/                     future timestamp scheduler
│   ├── audio/                         future Oboe/JUCE audio layer
│   └── platform/android/              JNI/platform bridge
├── tests/                              host-native tests
├── tools/                              developer scripts
├── CMakeLists.txt
└── .github/workflows/android-build.yml
```

## Dependency direction

Android can depend on native/platform adapters.

Platform adapters can depend on transport-neutral core APIs.

Core/domain/generator code must not depend on Android.

Scheduler depends on semantic MIDI events and clock interfaces, not Android classes.

Optional AI depends on generated request/response schemas, never on realtime scheduling internals.

Audio is a separate subsystem.
