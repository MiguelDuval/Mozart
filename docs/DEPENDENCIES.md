# Mozart Dependencies

Pinned baseline as of 2026-09-28.

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
| LiteRT C++ SDK | 2.2.0 | release `v2.2.0`; SHA-256 `0aa619d80aef27303ad9c6e3759a20110f77e7b11ade9b68061b8c6e5904b0c6` | on-device local AI inference | preparation |
| ONNX Runtime Android | 1.30.0 | official Maven Central AAR | Experimental Model Lab ONNX inspection | debug-only |

## Why these versions

JUCE 9.0.2 is the pinned 9.x baseline used by the project.

Oboe 1.10.2 is the pinned Android low-latency audio baseline.

Ableton Link 4.0 is the pinned shared musical clock baseline.

Tracktion Engine 3.2.0 is staged and is not required by the realtime MIDI vertical slice.

LiteRT 2.2.0 is the first pinned local-AI runtime target. The official release publishes a C++ SDK asset, and the repository now verifies that asset by SHA-256 before extraction. The exact runtime packaging is intentionally deferred until the Mozart model tensor contract is frozen.

See `docs/LITERT.md` for the reproducible SDK boundary and integration gates. ONNX Runtime 1.30.0 is intentionally debug-only for Experimental Model Lab inspection; it is not part of the commercial release dependency set.

## Licensing notes

Licenses matter even for a personal project, and especially if distribution changes later.

- Android/NDK/CMake components follow their respective licenses.
- Oboe is Apache-2.0.
- JUCE 9 is dual licensed under AGPL-3.0-only or commercial terms.
- Tracktion Engine is GPL/commercial licensed.
- Ableton Link is dual licensed under GPLv2+ or proprietary terms.

Before any public redistribution, run a dependency/license audit and decide whether the GPL/AGPL/commercial obligations fit the intended distribution model.

LiteRT and the production model require separate checks for source-code/runtime licensing, model-weight licensing, and training-data provenance. An open-source runtime does not automatically make model weights or training data redistributable.

## Dependency policy

Never depend on a moving branch.

Every source dependency must be:

- pinned to an immutable commit or release artifact;
- named in this document;
- upgraded in a dedicated change;
- rebuilt and tested before adoption.

## Local AI dependency policy

LiteRT is the planned Android inference runtime for the local Mozart music model.

The repository does **not** vendor the SDK or production model into Git. The SDK is fetched reproducibly with `tools/fetch_litert.sh`, and the extracted directory is ignored.

The model artifact is not treated as a normal source dependency. Its checksum, training revision, dataset provenance and license/attribution manifest must be recorded separately before release.

The project will not add third-party pretrained music-model weights to the production APK merely because their source repository is open. Code license, weight license and training-data provenance are evaluated separately.
