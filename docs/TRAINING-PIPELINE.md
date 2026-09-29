# Mozart Local MIDI Training Pipeline

## Purpose

This document defines the reproducible path from an audited MIDI source to a Mozart production-model training corpus.

The production generator is a compact 30–60M parameter causal symbolic-MIDI Transformer. The dataset pipeline must produce the frozen Mozart 512-token event vocabulary and explicit conditioning data without weakening the runtime validator.

## Pipeline

```text
audited MIDI sources
        |
        v
source manifest + checksums
        |
        v
MIDI parse / structural sanity checks
        |
        v
normalization (fixed revision)
        |
        v
musical filtering
        |
        v
deterministic grouping / split
        |
        v
Mozart tokenizer (512 tokens)
        |
        v
conditioning record generation
        |
        v
training shards + statistics
        |
        v
model training
        |
        v
held-out evaluation
        |
        v
export + quantization
        |
        v
model manifest + checksum
```

## Provenance gate

Every external source must be represented in `docs/dataset-manifest.example.json` and pass the project's commercial-use policy before production data can be used.

A production/audited manifest requires:

- immutable source revision;
- source-level license identifier;
- commercial-use permission;
- redistribution permission;
- attribution requirement;
- rights evidence;
- file-level SHA-256 checksums;
- acquisition date;
- explicit train/validation/test split locations.

A source marked `requires-review` or `prohibited` is never silently promoted to production data.

## MIDI normalization

Normalization is versioned. The current planned revision is `mozart-midi-normalization-v1`.

Required deterministic rules:

- normalize timing to a fixed internal PPQ, currently 480;
- preserve supported tempo and time-signature information as metadata;
- preserve MIDI channels 0–15;
- keep percussion on channel 9;
- reject structurally corrupt MIDI rather than repairing it invisibly;
- never clamp invalid notes/velocities into valid ranges without recording a rejection reason;
- quantize event timing to the 1/16-beat Mozart grid;
- encode velocity using the frozen 32-bin vocabulary;
- encode duration independently from time-shift;
- encode controller numbers 0–127 and controller values using 32 bins;
- canonicalize duplicate events deterministically;
- cap normalized examples at 4096 note events and 1024 controller events before tokenization.

The normalizer must emit a rejection report with stable reason codes. Rejected material is never silently counted as usable training data.

## Example construction

The first production training target is 4–16 bar material.

Examples should be built from musical boundaries rather than arbitrary MIDI-file byte offsets. A song/piece must remain in a single split to prevent near-duplicate windows from crossing train and evaluation sets.

The pipeline should preserve enough context for the model to learn:

- rhythmic structure;
- pitch relationships;
- bar-level repetition;
- phrase continuity;
- role-specific behavior.

Examples may be derived as continuation pairs later, but the underlying source identity remains part of split bookkeeping.

The current training-example tool emits the split-bookkeeping fields directly on every
record:

- `source_id`;
- `source_revision`;
- `source_path`.

The source identity fields are required inputs, not guessed from the filename, so an
immutable musical-source revision must be supplied explicitly by the offline pipeline.

## Deterministic splitting

Splits must be deterministic and source-grouped.

Do not randomly split individual windows from the same source across train/validation/test.

The assignment key is a stable hash of:

`source_id + source_revision`

The file/window path is not part of the group key because multiple files or windows may belong to the same musical source. Fixed bucket ranges assign the group to train/validation/test.

The current default is 90% train, 5% validation and 5% test. Repeated pipeline runs with the same seed and manifest therefore produce the same source-group assignments while avoiding source leakage.

The shard builder applies a second validation gate: a `source_id + source_revision`
group is rejected when records carrying that group appear in more than one split.
Records are sorted deterministically before writing bounded JSONL shards.

## Training shard output

The current offline tooling writes one or more bounded JSONL shards per split plus
`dataset-statistics.json`. The statistics currently cover record counts, split counts,
token-count totals/min/max/mean, bar-length totals/min/max/mean, and style/role
conditioning counts. They also record the manifest checksum when supplied and the
split/token vocabulary revisions.

This is the first corpus-packaging layer, not the final dataset evidence package:
source/license distributions, rejection-reason statistics, and canonical duplicate
detection remain required before a production dataset is approved.

Each training example now carries bounded musical quality metadata: note/controller
counts, maximum simultaneous note-on count per quantized start step, a 128-bin pitch
histogram, and a 32-bin velocity histogram. The shard builder validates these fields
and aggregates them into the corpus statistics file. These statistics are evidence
for dataset QA only; they do not replace the provenance/license gate.

## Conditioning records

Each training example should carry model-independent conditioning fields from the Mozart vocabulary:

- style;
- substyle;
- mood;
- rhythm;
- role;
- key/scale;
- chord progression when available;
- density;
- energy;
- syncopation;
- swing;
- variation;
- seed.

Conditioning values must use the slugs and enums already defined in `StyleVocabulary.h` / `GenerationRequest.h`.

The mapping from these fields into model tensors remains model-dependent and is frozen only with the actual checkpoint/export.

## Quality filters

At minimum, training examples should be filtered for:

- invalid/corrupt MIDI structure;
- unsupported or contradictory metadata;
- zero usable musical events;
- extreme event density beyond the runtime budget;
- pathological pitch ranges;
- impossible or negative durations;
- excessive duplicate events;
- unusable timing resolution;
- source duplicates detected by canonical content hash.

Filtering must produce counts per reason so dataset size changes are explainable.

## Dataset statistics

Every training build should record:

- number of source files discovered;
- number accepted/rejected;
- rejection reasons;
- bars generated;
- examples per split;
- token count distribution;
- note-event count distribution;
- polyphony distribution;
- pitch histogram;
- velocity-bin histogram;
- role/style distribution;
- source/license distribution;
- normalization revision;
- pipeline version;
- manifest checksum.

The statistics file is part of the training run evidence.

## Reproducibility

A training run must be reproducible from:

- dataset manifest;
- normalization revision;
- pipeline commit;
- source checksums;
- deterministic split seed/algorithm;
- tokenizer vocabulary revision;
- conditioning vocabulary revision;
- model configuration;
- training seed.

Changing any one of these creates a new training revision.

## Separation from realtime Mozart

The entire dataset/training pipeline is offline development infrastructure.

It must not be compiled into the production Android realtime path and must not affect:

- Ableton Link;
- scheduler timing;
- MIDI callbacks;
- audio callbacks.

The shipped application consumes only the resulting production model artifact and its manifest.

## Next implementation gates

1. Implement MIDI file discovery and structural validation.
2. Implement deterministic normalization to the Mozart event grid.
3. Implement source-grouped deterministic train/validation/test splitting.
4. Emit tokenized training shards using `MidiEventTokenizer`.
5. Emit conditioning records from audited metadata.
6. Add dataset statistics and rejection reports.
7. Run a small end-to-end fixture corpus before using any external data.
8. Freeze the first production dataset manifest only after rights evidence is complete.
