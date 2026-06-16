# Design note: v2 attention-geometry feature set

**Date**: 2026-06-16
**Status**: Draft design note — to be turned into a `/speckit-specify` spec in a fresh session
**Builds on**: the v1 null result (`docs/superpowers/findings/2026-06-16-v1-geometry-null-result.md`)
**Code already staged**: branch `001-phi3-attention-geometry-v1`, commit `db3437a` (magnitude norms)

## 1. Why v2 exists — the v1 null and its two structural blind spots

v1 single-token attention-geometry is a **clean, well-powered null** on HotpotQA
(485 events, 49.1% fail): per-head spectral shape, the full 7168-dim
per-`(layer,head)` representation, AND the cross-head crossbar are all at chance
(honest CV 0.513 ± 0.053, permutation p = 0.37, all |Cohen's d| < 0.10). The
`0.645` headline was a 40-event-CEM artifact (0/500 splits of the full data reach
it). See the findings doc for the full table.

The v1 feature set has **two structural blind spots**, by construction:

1. **Scale-free.** All three spectral primitives discard operator magnitude:
   stable rank (= ‖M‖_F²/‖M‖₂², a ratio), spectral entropy (normalized), and the
   Grassmannian (subspace orientation). The crossbar `D` is also scale-free.
   → Operator **magnitude** was never measured.
2. **Single-token.** `pipeline.py:258` computes each operator ONCE at the
   answer-commit token (`recover_qkt_avwo` ignores `token_idx`, line ~277) and
   broadcasts it across the 256-position lookback. So `F_summary`'s
   mean/p10/p50/p90 are bit-identical and `std ≈ 0` (verified). → Positional /
   temporal **dynamics** were never measured.

Neither blind spot can be filled from the existing cache: the raw QKᵀ/AVWO
operators (and attention weights) are discarded at extraction. **All v2 levers
require a fresh GPU re-extraction.**

## 2. The three open levers (priority order)

### L1 — Operator magnitude norms  *(implemented; just needs extraction)*
- Add `spectral_norm` (σ_max), `frobenius_norm`, `nuclear_norm` per operator.
- **Status: DONE in code** — `FEATURE_NAMES` 7→13, appended AFTER ricci so v1
  indices 0..6 are unchanged; shapes derive from `N_FEATURES`; analytic tests;
  full suite green (commit `db3437a`).
- Hypothesis: failures show **diffuse / low-magnitude** attention the scale-free
  features can't see. Cheapest lever — the norms are free off the SVD already
  computed for stable rank / entropy.

### L2 — Positional / temporal dynamics  *(the structural fix; bigger change)*
- Make the features genuinely **per-token across the lookback window** instead of
  single-token broadcast. Requires: `recover_qkt_avwo` to actually use
  `token_idx` (currently `_ = token_idx`), and `pipeline.py` to compute per
  lookback position instead of `F_tensor[:, ell, h, :] = features` (broadcast).
- Payoff: `F_summary`'s 5 stats (mean/p10/p50/p90/std) stop being degenerate and
  become real signal; enables the deferred FDA β(ℓ) / spine-curve analysis that
  is meaningless on single-token data.
- Hypothesis: the *trajectory* of the geometry as the model reads toward the
  answer carries signal that the static snapshot does not.

### L3 — Attention-to-evidence  *(new family; arguably most causal)*
- Features on the realized attention distribution: did the model attend to the
  **gold-evidence span**? per-query attention entropy, mass on the answer-relevant
  tokens, etc. Only Ricci currently touches the attention matrix `A`.
- Requires plumbing the gold-span token range into extraction. New code.
- Hypothesis: "did it look at the right place" is more directly tied to DocQA
  correctness than any spectral property of the operators.

## 3. Decisions the v2 spec must make

- **Which levers in the first v2 run?** Recommendation: **L1 + L2 together** —
  both need the same re-extraction, L1 is already coded and free, and L2 is the
  change that makes the 5 summary stats (and any future FDA) meaningful. Treat L3
  as a fast-follow if the gold-span plumbing is cheap.
- **Re-extract the same 485 events** (we have their `event.json` — deterministic,
  gives a clean matched comparison vs the v1 null) **vs. scale N** for power. The
  v1 null was well-powered at 485; matched re-extraction is the cleaner science.
- **Feature count / layout** if L2/L3 add axes beyond the current 13.

## 4. Evaluation (unchanged — keep the v1 rigor)

- Pooled, distance-blind detector. **Success bar: 95% CI lower bound > 0.5 AND
  permutation p < 0.05** (the v1 null taught us the single-split point estimate
  lies — always report the `null_evidence` pack: repeated CV + permutation +
  Cohen's d + the split-luck distribution).
- Reuse `scripts/null_evidence.py`, `analyze_per_layer.py`, `crossbar_signal.py`.

## 5. Prerequisites — DONE

- CUDA OOM cascade + `.gitignore`/checkpoint data-loss bugs are **both fixed**
  (commit `fe190b7`): `git_checkpoint` force-adds, patterns anchored, GPU freed
  per event + on the OOM path, `expandable_segments`. Re-extraction is now safe.
  (OOM fix is reasoned/symptom-matched, not GPU-validated — watch `nvidia-smi`.)

## 6. Implementation gotchas

- **Analysis scripts hard-code 7 features** (`analyze_per_layer`, `null_evidence`,
  `stat_scan`) — update to `N_FEATURES`-generic before analyzing the 13+-wide v2 cache.
- Per **Constitution Principle V** / `CLAUDE.md`, changing the extracted feature
  set is a methodology change → ratify via `/speckit-specify`, not script edits.
  The `FEATURE_NAMES` docstring flags it as a Principle IV breaking change; the
  manifest's `feature_layout` records which version a cache was extracted under,
  so v1 and v2 caches stay distinguishable.

## 7. Cost

~33 GPU-hr for a 485-event re-extraction (the v1 run's figure; the forward pass
dominates, the norms add ~nothing). Decide pod/GPU class when speccing.

## 8. Provenance

- v1 data + all reports: branch `experiment/pilot/2026-06-14-hotpot`.
- v2 magnitude-norm code + infra fixes + this note: branch `001-phi3-attention-geometry-v1`.
