# Pre-registration: v2 correctness-geometry first-allocation analysis

**Date**: 2026-06-19
**Status**: PRE-REGISTERED — written before any v2 data exists; this is the binding
analysis plan. Deviations must be logged as such.
**Parent**: `docs/superpowers/specs/2026-06-17-v2-correctness-geometry-program-design.md`
**Power evidence**: `src/phi3geom/scripts/power_simulation.py` (table in §6)

This exists because v1's headline (`AUROC=0.645`) was a 40-event mirage that collapsed
to 0.513 under honest CV. The cure is to fix the metric, the bars, the splits, and the
stopping rule **now**, before seeing data, so no post-hoc choice can manufacture a result.

## 1. Hypotheses

- **H1 (existence):** a pooled, distance-blind classifier on geometry features separates
  hallucination-vs-safe above chance.
- **H2 (beats baselines):** geometry adds AUROC **beyond** the cheap-confidence ceiling
  (logprob / predictive entropy / semantic entropy / linear probe).
- **H3 (transfers — the headline):** a detector trained on one corpus/model separates on
  a *held-out* corpus/model.
- **H4 (§5.6 dynamics):** the inter-head attention-drift family beats both cheap
  confidence AND the static-overlap control AND the v1 crossbar.

## 2. Primary metric & detector

Pooled logistic detector over the geometry feature vector, **blind to evidence
distance**; headline = **hallucination-vs-safe AUROC** (positive = {wrong-answer,
hallucination-on-unanswerable}). Reported via the `null_evidence` pack (repeated 5×CV,
permutation p, Cohen's d, split-luck) + the incremental-over-baseline and transfer
splitters. No single-split point estimates are ever reported as the headline.

## 3. Decision rules (the bars) — POWER-REVISED

The power analysis (§6) shows that at the pooled N (~18k) the bare existence bar is
nearly free (min detectable AUROC 0.511). So significance is **necessary but not
sufficient**; the load-bearing criteria are effect size, incremental gain, and transfer:

| Bar | Criterion |
|---|---|
| **B1 existence** (necessary) | pooled CV-AUROC 95% CI lower bound > 0.5 **and** permutation p < 0.05 |
| **B2 minimum effect** (NEW, power-driven) | pooled CV-AUROC point estimate **≥ 0.60** — below this the signal is statistically real but practically marginal and likely confounded |
| **B3 beats baselines** (load-bearing) | incremental ΔAUROC over the §5.0 baseline, 95% CI lower bound **> 0** (DeLong/nested) AND Δ point estimate ≥ 0.02 |
| **B4 transfer** (headline) | leave-one-corpus-out AND leave-one-model-out test AUROC CI lower bound > 0.5 |
| **B5 §5.6 dynamics** | §5.6 clears B3 over confidence AND over the static-overlap control AND over the v1 crossbar (program design §6 ladder) |

A "positive result" requires **B1 ∧ B2 ∧ B3 ∧ B4**. §5.6's claim additionally requires B5.

## 4. Splits

- **Primary:** pooled over all first-allocation events (~18k), distance-blind.
- **Transfer (headline):** leave-one-corpus-out and leave-one-model-out (the
  `analysis/harness/transfer.py` splitters), on the scalar-geometric features only.
- **Diagnostic (NOT headline):** per-(model,corpus) cell and per-measured-distance bin —
  **labelled diagnostics**; per §6 these are underpowered for subtle effects (only
  resolve AUROC ≥ 0.58 at N~1000), so they may only *localize* a signal the pooled
  detector already established, never *establish* one.

## 5. Confound battery (pre-specified)

Geometry must beat each confound-only model, and its incremental gain over the confound
set must clear B3: **document length, measured evidence distance, corpus id, answer
length, and the cheap-confidence baseline (logprob/entropy).** Cross-corpus + cross-model
transfer is the primary defense (a confound/corpus artifact will not transfer). CEM is
NOT used (v2 balances by natural fail/hallucination rate); balance is by `dataset/balance.py`.

## 6. Power analysis (the go/no-go)

Monte-Carlo of the repeated-CV AUROC estimator at first-allocation N, planting a single
informative feature with Cohen's d (AUROC = Φ(d/√2)) among noise. Source + reproduce:
`python -m phi3geom.scripts.power_simulation`.

```
min detectable AUROC (0.5 + 1.96·SE):  N=18000 → 0.511   N=6000 → ~0.52
power to clear "CI lower > 0.5":
   N      d   true_AUROC  mean   SE     ±CI    power
   250  0.10   0.528     0.513  0.052  0.103   0.03
   250  0.35   0.598     0.575  0.048  0.095   0.31
   250  0.50   0.638     0.619  0.045  0.088   0.80
  1000  0.20   0.556     0.543  0.022  0.044   0.54
  1000  0.35   0.598     0.590  0.018  0.036   1.00
  6000  0.10   0.528     0.524  0.009  0.018   0.76
  6000  0.20   0.556     0.554  0.008  0.016   1.00
 18000  0.10   0.528     0.527  0.005  0.009   1.00
```

**Readings that bind the plan:**
- **Pooled (~18k) is well-powered for any real effect** — even AUROC 0.528 is detected
  with power 1.0; CI half-width ±0.009. → If a geometry signal exists at all, the pooled
  detector finds it. This is why **B2 (min effect ≥ 0.60)** matters: significance is cheap
  here, so we must guard against celebrating a real-but-marginal 0.52.
- **Transfer tests (test-N ~3–6k) are well-powered** (resolve AUROC ≥ 0.53). → B4 is a
  fair, powered test, not a coin flip.
- **Per-cell (~1000) resolves only AUROC ≥ 0.58; N=250 only ≥ 0.64.** → per-cell/per-bin
  breakdowns are demoted to diagnostics (§4); do not over-read a null cell.
- **Budget is sufficient for the headline.** No need to scale N for the pooled/transfer
  claims; scaling would only sharpen per-cell diagnostics.

## 7. Multiple comparisons

Many metric families × cells. The **pooled headline + the two transfer tests are the
pre-registered primary**; every per-family / per-cell number is secondary and reported
with Benjamini–Hochberg FDR control across the secondary set. No secondary result is
promoted to a headline without re-running through B1–B4.

## 8. Stopping rule / no peeking

The detector + bars are frozen here. Analysis runs **once** on the complete frozen cache
after the pilot gate passes. No interim peeking at the headline AUROC to decide whether to
collect more; if B1–B4 are not met, that is the reported (null or marginal) result. Any
post-hoc analysis is labelled exploratory and cannot use the B-bars.

## 9. Falsification

- H1/H2 false ⇒ pooled AUROC < 0.60 or incremental CI crosses 0 → geometry is not a
  useful hallucination detector beyond confidence (a clean, publishable null, like v1).
- H3 false ⇒ in-corpus signal that does not transfer → it was a corpus/confound artifact.
- H4 false ⇒ §5.6 does not beat the static-overlap control → the *dynamics* add nothing
  (the inter-head story is "another crossbar null dressed up").
