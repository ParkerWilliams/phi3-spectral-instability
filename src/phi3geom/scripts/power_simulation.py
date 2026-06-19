"""Pre-experiment power simulation (SP-0 prep) — CPU.

Monte-Carlos the headline metric (repeated-CV AUROC via the analysis harness) at the
first-allocation sample sizes, for a sweep of planted effect sizes, to answer the
go/no-go questions BEFORE spending the GPU allocation:

1. What is the CI resolution (SE / 95% half-width) of the pooled AUROC at each N?
2. What is the minimum detectable true effect (Cohen's d / AUROC) at each N — i.e.,
   how big must the geometry signal be to clear "CI lower bound > 0.5"?
3. How does that change across pooled vs per-(model,corpus)-cell vs transfer-test N?

This is exactly the question v1 failed on ("CI ±0.18, unresolvable at this N"). A
single feature with Cohen's d has AUROC = Φ(d/√2); the sim plants that separation in
one informative feature among noise and measures the estimator's sampling distribution.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

from phi3geom.analysis.harness.null_evidence import _cv_auroc

# Representative first-allocation sample sizes (events feeding a single fit).
N_GRID = (250, 1000, 6000, 18000)
# Planted single-feature Cohen's d (0.1 ≈ v1's negligible features).
D_GRID = (0.1, 0.2, 0.35, 0.5)


def auroc_from_d(d: float) -> float:
    return float(norm.cdf(d / np.sqrt(2.0)))


def _synth(n: int, d: float, *, n_noise: int = 4, seed: int = 0):
    rng = np.random.default_rng(seed)
    y = np.tile([0, 1], n // 2 + 1)[:n]
    signal = rng.standard_normal(n) + d * y  # mean-shift d between classes
    noise = rng.standard_normal((n, n_noise))
    return np.column_stack([signal, noise]).astype(np.float64), y.astype(int)


def simulate_cell(n: int, d: float, *, n_trials: int = 120, n_folds: int = 5, seed0: int = 0) -> dict:
    aurocs = []
    for t in range(n_trials):
        X, y = _synth(n, d, seed=seed0 + t)
        a = _cv_auroc(X, y, n_folds=n_folds, seed=seed0 + t)
        if not np.isnan(a):
            aurocs.append(a)
    a = np.asarray(aurocs)
    se = float(a.std())
    return {
        "n": n,
        "d": d,
        "true_auroc": round(auroc_from_d(d), 4),
        "mean_auroc": round(float(a.mean()), 4),
        "se": round(se, 4),
        "ci_halfwidth": round(1.96 * se, 4),
        # approx power: fraction of experiments whose typical CI lower bound clears 0.5
        "power_clear_0.5": round(float((a - 1.96 * se > 0.5).mean()), 3),
    }


def min_detectable_auroc(n: int, *, n_trials: int = 120) -> float:
    """0.5 + 1.96·SE near the chance regime — the smallest true AUROC that clears the bar."""
    a = np.asarray(
        [_cv_auroc(*_synth(n, 0.0, seed=t), n_folds=5, seed=t) for t in range(n_trials)]
    )
    a = a[~np.isnan(a)]
    return round(0.5 + 1.96 * float(a.std()), 4)


def main() -> int:
    print("min detectable AUROC at chance (0.5 + 1.96·SE):")
    for n in N_GRID:
        print(f"  N={n:6d}  min_detectable_AUROC={min_detectable_auroc(n)}")
    print("\npower to clear 'CI lower > 0.5' by (N, planted d):")
    print(f"  {'N':>6} {'d':>5} {'true_AUROC':>10} {'mean':>7} {'SE':>7} {'±CI':>7} {'power':>6}")
    for n in N_GRID:
        for d in D_GRID:
            r = simulate_cell(n, d)
            print(f"  {r['n']:>6} {r['d']:>5} {r['true_auroc']:>10} {r['mean_auroc']:>7} "
                  f"{r['se']:>7} {r['ci_halfwidth']:>7} {r['power_clear_0.5']:>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
