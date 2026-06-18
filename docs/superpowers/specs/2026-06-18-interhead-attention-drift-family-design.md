# Design note: inter-head attention-drift family (program catalog §5.6)

**Date**: 2026-06-18
**Status**: Approved (brainstorming) — feeds the SP-0 capture-manifest update + the SP-2 analysis
**Parent program**: `docs/superpowers/specs/2026-06-17-v2-correctness-geometry-program-design.md`
**Touches**: SP-0 spec `specs/002-sp0-extraction-substrate/` (a capture add) + a future SP-2 family
**Branch**: `002-sp0-extraction-substrate`

---

## 1. Motivation — the static inter-head null, and the bet

v1's **crossbar** measured a *static* inter-head relation — pairwise top-k Q/K
**subspace** Grassmannian between heads — and it was a clean null (0.51 / 0.54 / 0.45
across the full upper-triangle, per-layer-mean, and Fiedler-gap reductions). Every v2
metric so far is either per-head (DLA, retrieval-head, norms) or aggregate; the
*relational geometry between heads* and **how it drifts** has not been tested.

This family makes the bet that the **dynamics of inter-head relations carry signal the
static snapshot does not** — and it changes *two* things at once relative to the null,
so the design must isolate which (if either) matters:

1. **A new object** — inter-head **attention-distribution overlap** (do heads cover the
   same vs complementary source tokens), not Q/K subspace orientation.
2. **A new axis** — the **joint token×layer drift field**: does the head configuration
   *reorganize* as the model reads toward the answer and as information moves through
   depth?

Hypothesis: on a correct answer the heads **collectively lock onto the evidence** (the
configuration sharpens — dispersion collapses, attention modes collapse, coverage
rises) as the evidence token is read; on a hallucination they do not.

## 2. The four core decisions (this design)

| Decision | Choice |
|---|---|
| Drift axis | **Joint token × layer field** `S(t, ℓ)` |
| Relational object | **Inter-head attention-distribution overlap** |
| Per-cell summary | **Both** a divergence configuration **and** the overlap-matrix spectrum |
| Drift reduction | **Both** a transferable field reduction **and** an evidence-anchored changepoint |

## 3. Per-cell summary `S(t, ℓ)`

At query token `t`, layer `ℓ`, let `A_h ∈ Δ^{T}` be head `h`'s post-softmax attention
distribution over the `T` source tokens. The per-cell summary stacks two corpus-agnostic
views (both cheap off the same `H × T` block) plus one with-context diagnostic:

- **Divergence configuration** (transport view): inter-head **dispersion** = mean pairwise
  **Jensen–Shannon** distance between `{A_h}` (and Hellinger as a robustness twin).
  Low = redundant heads; high = specialized heads.
- **Overlap-matrix spectrum** (spectral view): form the `H × H` head-head similarity
  matrix `M_{hh'} = 1 − JS(A_h, A_{h'})` (or Bhattacharyya); report **effective rank**,
  **Fiedler (algebraic-connectivity) gap**, and **top eigenvalue** — the number of
  distinct attention modes among heads.
- **Evidence-coverage** (with-context diagnostic ONLY — needs a gold span, so it is
  absent for closed-book TriviaQA/NQ): head-set attention mass on the gold-evidence span.

`S(t, ℓ)` is therefore a small fixed-length vector of scalars per cell.

## 4. Drift reduction

`S(t, ℓ)` over the sampled grid is the per-event **drift field**. It is reduced two
ways, separated by what can transfer across models/corpora:

- **Transferable headline (corpus- and model-agnostic).** Resample `S` onto a
  **normalized grid** — **relative depth `ℓ/L`** (so 32- and 80-layer models compare) ×
  **log-spaced token offsets** from the answer (offsets, not absolute positions, so
  different `T` compare). Features: **trajectory statistics** — total variation of the
  field, peak-drift depth-fraction and token-offset, mean velocity — plus **FPCA scores**
  over the field (fit across events). These are the features the existence /
  beats-baselines / **transfer** bars are evaluated on.
- **With-context diagnostic.** Evidence-anchored **CUSUM/EWMA changepoint** of `S` as the
  query crosses the gold-evidence token: the **magnitude, sharpness, and location** of the
  shift. Reuses the constitution's two-stage CUSUM/EWMA-on-FPCA machinery. With-context
  corpora only; reported as a mechanistic diagnostic, never the transfer headline.
- **Built-in static control.** The **static** summary — `S` at the answer-position cell
  only (no token axis) — is computed alongside, so the analysis can separate *"the
  dynamics carry signal"* from *"the new attention-overlap object carries signal even
  statically."* Without this control the family cannot claim the **drift** is what works.

## 5. Capture — the SP-0 manifest addition (urgent: before the GPU run)

The raw material is the `H × T` attention block at each sampled `(t, ℓ)`. Storing it for
many query positions × all layers is ~3+ GB/event — far too big (same constraint as the
RMT token cloud). So §5.6 is an **in-pass reduction**:

- During the forward pass, off the attention tensor **eager already materializes**,
  compute `S(t, ℓ)` on-GPU at a **log-spaced query set** `{answer − offset : 0, 1, 2, 4,
  8, …, 256} ∪ {gold-evidence positions}` × **all layers**, and store **only** the
  summary surface `S(t, ℓ)` per event (≈ `n_t × L × K_summary` scalars — tiny).
- New `CaptureBundle` field **`interhead_drift_surface`**; the capture manifest
  (`extraction/manifest.py`) maps the §5.6 metrics to it. No extra forward pass is needed
  — it is a reduction over already-computed attention.
- Float64 at the spectral seam for the overlap-matrix eigen-computation (Constitution IV),
  downcast at the cache boundary.
- The query-position sampling is the proposed default; it is pinned in the SP-0 spec.

This is a change to the **captured feature set**, so per Constitution Principle V it
ratifies through the spec/constitution path (an SP-0 spec amendment + a manifest/
`capture_version` note), **before** the first-allocation run — otherwise the field is
unrecoverable without a re-extraction.

## 6. Evaluation

Reuse the SP-0 harness (`analysis/harness`): the null-evidence pack, incremental-over-
baseline, transfer splitters, redundancy.

- **Existence:** pooled AUROC 95% CI lower bound > 0.5 **and** permutation p < 0.05.
- **Beats-baselines — a specific ladder.** §5.6 must beat, incrementally: **(a)** cheap
  confidence (§5.0); **(b)** per-head **attention-to-evidence** (§5.2); and **(c)** the
  **static v1 crossbar / the static-overlap control (§4)**. Clearing (c) is the load-
  bearing test — it is what shows the *dynamic, relational* content adds signal over both
  the static relation and the per-head story.
- **Transfer (headline):** cross-corpus and cross-model transfer on the agnostic features.
- **Redundancy:** partial-correlation / nested ablation vs the other families, so §5.6 is
  not a re-encoding of attention-to-evidence or confidence.

## 7. Scope, sequencing & what's CPU-validatable now

- **Not a new sub-project** — a new catalog family (§5.6) added to the program design,
  with an SP-0 capture dependency and an SP-2 analysis home.
- **SP-0 (now):** the in-pass `S(t, ℓ)` computation + `interhead_drift_surface` bundle
  field + manifest mapping must land before the GPU run.
- **SP-2 (later):** the field reduction + the detector + the baseline-ladder evaluation.
- **CPU-validatable immediately** (like the other SP-0 primitives, TDD on the dev box):
  the per-cell summary math — pairwise **Jensen–Shannon/Hellinger dispersion**, the
  **overlap-matrix spectrum** (effective rank / Fiedler / top-eig) — and the field
  reduction — **trajectory statistics**, **CUSUM/EWMA changepoint**, **FPCA** over the
  normalized grid. Only the in-pass GPU wiring and the live field are pod-bound.

## 8. Risks

- **"Another crossbar null dressed up."** Mitigated by the static-overlap control (§4) and
  the §5.6→(c) baseline rung (§6): the family only counts if the *dynamics* beat the
  *static* relation.
- **Grid-normalization artifacts** across models (different `L`, `T`): the relative-depth ×
  log-offset resampling is the defense; verify the resampled field is stable under a
  layer-count change before trusting cross-model transfer.
- **Evidence-coverage / changepoint absent closed-book:** by construction these are
  with-context diagnostics; the transferable features never depend on them, so the
  headline survives closed-book.
- **In-pass cost:** the per-cell eigen-computation over `H×H` at `n_t × L` cells adds
  forward-pass compute; benchmark it in the SP-0 gate before committing the sampling
  density.
