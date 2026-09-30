# Mozart Dataset Duplicate Review

## Purpose

`tools/dataset_quality.py` reports exact duplicate-content candidates by a stable SHA-256 derived from tokens, conditioning and musical metadata.

A duplicate candidate is not automatically rejected. Human review must decide whether the repeated material is intentional or must be excluded from the production corpus.

## Review file

Use a small JSON file outside the generated corpus:

```json
{
  "schema_version": 1,
  "reviews": {
    "<duplicate-sha256>": {
      "decision": "intentional"
    }
  }
}
```

Allowed decisions are:

- `intentional` — keep the candidate in the corpus and record that it was reviewed.
- `exclude` — the candidate is not acceptable for a strict production-quality gate and must be removed or replaced by the dataset preparation workflow before release.

The review file is evidence about the current candidate hashes. Unknown hashes are rejected so an old review cannot silently approve unrelated future corpus content.

## Strict gate

Run the QA tool with the review file and `--strict` for a release-quality check:

```bash
python3 tools/dataset_quality.py records.jsonl qa.json \
  --duplicate-review duplicate-review.json \
  --strict
```

Strict mode fails when:

- any record has validation rejection reasons;
- a source group crosses split boundaries;
- a duplicate candidate remains unreviewed;
- a duplicate has an `exclude` decision.

The report remains non-destructive: it never silently removes records.

## Reproducibility

Because duplicate hashes are derived from canonical JSON, review decisions are tied to exact corpus content. Any change to tokens, conditioning or musical metadata produces a different candidate hash and therefore requires a new review decision.

This mechanism is QA infrastructure only. It does not establish dataset ownership, licensing or commercial redistribution rights.
