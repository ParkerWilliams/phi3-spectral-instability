# Finding: v1 single-token attention-geometry does not detect Phi-3 DocQA failures

**Date**: 2026-06-16
**Status**: Null result (v1 feature set), reported with scope and limitations
**Data**: branch `experiment/pilot/2026-06-14-hotpot` (485 events, HotpotQA, Phi-3-mini-128k-instruct)
**Supersedes the optimism of**: the `pooled AUROC=0.645` checkpoint headline (shown below to be a small-sample artifact)

## 1. Question

Does a single, distance-blind classifier fed **only attention-geometry features**
separate Phi-3-mini failures from successes on real (HotpotQA) DocQA traffic?
(Design: `docs/superpowers/specs/2026-05-28-distance-blind-failure-detector-design.md`,
success bar = pooled AUROC whose 95% CI lower bound > 0.5.)

## 2. What was measured

- **Corpus**: HotpotQA multi-hop QA, 485 events extracted, **49.1% failure rate**
  (a healthy fail/success balance — the regime the study needs).
- **Model**: Phi-3-mini-128k-instruct, fp16, pinned revision.
- **Features (v1)**: per `(layer, head)`, three **scale-invariant** spectral
  descriptors on each of the QKᵀ and AVWO operators — stable rank, top-k
  Grassmannian distance, spectral entropy — plus a Forman-Ricci scalar
  (NaN on the spectral-only baseline). 7 features × 32 layers × 32 heads.
- **Important architectural fact**: v1 computes each operator **once per
  `(layer, head)` at a single token** (the answer-commit position) and
  broadcasts it across the lookback window (`pipeline.py:258`). There is no
  positional/temporal content; the `F_summary` mean/p10/p50/p90 stats are
  therefore **bit-identical** and `std ≈ 0` (verified). The effective per-event
  representation is 7168 single-token numbers.

## 3. Result: a rigorous null

| Evidence | Value | Reading |
|---|---|---|
| Checkpoint headline (200 CEM-matched events, 40 test) | AUROC **0.645**, CI [0.459, 0.817] | does not clear the >0.5-lower-bound bar |
| **Honest repeated CV** (5×20-fold, 485 events) | **0.513 ± 0.053** | chance |
| 500 random 80/20 splits of the full data | median 0.526, 97.5%ile **0.613** | — |
| Fraction of splits reaching the 0.645 headline | **0.0 %** | headline is **unreachable** on the honest data |
| **Permutation test** (200 label shuffles, on the CV mean) | null mean 0.499, **p = 0.37** | **cannot reject "no signal"** |
| Full per-`(layer, head)` 7168-dim fit (linear) | **0.494** | chance — the *complete* v1 information |
| Best single layer (of 32) | 0.539, CI crosses 0.5 | no layer beats chance |
| Per-feature Cohen's d (all 7) | all **\|d\| ≤ 0.10** | negligible effect sizes |
| Confound-only (doc length + evidence distance) | 0.42 | confounds are **not** predictive either |
| **Cross-head relational crossbar** (`D.npy`), full 31744-dim | 0.510, CI [0.395, 0.629] | chance |
| — per-layer mean (64-dim) | 0.539, CI [0.428, 0.651] | chance |
| — per-layer head-graph spectral gap (64-dim) | 0.450, CI [0.334, 0.563] | chance |

Three independent lines converge:

1. **The 0.645 was a small-sample artifact.** It came from the 200-event
   CEM-matched subset with a 40-event test split. On the full 485, a single-split
   AUROC never once reaches 0.645 across 500 tries (it tops out at 0.613); the
   honest cross-validated value is **0.513**.
2. **Not distinguishable from chance.** Permutation p = 0.37 ≫ 0.05; the
   label-shuffled null (0.499) and the real fit (0.513) sit inside each other's
   noise.
3. **Negligible effects.** Every feature's |d| < 0.10; the strongest whisper is
   `avwo_spectral_entropy` at 0.099.

The "maybe the signal is averaged out across layers/heads" rescue hypothesis is
**tested and rejected**: the full 7168-dim representation (no averaging) is also
at chance, and no single layer beats chance. The **cross-head relational**
hypothesis — that *how heads relate to each other* (the pairwise-Grassmannian
crossbar) carries signal even though each head in isolation does not — is **also
tested and rejected**: all three crossbar reductions straddle 0.5.

## 4. Conclusion (scoped)

> On HotpotQA, the **v1 single-token, scale-free attention-geometry feature set**
> does not separate Phi-3-mini failures from successes — neither the **per-head**
> spectral shape (verified at the full per-`(layer, head)` resolution, with a
> permutation test and negligible effect sizes) nor the **cross-head relational**
> crossbar.

This is a clean negative result for *these features*. It is **not** a claim that
attention geometry is uninformative in general.

## 5. What this does NOT test (named future work)

- **Operator magnitude.** All three v1 spectral features are scale-invariant, so
  the set is blind to σ_max / Frobenius / nuclear norm. Magnitude features are
  now implemented (`FEATURE_NAMES` 7→13, branch `001`, commit `db3437a`) but need
  a fresh extraction to populate.
- **Positional / temporal dynamics.** v1 is single-token by construction; how the
  geometry evolves across the lookback window is the explicit v2 enhancement.
- **Attention-to-evidence.** Whether the model attended to the gold span — a more
  directly causal signal than operator spectra — is unmeasured.
- Other corpora, other models, calibration / natural base rate.

## 6. Reproduce

```bash
# on the pod (485-event cache present):
python scripts/null_evidence.py   --cache-root cache/ --out reports/null_evidence.json
python scripts/analyze_per_layer.py --cache-root cache/ --with-full-lh --out reports/per_layer_analysis.json
```

Reports: `reports/null_evidence.json`, `reports/per_layer_analysis.json`,
`reports/pilot/{pooled_auroc,confound_audit,distance_diagnostic}.json` on the
experiment branch.
