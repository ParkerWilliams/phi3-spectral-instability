# Design: SP-0 — multi-model extraction substrate, labeling, storage, harness

**Date**: 2026-06-17
**Status**: Approved (brainstorming) — ready for `/speckit-specify`
**Parent**: `docs/superpowers/specs/2026-06-17-v2-correctness-geometry-program-design.md`
**Branch**: `001-phi3-attention-geometry-v1`

SP-0 is the critical-path foundation of the v2 program. It is the only GPU-heavy
sub-project that everything else depends on, so its job is to **capture the raw
material once, correctly, for the full program** — even though the first allocation
only *runs* a subset of the roster. Get the schema right and SP-1/SP-2 become free
CPU sweeps and later allocations add data with no re-extraction; get it wrong and
we re-pay the GPU.

## 1. Scope

**In scope (SP-0):**
- Model-agnostic forward-pass capture across the roster.
- The **capture manifest** (metric → raw material) — the primary deliverable.
- Storage schema keyed by `(model, corpus, event)` + per-model metadata.
- 4-way labeling + abstention detector + alias/EM/F1.
- Corpus adapters: HotpotQA, SQuAD2±, closed-book TriviaQA/NQ, long-context.
- The shared **evaluation-harness interfaces** SP-1..SP-3 consume (not the metrics
  themselves).
- The **per-event H200 benchmark** (gate) + a small **multi-model pilot**.

**Out of scope (later sub-projects):** the baseline metrics (SP-1), the geometry
metrics (SP-2), and all interventions (SP-3). SP-0 ships the substrate and the
hooks they need, nothing more.

## 2. The capture manifest (primary deliverable)

Every downstream metric must trace to a stored tensor here. `[raw]` = stored as
captured; `[in-pass]` = reduced on-GPU because the raw form is too big.

| Captured | Form | Size/event (order) | Feeds (metric §) |
|---|---|---|---|
| Hidden states @ answer position, all layers | `[raw]` `(L+1, d)` fp16 | ~0.2 MB | trajectory 5.1, logit-lens 5.1, linear probe 5.0 |
| Hidden states @ a short token window (±W) | `[raw]` `(2W+1, L+1, d)` fp16 | ~few MB | per-token dynamics 5.5, local-ID 5.1 |
| Unembedding `W_U` + final norm | `[raw]` once per model | — | offline logit-lens (no per-event logits needed) |
| Answer-position attention rows, per `(layer, head)` | `[raw]` `(L, H, T)` fp16 | ~MBs | attention-to-evidence 5.2, routing entropy 5.2 |
| Full `T×T` attention, **layer subset S** (all layers when budget allows) | `[raw]`/`[in-pass]` | tune via benchmark | rollout 5.2, Ollivier-Ricci 5.4, Laplacian 5.4 |
| Per-layer token-cloud **eigen-spectrum + MP-fit stats** | `[in-pass]` `(L, k)` | small | all RMT 5.3 |
| Gold-evidence token spans | `[raw]` index ranges | tiny | attention-to-evidence 5.2 |
| K sampled answers + token logprobs | `[raw]` | small | semantic entropy 5.0 |
| Answer-token logits / final logit vector | `[raw]` | small | confidence baselines 5.0 |
| Per-model metadata (`d_model`, `n_layers`, `n_heads`, `d_head`, tokenizer, revision) | `[raw]` | tiny | cross-model harness 6 |

**Completeness rule:** before the first big run, walk the §5 catalog of the parent
doc and confirm every metric maps to a row above. A missing row = a future
re-extraction.

**SP-3 hooks:** SP-0 also exposes the capture as a reusable, model-agnostic
forward-pass context so SP-3 can re-run with interventions (attention-knockout,
activation patching) without new plumbing. SP-0 ships the *hook surface*, not the
interventions.

## 3. Storage schema

- Layout: `cache/<capture_version>/<model_id>/<corpus_id>/<event_id>/…` with a
  manifest header per file (model metadata, code commit, corpus, capture_version).
- A new **`capture_version`** field (distinct from v1's `feature_layout`) marks the
  raw-capture schema so v1 and v2 caches never collide.
- **Checkpoint/commit discipline:** force-add past `.gitignore` (the v1 data-loss
  bug — fixed in `fe190b7`; keep the regression test green) and a per-event
  resilient-resume that reads what was actually committed.
- Per-event labeled metadata JSON for resume-from-cache.

## 4. Labeling

- **Answerable correctness:** normalized prediction matches any gold alias
  (normalized-EM) → correct; else wrong. Alias sets for TriviaQA/NQ; token-F1 ≥ θ
  as a robustness cross-check (EM brittleness — [[project_001_hotpotqa_pilot_2026-06-09_results]]).
- **Abstention detector:** pattern set ("not in the document", "cannot be
  determined", "no answer", …) + an NLI/entailment fallback. Validated on a
  hand-labeled sample; report its precision/recall in the pilot.
- **4-way assignment** per the parent doc §3 table; headline binary derived from it.
- Wrongful abstain on an answerable item → `wrong-answer` (positive).

## 5. Corpus adapters

Each adapter yields a common `DocQAEvent`-like record: `document` (empty for
closed-book), `question`, `gold_answer(s)/aliases`, `is_answerable`,
`evidence_span(s)` (token ranges, when available), `corpus_id`, plus the existing
provenance fields.

- **HotpotQA** — multi-hop; gold = supporting sentences → evidence spans.
- **SQuAD2** — answerable + unanswerable; single span; the unanswerable half is the
  hallucination testbed.
- **Closed-book TriviaQA / NQ** — no document; alias sets; routing metrics dark.
- **Long-context** — RULER / LongBench / needle-in-haystack at 4k–32k+; evidence
  span known by construction; **reduced N in the first allocation**.

Selection should target a **healthy fail/hallucination balance** per corpus
(v1 lesson: Phi-3 is too accurate on easy synthetic sets —
[[project_001_phi3_too_accurate_for_cem_matching]]); use natural difficulty +
the unanswerable split rather than synthetic distractors.

## 6. Model-agnostic capture

- Generalize the v1 hook (`extraction/hooks.py`, today Phi-3-specific fused
  `qkv_proj`) to a registry that resolves Q/K/V, attention weights, `o_proj`, and
  per-layer hidden states for each roster architecture (Phi-3, Llama-3, Qwen2.5,
  Mistral, Gemma-2), keyed off the model config. Two architecture-specific gotchas
  the v1 Phi-3 path does not face:
  - **GQA/MQA head-grouping** — Llama/Qwen/Mistral share KV heads across query
    heads; the v1 one-K-per-Q assumption breaks. The adapter must expand grouped KV
    to per-query-head before the per-head operators are formed.
  - **Gemma-2 alternating sliding-window attention + logit soft-capping** — half its
    layers attend only within a local window (not full `T×T`); the capture must
    record the effective attention support per layer so routing metrics are not
    computed against a mask the model never used.
- Capture the **prefill** pass (square `T×T`), skip decode steps — same contract as
  v1 (`hooks.py:149`).
- Float64 at the spectral boundary, float16/float32 at the cache boundary
  (Constitution Principle IV), unchanged.

## 7. Evaluation-harness interfaces

SP-0 ships the *interfaces*; SP-1..SP-3 implement metrics against them.

- A frozen-cache loader returning, per `(model, corpus, event)`, the labeled
  4-way/binary target + a pluggable feature-vector assembler.
- The `null_evidence` pack (repeated CV + permutation + Cohen's d + split-luck),
  generalized off the v1 hard-coded 7-feature assumption (`analyze_per_layer`,
  `null_evidence`, `stat_scan` hard-code 7 — make `N_FEATURES`/schema-generic).
- Incremental-AUROC-over-baseline (nested logistic / DeLong) and the
  cross-corpus / cross-model transfer splitters.
- The redundancy / partial-correlation utility.

## 8. Gate + pilot

1. **Benchmark first** (replaces every estimate): real per-event H200 timing +
   peak memory + on-disk size, per roster model × {short, long} context, with full
   rich capture. Sets N, the `T×T` layer-subset `S`, and the long-context N before
   any big run commits. Watch `nvidia-smi` (the v1 OOM fix is reasoned, not
   GPU-validated — [[project_001_hotpotqa_pilot_2026-06-14_results]]).
2. **Multi-model pilot** (≥2 diverse architectures × all corpora × small N):
   validates the schema, GQA handling, labeling + abstention detector, storage,
   resume, and OOM behavior end-to-end. Report fail/hallucination balance per
   corpus and the abstention-detector P/R.

## 9. First-allocation run plan (post-gate)

Per parent §9: 6 checkpoints (5 diverse @ 7–14B + Llama-3-8B base) × 3 short corpora
at full N + long-context reduced-N probe. Scaling ladder / 70B / SP-3 deferred,
pre-architected.

## 10. Open questions / interfaces to later sub-projects

- **`T×T` layer subset `S`** — which layers get full attention stored? Default:
  retrieval-head layers (per a quick retrieval-head scan) + a depth spread; finalize
  from the benchmark's size budget.
- **Token window `W`** for per-token dynamics — set from the size budget.
- **Semantic-entropy K** and sampling temperature — set in SP-1; SP-0 only stores
  the K samples.
- **Abstention threshold θ / NLI model** — pin in the pilot.

## 11. Test strategy

- Analytic/property tests for any new in-pass reduction (e.g., MP-fit on a known
  Gaussian matches the closed-form bulk edge) — Constitution Principle II, and the
  [[feedback_dcsbm_scaffold_not_oracle]] rule: verify primitives against
  closed-form, not against a scaffold.
- Per-architecture capture round-trip tests (recovered Q/K/V/attention shapes match
  the model's own, GQA expansion correct).
- A regression test that the `.gitignore`/checkpoint force-add still commits cache
  data (keep the `fe190b7` regression green).
- Labeling unit tests incl. the 4-way truth table and abstention-detector fixtures.
