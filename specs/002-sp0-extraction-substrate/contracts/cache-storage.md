# Contract: Cache Storage, Versioning & Durability

**Feature**: `002-sp0-extraction-substrate` | Extends v1 `src/phi3geom/storage/cache.py`

## Layout

```
cache/<capture_version>/<model_id>/<corpus_id>/<event_id_prefix>/<event_id>/
    hidden_answer_pos.npy        + .header.json
    hidden_window.npy            + .header.json
    attn_rows_answer_pos.npy     + .header.json
    attn_full_subset.npy         + .header.json    # layers in S only
    token_cloud_spectra.npy      + .header.json
    samples.json                 # K+1 GenerationSample
    answer_logits.npy            + .header.json
    label.json                   # Label
    event.json                   # DocQAEventRecord + provenance
models/<model_id>/                # per-model "once" artifacts
    lm_head_weight.npy  norm.json  model_descriptor.json
```

## Header schema (sidecar per tensor)

`{capture_version, manifest_sha256, code_commit_sha, model_id, revision_sha, corpus_id,
dtype, shape, created_at, host}`. Extends the v1 header (which already carries
`manifest_sha256`). `read_*` raises `CacheStaleError` on `capture_version` **or**
`manifest_sha256` mismatch — **no silent fallback** (Constitution I).

## Versioning

- `capture_version` (e.g. `"2.0.0"`) is **distinct from** v1's `feature_layout`/
  `SCHEMA_VERSION`, so v1 and v2 caches never collide and a reader can tell which schema a
  bundle was written under (program §11).
- Adding a roster model or corpus increments nothing and **touches no existing bundle**
  (SC-006): new `(model, corpus)` subtrees are written alongside.

## Durability (the v1 data-loss defect class)

- Captured bundles MUST be **durably persisted and never silently dropped by
  storage-ignore rules** — the v1 `.gitignore` bug that dropped `cache/`/`reports/`
  (fixed in `fe190b7` via anchored ignores + force-add). The regression test that
  reproduces the old drop MUST stay green (FR-018, SC-007).
- **Resilient resume** reads what was *actually persisted* (not what was scheduled): an
  interrupted run restores 100% of committed events and recomputes none (FR-019, SC-007).
  The v1 `restore_from_branch` read an uncommitted path → 0 restored; the v2 resume MUST
  read the committed cache.

## Precision (Constitution IV)

Float64 only at the spectral seam (the in-pass `token_cloud_spectra` computation). All
stored tensors downcast at this cache boundary (fp16 for activations/attention, fp32 for
spectra). The seam never accepts float32 input; the cache never stores float64 activations.

## Storage medium

First-allocation cache (tens of GB at the 6-checkpoint cut) on local SSD + the durable
git-branch store (v1 pattern). **Risk** (program §10, spec Assumptions): full-program
scale (full `T×T`, 10 models, long context) may exceed what the branch store should hold;
the contract is medium-agnostic (durable + resumable + SHA-stamped), and migrating to
external object storage at scale does not change this contract.
