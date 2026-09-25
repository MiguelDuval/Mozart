# Mozart Dependencies

Pinned baseline as of 2026-09-25.

| Dependency | Version | Source revision | Role | Current use |
|---|---|---|---|---|
| Android Gradle Plugin | 9.4.0 | official Maven | Android build | bootstrap |
| Gradle | 9.6.0 | official distribution | Android build | bootstrap |
| JDK | 17 | Temurin/OpenJDK | Android build | bootstrap |
| Android SDK | 36 | Google | target baseline | bootstrap |
| Android NDK | 28.2.13676358 | Google | native build | bootstrap |
| CMake | 3.22.1 | Kitware/Android | native build | bootstrap |
| JUCE | 9.0.2 | `72782788ce18c2d4d760b28e0921d6ffc6431102` | native framework/audio utilities | staged |
| Oboe | 1.10.2 | `faa019cb12f448d18b5ab2b933272cf0c16763b2` | Android realtime audio | staged |
| Ableton Link | 4.0 | `e9a2e414d63f55f1aad158370b007a6fbdc1eeb9` | shared musical clock | Stage 2 |
| Tracktion Engine | 3.2.0 | `0a5f4e6a5f53d09c89b414a44386a12df7fa1ec6` | higher-level sequencing/audio | staged |

## Why these versions

JUCE 9.0.2 is the current 9.x stable release observed on 2026-09-25. Its 9.0.2 release includes multiple audio/file-format and UMP fixes. [JUCE release](https://github.com/juce-framework/JUCE/releases)

Oboe 1.10.2 is the current 1.10 patch baseline used by the upstream project at the time of bootstrap. The upstream project documents Android low-latency audio, latency tuning and Android-specific workarounds. [Oboe](https://github.com/google/oboe)

Ableton Link 4.0 is the stable 4.x cross-platform Link release. Link 4.0 adds Link Audio support, but Mozart initially uses the clock/timing portion only. [Link releases](https://github.com/Ableton/link/releases)

Tracktion Engine 3.2.0 is the current tagged release observed in the repository and requires C++20; it supports Android. [Tracktion Engine](https://github.com/Tracktion/tracktion_engine)

Android Gradle Plugin 9.4.0 is the current stable line as of September 2026, and requires Gradle 9.6.0. [Android Developers](https://developer.android.com/build/releases/agp-9-4-0-release-notes)

## Licensing notes

Licenses matter even for a personal project, and especially if distribution changes later.

- Android/NDK/CMake components follow their respective licenses.
- Oboe is Apache-2.0.
- JUCE 9 is dual licensed under AGPL-3.0-only or commercial terms.
- Tracktion Engine is GPL/commercial licensed.
- Ableton Link is dual licensed under GPLv2+ or proprietary terms.

Before any public redistribution, run a dependency/license audit and decide whether the GPL/AGPL/commercial obligations fit the intended distribution model.

## Dependency policy

Never depend on a moving branch.

Every source dependency must be:

- pinned to an immutable commit;
- named in this document;
- upgraded in a dedicated change;
- rebuilt and tested before adoption.
