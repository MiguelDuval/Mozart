# Mozart Setup

## Requirements

- Android Studio compatible with AGP 9.4.
- JDK 17.
- CMake 3.22.1.
- Android SDK 36.
- Android NDK 28.2.13676358.
- Git.

## Android build

```bash
cd android
gradle --no-daemon :app:assembleDebug
```

The APK is written to:

```
android/app/build/outputs/apk/debug/app-debug.apk
```

## Native tests

```bash
bash tools/run_native_tests.sh
```

## Optional dependency checkout

The heavy third-party stack is intentionally not required for the bootstrap build.

When a feature actually needs it:

```bash
bash tools/fetch_dependencies.sh
```

This checks out immutable commits recorded in `docs/DEPENDENCIES.md`.

## First development slice

Create or continue work on `feature/midi-foundation`.

The target is Android MIDI discovery, deterministic endpoint selection and a transport-neutral native boundary.

Do not implement AI or audio rendering in this first slice.
