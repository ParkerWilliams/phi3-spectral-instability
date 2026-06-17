# Contract: Evaluation-Harness Interfaces

**Feature**: `002-sp0-extraction-substrate`

SP-0 ships the **interfaces** SP-1/SP-2/SP-3 build on — **not** the metrics. These are the
seams that let SP-1/SP-2 run as pure offline CPU sweeps over the frozen cache and SP-3
re-run forward passes with interventions. Generalized off the v1 hard-coded 7-feature
assumption (`analyze_per_layer`, `null_evidence`, `stat_scan`).

## I1 · Frozen-cache loader

```
load(cache_root, capture_version, *, models=None, corpora=None)
    -> HarnessDataset
```
- Returns a read-only `HarnessDataset`: per event yields
  `(bundle, target, group)` where `group = {corpus_id, model_id, class_4way}`.
- Verifies `capture_version` + manifest SHA per bundle; raises on mismatch (no silent
  fallback).
- Accepts a **pluggable feature assembler** `assemble(bundle) -> np.ndarray` of **arbitrary
  width** — SP-1/SP-2 register their own; SP-0 hard-codes none.

## I2 · Null-evidence pack (feature-width-generic)

```
null_evidence(X, y, *, groups=None, n_repeats, n_folds, n_perm, seed) -> dict
```
Returns `{cv_auroc_mean, cv_auroc_std, permutation_p, cohens_d_per_feature,
split_luck_distribution}`. No hard-coded `N_FEATURES`; shape derived from `X`. This is the
pre-registered existence bar (CI lower bound > 0.5 **and** permutation p < 0.05).

## I3 · Incremental-over-baseline

```
incremental_auroc(X_geom, X_baseline, y, *, groups, seed) -> dict
```
Nested logistic / DeLong: returns `{auroc_baseline, auroc_combined, delta, delta_ci}`.
The beats-baselines bar = `delta_ci` lower bound > 0. SP-1 supplies `X_baseline`
(confidence + semantic entropy + probe); SP-2 supplies `X_geom`.

## I4 · Transfer splitters (the headline differentiator)

```
cross_corpus_split(dataset)  -> Iterator[(train_idx, test_idx)]   # leave-one-corpus-out
cross_model_split(dataset)   -> Iterator[(train_idx, test_idx)]   # leave-one-model-out
```
Train on one corpus/model, test on another. Cross-model transfer operates at the
**scalar-geometric-feature** level (curvature, MP-spike count, attention-to-evidence mass,
semantic entropy) — comparable across differing `d_model`/`n_heads`; raw-activation probes
and DLA are reported per-model only (program §6).

## I5 · Redundancy / orthogonality

```
redundancy(X_named, y) -> dict   # partial correlations + nested ablation
```
So "no tool untouched" does not collapse into 12 correlated copies of one confidence
detector (program §5 rigor note).

## Boundary

SP-0 implements I1–I5 as **contracts with trivial reference assemblers/targets for
testing only**. The actual baseline features (SP-1), geometry features (SP-2), and
intervention re-runs (SP-3) are out of scope. SP-3's re-run uses the reusable forward-pass
capture surface (`extraction/capture.py`) exposed for interventions — SP-0 ships that
*surface*, not the interventions.

## Validation

- A stub consumer registers a 1-D assembler, loads the frozen cache, and obtains a pooled
  AUROC + full null-evidence pack + one cross-corpus split — **without re-running
  extraction** (spec US5 Independent Test).
- All interfaces accept `groups` so CV never leaks across the same event's model/corpus.
