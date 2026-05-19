# Contract: Dataset Manifest

**Scope**: JSONL line-schema for `dataset/manifest.jsonl` and JSON schema for
`dataset/manifest_header.json`. Implemented in `src/phi3geom/dataset/manifest.py`.

---

## File layout

```
dataset/
├── manifest_header.json     # Study-wide pins (SHAs, k_grass, k_attn, …)
├── manifest.jsonl           # One line per DocQAEvent (scannable index)
└── events.jsonl             # One line per DocQAEvent with full text fields
```

The split between `manifest.jsonl` (index) and `events.jsonl` (text) lets reviewers grep the
manifest by hash, bin, or label without loading multi-MB document strings into memory.

---

## `manifest_header.json` schema

```jsonc
{
  "schema_version": "1.0.0",
  "manifest_sha256": "<64 hex chars>",        // Self-SHA over manifest.jsonl bytes
  "events_sha256": "<64 hex chars>",          // SHA over events.jsonl bytes
  "code_commit_sha": "<40 hex chars>",        // git rev-parse HEAD at manifest write
  "model_revision_sha": "<40 hex chars>",     // HuggingFace revision for Phi-3-mini-128k
  "prompt_template_sha256": "<64 hex chars>", // SHA of prompt template string
  "generation_config_sha256": "<64 hex chars>",
  "k_grass": 8,
  "k_attn": <int from pilot>,
  "lookback_window_length": 256,
  "feature_layout": [
    "stable_rank_qkt",
    "grassmannian_qkt",
    "spectral_entropy_qkt",
    "stable_rank_avwo",
    "grassmannian_avwo",
    "spectral_entropy_avwo",
    "forman_ricci_attention_graph"
  ],
  "forman_ricci_convention": "nan_with_median_imputation_and_indicator",
  "adversariality_policy_per_bin": {
    "B1": "lexical|sibling_entity|self_contradiction|none",
    "B2": "lexical|sibling_entity|self_contradiction|none",
    "B3": "none",
    "B4": "none",
    "B5": "none",
    "B6": "none"
  },
  "split_seed": <int from SHA1("split:v1")>,
  "matching_seed_per_bin": {
    "B1": <int>, "B2": <int>, "B3": <int>, "B4": <int>, "B5": <int>, "B6": <int>
  },
  "constitution_version": "1.0.0",
  "spec_version": "001",
  "write_timestamp_utc": "2026-MM-DDTHH:MM:SSZ"
}
```

**Validation**:
- All SHA fields MUST be exactly 64 hex (SHA256) or 40 hex (SHA1/git) as indicated.
- `k_grass` MUST equal 8 for v1.
- `lookback_window_length` MUST equal 256 for v1.
- `feature_layout` MUST equal the canonical 7-element list verbatim.
- `manifest_sha256` MUST be the SHA256 of `manifest.jsonl` AFTER all events are written; it is
  the LAST field finalized (header is written second-to-last; the file finally renames into
  place atomically).
- `adversariality_policy_per_bin` MUST have all 6 bin keys; the chosen policy MUST be one of
  the 4 enumerated values from research.md §11.

---

## `manifest.jsonl` line schema (one line per `DocQAEvent`)

```jsonc
{
  "event_id": "<64 hex>",                     // SHA256(prompt_template_sha ‖ doc ‖ q ‖ gold)
  "bin_id": "B1|B2|B3|B4|B5|B6",
  "cem_stratum_id": "<template_id>|<density_coarsen>|<length_coarsen>",
  "question_template_id": "<id>",
  "distractor_density": 0.0,                  // float in [0, 1]
  "distractor_density_coarsening": "low|med|high",
  "gold_answer_length_tokens": 0,             // int
  "gold_answer_length_coarsening": "1|2-3|4+",
  "evidence_position_token_idx": 0,
  "evidence_distance_tokens": 0,
  "adversariality_policy": "lexical|sibling_entity|self_contradiction|none",
  "model_generation_normalized": "<string>",
  "gold_answer_normalized": "<string>",
  "is_fail": true,                            // bool
  "per_event_seed": 0                         // int = first 8 hex chars of SHA1("event:" + event_id)
}
```

**Validation**:
- `event_id` MUST be derivable from the full text fields stored in `events.jsonl`. Re-computing
  the SHA256 from `events.jsonl` MUST produce a bit-identical `event_id`.
- `evidence_distance_tokens` MUST fall within the half-open interval of `bin_id`.
- `is_fail` MUST equal the strict string-equality result of comparing
  `model_generation_normalized` and `gold_answer_normalized` after the FR-002 normalization
  pipeline.
- `cem_stratum_id` MUST be constructable as `f"{question_template_id}|{distractor_density_coarsening}|{gold_answer_length_coarsening}"`.

---

## `events.jsonl` line schema (full text fields)

```jsonc
{
  "event_id": "<64 hex>",                     // Matches manifest.jsonl
  "document": "<full document text>",
  "question": "<question text>",
  "gold_answer": "<canonical gold>",
  "model_generation_raw": "<text up to first stop token>"
}
```

**Validation**:
- `event_id` MUST equal `SHA256(prompt_template_sha ‖ document.encode('utf-8') ‖
  question.encode('utf-8') ‖ gold_answer.encode('utf-8'))`. Tested in
  `tests/unit/test_manifest.py`.
- `model_generation_raw` is the model's output BEFORE the FR-002 normalization. The normalized
  form is stored in `manifest.jsonl`.

---

## I/O API

```python
# src/phi3geom/dataset/manifest.py

def write_manifest(
    events: list[DocQAEvent],
    header: ManifestHeader,
    out_dir: pathlib.Path,
) -> None:
    """Write events.jsonl, manifest.jsonl, manifest_header.json atomically.

    Order of operations:
      1. Compute events.jsonl bytes; write to tmpfile; rename to events.jsonl.
      2. Compute events_sha256.
      3. Compute manifest.jsonl bytes; write to tmpfile; rename to manifest.jsonl.
      4. Compute manifest_sha256.
      5. Update header with both SHAs; write header.json.
    """

def read_manifest(in_dir: pathlib.Path) -> tuple[ManifestHeader, list[DocQAEvent]]:
    """Reverse of write_manifest. Verifies SHAs match before returning.

    Raises ManifestIntegrityError if any SHA mismatch is detected.
    """

def verify_event_id(event: DocQAEvent, prompt_template_sha: str) -> bool:
    """Recompute event_id from text fields and compare.

    Used in CI and at run startup to catch a corrupted events.jsonl.
    """
```

**Test obligations** (TDD scope, Constitution Principle II):
- `tests/unit/test_manifest.py::test_event_id_reproducible` — write, read, verify_event_id
  succeed.
- `tests/unit/test_manifest.py::test_sha_integrity_failure` — flip a byte in `manifest.jsonl`
  and verify `read_manifest` raises `ManifestIntegrityError`.
- `tests/unit/test_manifest.py::test_round_trip` — `read_manifest(write_manifest(e))` returns
  bit-identical events.
- `tests/unit/test_manifest.py::test_header_required_fields` — missing any required header
  field raises `ManifestSchemaError`.
