# Contract: Per-Regime Composite Logistic

**Scope**: Function signatures for the per-regime composite logistic regression (`FR-008`) and
the pooled negative control (`SC-003`). Implemented in `src/phi3geom/analysis/composite.py` and
`src/phi3geom/analysis/pooled_negative_control.py`.

The contract enforces Constitution Principle III at the function-signature level: it is
impossible to fit a per-regime composite on multi-bin data, and the pooled negative control
exists in a separately named module.

---

## `fit_per_regime_composite(features, labels, bin_id, *, l2_penalty, random_state) -> PerRegimeCompositeFit`

**Inputs**:
- `features`: `np.ndarray[float64]` of shape `(n_events, n_features)`. Per-event candidate
  features: per-atomic-unit features aggregated (e.g., mean over the lookback window), head-
  graph aggregates, spine FPC scores. NaNs permitted in the Forman-Ricci-derived columns only;
  imputation happens inside this function with per-bin median (research.md §10).
- `labels`: `np.ndarray[bool]` of shape `(n_events,)`. `True` = fail event, `False` = control.
- `bin_id`: `enum {B1, B2, B3, B4, B5, B6}`. Used for:
  1. Asserting all events are from this bin (see Invariants).
  2. Tagging the resulting `PerRegimeCompositeFit.bin_id`.
- `l2_penalty`: `float` — L2 regularization strength. Default: `1.0` (sklearn convention).
- `random_state`: `int` — derived from `SHA1("analysis:per_regime_composite:" + bin_id)` for
  reproducibility.

**Output**: a `PerRegimeCompositeFit` dataclass (data-model.md) with all fields populated.

**Invariants**:
- The caller MUST pre-filter `features` and `labels` to a single bin. The function asserts:
  `len(features) == len(labels)` and that the bin_id matches a study-known bin.
- Cross-bin fitting is impossible by API: the function takes a single `bin_id` and pre-filtered
  data. Bin assignment is the caller's responsibility, validated at the function boundary.
- AUROC is computed on a held-out 20% split, stratified by label, with `random_state` from
  `bin_id`. This is the per-bin equivalent of the DCSBM prior-work split rule.
- Confidence interval: percentile bootstrap with 1000 resamples, derived from a per-call seed
  `SHA1("ci:per_regime:" + bin_id + ":" + str(random_state))`.
- Output `coefficients` length equals input `features.shape[1]`.

**Forbidden patterns**:
- `bin_id == None` or `bin_id == "ALL"` — MUST raise `ValueError("bin_id must be a single bin
  enum; use pooled_negative_control.fit for cross-bin analyses (SC-003 only).")`.
- Calling with `features.shape[0] < 100` — MUST raise `InsufficientDataError`. The minimum
  per-bin event count is 100 (50 fail + 50 control); below this the fit is unreliable.

---

## `pooled_negative_control.fit(features, labels, *, l2_penalty, random_state) -> PooledNegativeControl`

**Inputs**:
- `features`: `np.ndarray[float64]` of shape `(n_events, n_features)` — events POOLED across
  all 6 bins. The caller is required to provide pooled data explicitly.
- `labels`: `np.ndarray[bool]`.
- `l2_penalty`: `float`. Default: `1.0`.
- `random_state`: derived from `SHA1("analysis:pooled_negative_control")`.

**Output**: a `PooledNegativeControl` dataclass.

**Invariants**:
- This function MUST live in `src/phi3geom/analysis/pooled_negative_control.py`. Importing it
  from `src/phi3geom/analysis/composite.py` raises `ImportError` by design (the two modules do
  not cross-import).
- AUROC is computed on a single 80/20 stratified split of the pooled data.
- Output is used ONLY for the SC-003 negative-control report. The reporting module
  (`src/phi3geom/reporting/writeup.py`) annotates pooled results as "negative control" in
  every output it produces.

**Forbidden patterns**:
- Re-exporting `pooled_negative_control.fit` under any name from `composite.py` is a violation
  of Constitution Principle III and MUST fail code review (enforced by a `tests/unit/
  test_principle_iii_segregation.py` test that imports `composite` and asserts the symbol is
  NOT present).

---

## `fit_functional_logistic(spine_curves, labels, bin_id, edge_type, *, n_fpcs_variance_threshold, random_state) -> FunctionalLogisticResult`

**Inputs**:
- `spine_curves`: `np.ndarray[float64]` of shape `(n_events, 32)` — the 32-point spine curve
  for each event, single-aggregate (typically `mean_grassmannian` at each layer). Multi-
  aggregate fits are out of v1 scope.
- `labels`: `np.ndarray[bool]`.
- `bin_id`: `enum`. Same single-bin invariant as `fit_per_regime_composite`.
- `edge_type`: `enum {qkt_grassmannian, avwo_grassmannian}`. Tags the result.
- `n_fpcs_variance_threshold`: `float`. Default `0.95` (research.md §8).
- `random_state`: derived from `SHA1("analysis:functional_logistic:" + bin_id + ":" +
  edge_type)`.

**Output**: a `FunctionalLogisticResult` dataclass.

**Invariants**:
- FPCs are fit on the per-bin pooled fail+control curves to extract a shared depth basis.
- Functional logistic regression is fit on the FPC scores against `labels`.
- `beta_function` is reconstructed by projecting the fitted coefficients back through the FPC
  basis, then exported on the depth grid `[0, 1, …, 31]`.
- 95% CI bands on `beta_function` use a percentile bootstrap with 1000 resamples (consistent
  with the composite logistic).
- `discriminative_depth_intervals` is computed as the union of layer intervals where the CI
  band excludes zero (`beta_ci_lower > 0` OR `beta_ci_upper < 0`). Inclusive-on-both-ends.

**Forbidden patterns**: same single-bin invariant as composite; same minimum-event-count rule.

---

## Test obligations

These contract tests ensure the per-regime invariant is enforced at the API level:

- `tests/unit/test_principle_iii_segregation.py`:
  - Asserts `pooled_negative_control.fit` is NOT exported from `phi3geom.analysis.composite`.
  - Asserts `phi3geom.analysis.composite.fit_per_regime_composite(..., bin_id=None)` raises
    `ValueError`.
  - Asserts `phi3geom.analysis.composite.fit_per_regime_composite(..., bin_id="ALL")` raises
    `ValueError`.

- `tests/contract/test_sklearn_logistic.py`:
  - Shape contract: input `(N, F)` → output coefficients `(F,)` and intercept scalar.
  - NaN handling: feature matrices with NaN in the Forman-Ricci column flow through fit
    without raising (median imputation occurs internally).
  - Determinism: identical inputs with identical `random_state` yield bit-identical
    `coefficients` and `intercept`.

- `tests/contract/test_skfda_func_logistic.py`:
  - Shape contract: `(N, 32)` spine curves → β(ℓ) of length 32.
  - Variance threshold: setting `n_fpcs_variance_threshold=0.95` returns `n_fpcs ∈ [2, 8]` on a
    synthetic 32-point curve with known intrinsic dimension 4.
  - Determinism: same inputs + same `random_state` → same `beta_function`.
