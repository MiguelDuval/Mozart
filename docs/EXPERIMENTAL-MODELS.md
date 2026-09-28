# Mozart Experimental Model Lab

## Purpose

Mozart has a permanent Experimental Model Lab alongside the commercial production path.

The lab exists so development can use external or otherwise non-redistributable model checkpoints without making those checkpoints part of the Mozart commercial artifact.

This is an architectural boundary, not a temporary debug feature.

## Two model classes

### Commercial

Commercial models are eligible for inclusion in a distributed Mozart release only after the project has verified:

- model implementation license;
- model-weight license;
- training-data provenance;
- redistribution rights;
- preprocessing/provenance records;
- exact model checksum;
- model/runtime compatibility.

A commercial model uses the normal production packaging path.

### Private experimental

Private experimental models may be used by the developer for local testing when their terms permit that use, even when they are not eligible for redistribution.

Private experimental artifacts must:

- remain outside the Git repository;
- remain outside the distributed APK/AAB;
- be loaded from developer/user-controlled storage;
- never become a transitive packaged dependency;
- be identified in the model catalog as PrivateExperimental;
- pass the same token detokenization and PatternProposalValidator gates as production models.

The experimental classification does not override a model's license. A model may only be used in ways permitted by its actual terms.

## Universal adapter architecture

The model runtime is abstracted behind TokenInferenceBackend.

The model catalog maps a stable modelId to:

- a human-readable name;
- a backend ID;
- an external artifact path;
- an optional manifest path;
- a distribution class.

The intended flow is:

~~~text
Experimental Model Lab UI
        |
        v
   selected modelId
        |
        v
     ModelCatalog
        |
        v
 TokenInferenceBackend
   |      |       |
 LiteRT  ONNX   other runtime
        |
        v
 MidiEventToken stream
        |
        v
 MidiEventDetokenizer
        |
        v
 PatternProposalValidator
        |
        v
 existing musical/scheduler path
~~~

A backend is deliberately unaware of Ableton Link, the scheduler, MIDI hardware and the UI.

## Model selection UX

The production UI should expose an Experimental Models entry only in development/experimental builds.

Inside that entry:

1. show the available catalog entries;
2. clearly label private experimental models;
3. show model availability and manifest/compatibility state;
4. allow selecting one model for generation;
5. provide a reload/unload action so large models can be evicted without restarting Mozart;
6. return to deterministic generation without requiring an experimental model.

The first implementation may use a simple selector rather than a complex model manager. The architectural requirement is the separation, not the visual design.

## Realtime isolation

The Experimental Model Lab is never on the realtime path.

Generation and model loading run on worker threads.

No model backend may be called from:

- Ableton Link callbacks;
- scheduler send loops;
- MIDI receive callbacks;
- realtime audio callbacks.

A slow, unavailable or broken experimental model must not stop transport.

## Artifact boundary

Recommended local layout:

~~~text
app-private/
  experimental-models/
    <model-id>/
      model artifact
      model manifest
~~~

The exact Android storage mechanism can change, but the release build must not package the experimental directory.

The repository may contain:

- adapter interfaces;
- catalog schema;
- validation code;
- tests;
- documentation;
- scripts that help developers install models.

The repository must not contain restricted experimental model weights.

## Compatibility

Every experimental backend eventually has to produce Mozart's frozen MidiEventToken vocabulary.

A backend may use any internal tokenization or runtime format, but its adapter must translate into the Mozart contract before the proposal reaches the musical engine.

Therefore:

~~~text
external model format
        !=
Mozart runtime token ABI
~~~

The adapter is the translation boundary.

A candidate model that cannot reliably translate into Mozart's vocabulary and validation contract is a research experiment, not a Mozart generation backend.

## Commercial release gate

The commercial build must not depend on the Experimental Model Lab for:

- application startup;
- core generation;
- MIDI output;
- Link synchronization;
- scheduler operation.

A commercial model is promoted from experimental status only after the model manifest and licensing/provenance audit are complete.

Promotion means changing the model classification and packaging path deliberately; it is never an automatic side effect of selecting a model in the lab.

## Current implementation

The repository currently provides:

- TokenInferenceBackend as the universal runtime adapter boundary;
- ModelCatalog for model-to-backend selection;
- ModelDistributionClass::PrivateExperimental;
- runtime-neutral token and conditioning contracts;
- strict detokenization and proposal validation;
- a production model manifest template.

The Android debug-only Experimental Model Lab selector is now present. It discovers descriptors from app-private experimental-models storage and sends the selected model descriptor through JNI into the native ModelCatalog selection state.

Concrete external-runtime adapters and native generation execution are the next implementation layers.

## Related documents

- docs/AI-GENERATION.md
- docs/MODEL-ABI.md
- docs/MODEL-MANIFEST.md
- docs/MODEL-SELECTION.md
- docs/LITERT.md
