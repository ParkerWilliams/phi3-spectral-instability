# Data Model: SP-0 — Multi-Model Geometry Extraction Substrate

**Date**: 2026-06-17 | **Feature**: `002-sp0-extraction-substrate`

Entities the substrate produces/consumes. Field types are conceptual (precision per
Constitution IV: float64 at the seam, downcast at the cache boundary). Relationships and
validation rules are derived from the spec's functional requirements.

## DocQAEventRecord (the common cross-corpus input)

The single record shape every corpus adapter emits (extends v1 `dataset/types.py:DocQAEvent`).

| Field | Type | Notes |
|---|---|---|
| `event_id` | str (SHA256) | `SHA256(prompt_template_sha ‖ document ‖ question ‖ gold)` (Constitution I) |
| `corpus_id` | enum | `hotpotqa \| squad2 \| triviaqa_nq \| ruler \| nolima` |
| `document` | str | **empty for closed-book**; long for RULER |
| `question` | str | |
| `gold_aliases` | list[str] | ≥1; the alias set for EM max-over-references |
| `is_answerable` | bool | False only for SQuAD2-unanswerable (and any unanswerable RULER variant) |
| `evidence_spans` | list[(start_tok, end_tok)] \| null | gold-evidence token ranges; null when corpus gives none (closed-book) |
| `provenance` | dict | source split, sampling seed, generator params (RULER), corpus version |

**Validation**: `gold_aliases` non-empty unless `is_answerable=False`; `evidence_spans`
token indices within the tokenized prompt; closed-book ⇒ `document==""` and
`evidence_spans is null`.

## ModelDescriptor (per-model metadata + capture profile)

| Field | Type | Notes |
|---|---|---|
| `model_id` | str | HF id |
| `revision_sha` | str | pinned HF revision (Constitution I) |
| `d_model, n_layers, n_heads, n_kv_heads, head_dim` | int | **read from config**, never computed (R1.2) |
| `n_rep` | int | `n_heads // n_kv_heads` |
| `tokenizer_id, transformers_version` | str | pinned ≥4.48 (R1.6) |
| `attention_profile` | list[per-layer] | `full` vs `sliding(window)`; softcap params (Gemma-2, R1.3) |
| `tied_embeddings` | bool | capture `lm_head.weight` directly regardless |

**Validation**: `attention_profile` length == `n_layers`; sliding/softcap fields present
for Gemma-2.

## GenerationSample (one of the K+1 decodes)

| Field | Type | Notes |
|---|---|---|
| `text` | str | decoded |
| `token_ids` | list[int] | for exact retokenization |
| `token_logprobs` | list[float] | **chosen-token** logprob per step (R3.1) |
| `seq_logprob` | float | Σ token_logprobs |
| `length` | int | token count (for offline length-normalization) |
| `is_greedy` | bool | the one T=0 sample is the **scored** answer |
| `seed` | int | per-sample RNG seed (reproducibility) |

**Validation**: exactly one `is_greedy=True`; K others sampled (T=1.0, top-p 0.9).

## Label (4-way + headline binary)

| Field | Type | Notes |
|---|---|---|
| `class_4way` | enum | `correct-answer \| wrong-answer \| correct-abstention \| hallucination` |
| `is_hallucination` | bool | headline positive = {wrong-answer, hallucination} |
| `em_match` | bool | normalized EM vs gold_aliases (greedy sample) |
| `token_f1` | float | SQuAD-style robustness cross-check |
| `abstained` | bool | abstention detector output |
| `abstention_evidence` | enum | `rule \| classifier \| judge` |

**State table** (R3.2): `(is_answerable, em_match, abstained) → class_4way`. Answerable
+abstained ⇒ wrong-answer. Unanswerable+abstained ⇒ correct-abstention;
unanswerable+¬abstained ⇒ hallucination.

## CaptureBundle (the per-`(model, corpus, event)` stored unit)

The raw material; every field traces to a metric in `contracts/capture-manifest.md`.

| Field | Type / shape | Precision | Feeds |
|---|---|---|---|
| `hidden_answer_pos` | `(L+1, d_model)` | fp16 | trajectory, logit-lens, probe |
| `hidden_window` | `(2W+1, L+1, d_model)` | fp16 | per-token dynamics, local-ID |
| `attn_rows_answer_pos` | `(L, n_heads, T)` | fp16 | attention-to-evidence, routing entropy |
| `attn_full_subset` | `(|S|, n_heads, T, T)` | fp16 | rollout, Ollivier-Ricci, Laplacian |
| `token_cloud_spectra` | `(L, k_eig)` + MP-fit stats | fp64→fp32 | all RMT (in-pass; raw cloud not stored) |
| `interhead_drift_surface` | `(n_t, L, K_summary)` `S(t,ℓ)` | fp64→fp32 | §5.6 inter-head attention-drift (in-pass; raw H×T not stored) |
| `samples` | K+1 × GenerationSample | — | semantic entropy, baselines |
| `answer_logits` | `(vocab,)` or top-k | fp16 | confidence baselines |
| `evidence_spans` | from DocQAEventRecord | — | attention-to-evidence |
| `label` | Label | — | supervised target |
| `model_descriptor_ref` | ModelDescriptor id | — | cross-model harness |

**Validation**: `attn_full_subset` layer set `S` and window `W` from the benchmark gate;
`token_cloud_spectra` computed in float64 in-pass (Constitution IV) then stored; no raw
token cloud persisted.

## CaptureManifest

The authoritative metric→raw-tensor mapping (contracts/capture-manifest.md) + a
`capture_version` string. The **completeness check** asserts every program-catalog metric
maps to a CaptureBundle field before any full run (SC-001).

## CacheHeader (sidecar per file)

`{capture_version, manifest_sha256, code_commit_sha, model_id, revision_sha, corpus_id,
created_at, host}` — extends the v1 `storage/cache.py` header. `read_*` raises on
`capture_version`/`manifest_sha256` mismatch (no silent fallback).

## BenchmarkReport / PilotReport

- **BenchmarkReport**: per `(model, context_bucket)` → `{sec_per_event, peak_mem_gb,
  disk_mb_per_event}`; derived `{chosen_N, layer_subset_S, longctx_N}`.
- **PilotReport**: per corpus → `{fail_rate, hallucination_rate, abstention_P, abstention_R}`;
  `{oom_skips:0, resume_restored_pct:100, archs_validated:[…]}`.

## HarnessDataset (the SP-1..SP-3 loader view)

A read-only projection over CaptureBundles: `(features := assembler(bundle), target :=
label.is_hallucination | label.class_4way, group := {corpus_id, model_id})`. The feature
assembler is **pluggable and arbitrary-width** (no hard-coded feature count).

## Entity relationships

```
ModelDescriptor 1──* CaptureBundle *──1 DocQAEventRecord
CaptureBundle 1──* GenerationSample
CaptureBundle 1──1 Label
CaptureManifest 1──* (validates) CaptureBundle.fields
CaptureBundle 1──1 CacheHeader
HarnessDataset = view over CaptureBundle (× assembler)
```
