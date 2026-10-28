# External Dataset Candidates for Broad Electronic-Music Coverage

**Research date:** 2026-10-21  
**Status:** Public-source screening only; no downloads performed  
**Goal:** Close the verified gap in broad electronic-subgenre labels and full-length / role-diverse symbolic material without introducing unsuitable licenses or enormous local storage requirements.

## Screening result

No reviewed candidate has yet been verified to simultaneously provide (a) broad electronic subgenre labels, (b) substantial usable symbolic MIDI with meaningful instrument roles, and (c) rights suitable for a production-oriented model. Do not start training or download a large archive from this memo alone.

| Candidate | Relevant evidence | Rights / scale concern | Recommended use |
|---|---|---|---|
| **mshoxxDB — versioned electronic-music dataset** | 18 full-length pieces, 61 minutes, track-level MIDI, CSV genre/tempo/time-signature metadata, multi-track audio stems. Covers video game/chiptune, EDM, pop, house, chillout/dreamy styles. | **CC BY-NC-SA 4.0**. Only 18 compositions; cannot support broad long-run training. | Best small *research-only* candidate for validating track parsing, role/instrument metadata, section/structure inventory, and fixed-set evaluation. Do not place in a production-oriented training mix. |
| **XMIDI** | 108,023 MIDI files, labels embedded in file names for genre and emotion, reported average piece duration ~176 seconds. | The repository page reviewed does not establish a clear license/rights chain for each MIDI file. The visible sample genre tags are classical, country, folk, jazz, pop and rock; electronic subgenre coverage is not established. | Do not download/use for training until rights and target-genre coverage are verified. A large labelled count is not enough. |
| **GigaMIDI** | Very large symbolic corpus, with 89,569 MIDI files reported as having genre/artist/song labels. | **CC BY-NC 4.0** access terms, research-only; full corpus is reported around 152 GB and gated behind contact/usage conditions. Not production-eligible under these terms. | No production path. At most consider a narrowly scoped, non-commercial metadata/analysis experiment if the terms and storage budget justify it; never download the full corpus on this laptop by default. |
| **WaivOps EDM-HSE / EDM-TECH** | 8,000 house/EDM drum-loop audio files with JSON labels for styles including big room, electro, minimal and classic; another set has 11,270 techno drum-loop audio examples and substyle metadata. Both use CC BY 4.0 according to their project pages. | Audio datasets, not a ready symbolic-MIDI training corpus; published WAV archives are approximately 7.6 GB and 12.1 GB respectively. | Possible future audio-side validation or taxonomy reference. Do not treat their JSON label fields as MIDI data; no bulk WAV download until a concrete use case exists. |
| **Existing NRG-CP source** | Official dataset page describes 30,943 eight-bar MIDI chord progressions and CC BY 4.0. It is specifically chord-progression material in dance/trance/house/EDM styles. | Current local scan reported 15,235 files. It does not provide authoritative per-file electronic-subgenre labels or full arrangements. | First reconcile local file counts and split manifest; do not assume the official total means 15,708 locally usable unique files are missing. This is a source/count discrepancy, not proof of a genre solution. |

## Decision

1. **Use no new dataset for production training yet.** The current blockers are rights-cleared electronic-subgenre annotations, trustworthy train/validation/test identity, and broader symbolic instrument/arrangement roles.
2. The only strong small structural candidate found here is **mshoxxDB for research-only evaluation**, not training a production model. It can help test full-track, multi-stem parsers, but its 18 compositions are far too few for broad training and the license is non-commercial/share-alike.
3. Keep XMIDI on a rights-verification list, not a download list. A dataset's public GitHub page and research publication do not themselves establish permission to redistribute or train a commercial model on each included work.
4. Treat audio-only EDM loop sets as complementary resources, not drop-in symbolic data.
5. Before any acquisition, evaluate source-level license/provenance, exact target subgenres, asset count after deduplication, per-file train/validation/test identity, disk budget, and whether the data changes the evidence behind the model decision.

## Source links

- XMIDI project repository: https://github.com/xmusic-project/XMIDI_Dataset
- mshoxxDB repository and README: https://github.com/mic-tae/mshoxxdb
- mshoxxDB Zenodo archive: https://doi.org/10.5281/zenodo.13284494
- GigaMIDI dataset card: https://huggingface.co/datasets/Metacreation/GigaMIDI
- WaivOps EDM-HSE: https://github.com/patchbanks/WaivOps-EDM-HSE
- WaivOps EDM-TECH: https://github.com/patchbanks/WaivOps-EDM-TECH
- WaivOps NRG-CP source: https://github.com/patchbanks/WaivOps-NRG-CP
- NRG-CP Zenodo record: https://zenodo.org/records/15304989
