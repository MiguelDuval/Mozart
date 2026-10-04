# Dataset Rights-Chain Audit Protocol

## Purpose

A public dataset license is only one part of a production rights audit. Mozart must separately establish:

1. who controlled the underlying material;
2. who had authority to grant rights to WaivOps/Patchbanks;
3. what rights were actually granted;
4. whether those rights cover commercial ML training and redistribution; and
5. whether the grant covers the exact files that enter the training corpus.

A publisher's own statement is useful evidence, but it is not automatically equivalent to documentary proof of the underlying chain of title.

## Evidence strength

Use these labels when recording authority evidence:

- `public_record` — a stable dataset/repository record establishing identity, revision, archive, or published metadata.
- `publisher_assertion` — a rights/provenance statement made by the dataset publisher or manager.
- `independent_document` — a contract, contributor grant, provider license, or other documentary evidence not relying only on the publisher's public description.
- `file_mapping` — an authoritative mapping from source rights records to the exact distributed file set.

Approval requires the authority-critical facts to be supported by evidence stronger than a publisher assertion alone, plus exact file coverage.

## NRG-CP result

For Zenodo `15304989` / version `1.0`, the public evidence establishes that Patchbanks and WaivOps are the named creators/project entities, that the dataset is distributed under CC BY 4.0, and that Patchbanks publicly states commercial use, redistribution-style sharing/remixing, and generative-AI pretraining/fine-tuning are intended uses. Sources: [Patchbanks FAQ](https://www.patchbanks.com/faq/), [WaivOps page](https://www.patchbanks.com/waivops/), [Zenodo record](https://zenodo.org/records/15304989).

The unresolved part is the underlying authority chain. The NRG-CP README says the corpus is generated from a symbolic chord-progression database plus custom rhythm-generation code, while the same README says the recordings were sourced from verified composers and providers for copyright clearance. No public contributor/provider roster, rights-grant document, or per-file rights manifest was found in the sources reviewed. Sources: [WaivOps NRG-CP GitHub repository](https://github.com/patchbanks/WaivOps-NRG-CP), [Zenodo record](https://zenodo.org/records/15304989).

Therefore the production decision remains **pending**, not because the public commercial/AI-use statements are absent, but because the evidence does not yet establish file-level authority for the exact 30,943-file corpus.

## Approval rule

Do not move NRG-CP into the production training manifest until the authority-chain JSON is upgraded from `pending` to `approved`, with documentary evidence and exact file coverage. The downloaded archive checksum and canonical inventory hash are necessary integrity gates, but they do not substitute for the authority chain.
