# Distance-Blind Failure Detector — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the per-bin (per-regime) composite analysis with a single pooled classifier that is blind to evidence distance, evaluated on the existing balanced CEM set, with evidence distance recorded truthfully and used only as a post-hoc diagnostic.

**Architecture:** The extraction pipeline stays intact; we add a true evidence-distance *measurement* at tokenize time. The per-bin `composite` becomes a secondary diagnostic. A new `pooled_detector` module fits the headline model over all matched events pooled. Reporting gains a pooled-AUROC headline, a distance-diagnostic slice, and a confound audit. The pilot driver pools its already-CEM-matched events into one fit.

**Tech Stack:** Python 3.11, numpy (float64), scikit-learn (`LogisticRegression`, `roc_auc_score`), pytest. Governed by constitution v2.0.0 (Principle III: pooled distance-blind primary; per-regime is diagnostic).

**Design source:** `docs/superpowers/specs/2026-05-28-distance-blind-failure-detector-design.md`

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/phi3geom/dataset/distance.py` | distance math + bin assignment | **Modify**: add tolerant `diagnostic_bin()` (no raise) |
| `src/phi3geom/extraction/pipeline.py` | per-event forward + features | **Modify**: measure true evidence distance, store on event |
| `src/phi3geom/analysis/types.py` | analysis dataclasses | **Modify**: add `PooledDetectorFit` |
| `src/phi3geom/analysis/pooled_detector.py` | the headline pooled fit | **Create** |
| `src/phi3geom/reporting/pilot_reports.py` | report writers | **Modify**: add pooled-auroc / distance-diagnostic / confound-audit writers; repoint `write_pilot_summary` |
| `src/phi3geom/scripts/pilot_main.py` | pilot driver | **Modify**: pool matched events into one fit; new reports |
| `tests/unit/test_evidence_distance_measure.py` | distance-measure unit tests | **Create** |
| `tests/unit/test_diagnostic_bin.py` | tolerant-bin unit tests | **Create** |
| `tests/unit/test_pooled_detector.py` | pooled-detector unit tests | **Create** |
| `tests/unit/test_principle_iii_segregation.py` | architecture guard | **Modify**: reframe for v2.0.0 |
| `tests/unit/test_pilot_reports_pooled.py` | new report writers | **Create** |
| `tests/integration/test_pilot_pipeline.py` | end-to-end GPU test | **Modify**: new report API |

**Nothing is deleted.** `pooled_negative_control.py` and `write_per_bin_auroc` are imported by the US3/US4 full-study scripts (`run_analysis.py`, `full_study_main.py`, `writeup.py`), which are out of this MVP's scope; we add the pooled path alongside them.

---

## Out of scope for this plan (deferred)

These follow from the design but are explicitly NOT in this MVP plan:

- **Head/depth attribution (β(ℓ), FPCA/FDA).** The MVP detector uses the 7-dim mean-over-(layer,head) feature vector, which cannot attribute to heads/depths. The "where does the signal live by depth" question (design §3 attribution / §6) needs a richer feature vector and the FDA machinery — a separate feature.
- **Ricci marginal-gain** for the pooled detector (design §6).
- **Full-study reconciliation:** retiring the SC-003 `pooled_negative_control` and re-pointing `run_analysis.py` / `full_study_main.py` / `writeup.py` from per-bin headline to pooled. These are US3/US4 scripts; reconciling them is its own feature.
- **Natural base-rate / calibration, real corpora, B5/B6 long-context + RoPE-wrap** (design §7 non-goals).
- **Generator placement fix:** if the measured-distance diagnostic shows a degenerate spread (most events in one bin), generation may need to vary evidence position (design §8). Deferred until the measured spread is observed — the diagnostic surfaces it.

---

## Task 1: Tolerant diagnostic bin assignment

The primary analysis is distance-blind, but the diagnostic slices the detector by measured distance. Most synthetic docs are short (often < 128 tokens to evidence), so the strict `assign_bin` (raises outside [128, 4096)) is wrong for a diagnostic. Add a tolerant variant that buckets everything, never raises.

**Files:**
- Modify: `src/phi3geom/dataset/distance.py`
- Test: `tests/unit/test_diagnostic_bin.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_diagnostic_bin.py
"""Tolerant post-hoc diagnostic binning (constitution v2.0.0, Principle III)."""
from __future__ import annotations

from phi3geom.dataset.distance import diagnostic_bin


def test_below_b1_floor_is_b0():
    assert diagnostic_bin(10) == "B0"
    assert diagnostic_bin(127) == "B0"


def test_in_range_matches_bin_ranges():
    assert diagnostic_bin(128) == "B1"
    assert diagnostic_bin(255) == "B1"
    assert diagnostic_bin(2048) == "B5"


def test_at_or_above_ceiling_is_b7():
    assert diagnostic_bin(4096) == "B7"
    assert diagnostic_bin(99999) == "B7"


def test_never_raises_on_negative():
    # A malformed/zero distance must bucket, not crash a diagnostic.
    assert diagnostic_bin(0) == "B0"
    assert diagnostic_bin(-5) == "B0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_diagnostic_bin.py -q`
Expected: FAIL with `ImportError: cannot import name 'diagnostic_bin'`.

- [ ] **Step 3: Implement `diagnostic_bin`**

Append to `src/phi3geom/dataset/distance.py`:

```python
def diagnostic_bin(distance_tokens: int) -> str:
    """Tolerant post-hoc diagnostic label for the distance slice.

    Unlike ``assign_bin`` (which raises outside [128, 4096) because that is
    the v1 *generation* scope), this never raises: it adds catch-all buckets
    ``"B0"`` (below B1's floor) and ``"B7"`` (at/above B6's ceiling) so the
    distance-diagnostic report can bin every event. Constitution v2.0.0:
    bins are a diagnostic, not a gate.
    """
    if distance_tokens < 128:
        return "B0"
    if distance_tokens >= 4096:
        return "B7"
    for bin_id, (lower, upper) in BIN_RANGES.items():
        if lower <= distance_tokens < upper:
            return bin_id
    raise AssertionError(f"unreachable: distance={distance_tokens}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_diagnostic_bin.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phi3geom/dataset/distance.py tests/unit/test_diagnostic_bin.py
git commit -m "feat(distance): tolerant diagnostic_bin for post-hoc distance slices"
```

---

## Task 2: Measure true evidence distance in the pipeline

The pipeline currently leaves `evidence_distance_tokens` at the generation-time *target* (a guess) and never re-measures. Add a pure-tokenizer helper and wire it in so each event carries the **measured** distance. Unit-tested with a fake whitespace tokenizer (no GPU/model needed).

**Files:**
- Modify: `src/phi3geom/extraction/pipeline.py`
- Test: `tests/unit/test_evidence_distance_measure.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_evidence_distance_measure.py
"""measure_evidence_distance_tokens uses the tokenizer to recover the true
distance from end-of-evidence to the answer-commit position."""
from __future__ import annotations

from dataclasses import replace

from phi3geom.extraction.pipeline import measure_evidence_distance_tokens, build_prompt
from phi3geom.dataset.generation import FACTS, TEMPLATES, generate_event
from phi3geom.extraction.pipeline import PROMPT_TEMPLATE_SHA256


class WhitespaceTokenizer:
    """Minimal stand-in: HF-style FLAT input_ids, one id per word (matches
    what a real HF tokenizer returns for a single string with no return_tensors)."""

    def __call__(self, text, return_tensors=None):
        return {"input_ids": text.split()}


def _toy_event(evidence_word_idx: int):
    tmpl = TEMPLATES[0]
    fact = FACTS[tmpl.template_id][0]
    ev = generate_event(
        template=tmpl, fact=fact, target_evidence_distance_words=20,
        distractor_density=0.3, prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
        bin_id="B1", rng=__import__("random").Random(0),
    )
    return replace(ev, evidence_position_token_idx=evidence_word_idx)


def test_distance_is_full_minus_prefix_tokens():
    tok = WhitespaceTokenizer()
    ev = _toy_event(evidence_word_idx=3)
    # Full prompt word count:
    full = len(build_prompt(ev.document, ev.question).split())
    # Preamble + first 3 document words:
    from phi3geom.extraction.pipeline import PROMPT_TEMPLATE
    preamble = PROMPT_TEMPLATE.split("{document}")[0]
    prefix = len((preamble + " ".join(ev.document.split()[:3])).split())
    expected = full - prefix
    assert measure_evidence_distance_tokens(ev, tok) == expected


def test_distance_is_positive_for_early_evidence():
    tok = WhitespaceTokenizer()
    ev = _toy_event(evidence_word_idx=1)
    assert measure_evidence_distance_tokens(ev, tok) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_evidence_distance_measure.py -q`
Expected: FAIL with `ImportError: cannot import name 'measure_evidence_distance_tokens'`.

- [ ] **Step 3: Implement the helper**

Add to `src/phi3geom/extraction/pipeline.py` (after `build_prompt`):

```python
def _token_len(tokenizer: "object", text: str) -> int:
    """Token length of ``text``. Handles HF's flat ``input_ids`` list (single
    string, no return_tensors), a nested ``[[...]]`` batch, or a tensor."""
    out = tokenizer(text)["input_ids"]
    if hasattr(out, "shape"):
        return int(out.shape[-1])
    if out and isinstance(out[0], (list, tuple)):
        return len(out[0])
    return len(out)


def measure_evidence_distance_tokens(event: DocQAEvent, tokenizer: "object") -> int:
    """Measure tokens from end-of-evidence to the answer-commit position.

    ``event.evidence_position_token_idx`` is a *word* index into the document
    (set at generation). We render the prompt preamble plus the document
    truncated at end-of-evidence, tokenize it, and subtract that length from
    the full prompt's token length. The shared preamble (and any BOS) cancels,
    so the result is the true evidence->answer token distance. Approximate to
    within tokenizer boundary effects — acceptable for a diagnostic (Principle
    III, v2.0.0: bin fidelity may be low).
    """
    words = event.document.split()
    n_words = max(0, min(event.evidence_position_token_idx, len(words)))
    doc_prefix = " ".join(words[:n_words])
    preamble = PROMPT_TEMPLATE.split("{document}")[0]
    prefix_len = _token_len(tokenizer, preamble + doc_prefix)
    full_len = _token_len(tokenizer, build_prompt(event.document, event.question))
    return full_len - prefix_len
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_evidence_distance_measure.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Wire the measurement into `run_event_extraction`**

In `src/phi3geom/extraction/pipeline.py`, inside `run_event_extraction`, change the step-4 `replace(...)` call to also set the measured distance. Replace:

```python
    # 4. Update the event with model output + label.
    from dataclasses import replace
    event = replace(
        event,
        model_generation=model_generation_raw,
        model_generation_normalized=gen_norm,
        is_fail=is_fail,
    )
```

with:

```python
    # 4. Update the event with model output + label + MEASURED distance.
    from dataclasses import replace
    measured_distance = measure_evidence_distance_tokens(event, tokenizer)
    event = replace(
        event,
        model_generation=model_generation_raw,
        model_generation_normalized=gen_norm,
        is_fail=is_fail,
        evidence_distance_tokens=measured_distance,
    )
```

- [ ] **Step 6: Run the full unit suite to confirm no regression**

Run: `python -m pytest tests/unit tests/contract -q`
Expected: PASS (prior count + 6 new from Tasks 1–2).

- [ ] **Step 7: Commit**

```bash
git add src/phi3geom/extraction/pipeline.py tests/unit/test_evidence_distance_measure.py
git commit -m "feat(pipeline): record measured evidence distance on each event"
```

---

## Task 3: PooledDetectorFit dataclass

**Files:**
- Modify: `src/phi3geom/analysis/types.py`
- Test: covered by Task 4's `test_pooled_detector.py`

- [ ] **Step 1: Add the dataclass**

Append to `src/phi3geom/analysis/types.py`:

```python
@dataclass(frozen=True, slots=True)
class PooledDetectorFit:
    """The headline distance-blind detector (constitution v2.0.0, Principle III).

    Fit over all events POOLED across evidence-distance bins, using only
    attention-geometry features. Distance is never an input.
    """

    feature_names: tuple[str, ...]
    coefficients: np.ndarray  # float64, shape (n_features,)
    intercept: float
    auroc: float
    auroc_ci_lower: float
    auroc_ci_upper: float
    n_events_train: int
    n_events_held_out: int

    @property
    def beats_chance(self) -> bool:
        """Primary success criterion: 95% CI lower bound strictly above 0.5."""
        return self.auroc_ci_lower > 0.5
```

- [ ] **Step 2: Commit**

```bash
git add src/phi3geom/analysis/types.py
git commit -m "feat(analysis): add PooledDetectorFit dataclass"
```

---

## Task 4: The pooled distance-blind detector

Promotes the (previously quarantined) pooled logistic to the primary path. Mirrors `composite.fit_per_regime_composite`'s numerics (L2 logistic, stratified split, percentile bootstrap AUROC CI) but is pooled and takes no `bin_id`.

**Files:**
- Create: `src/phi3geom/analysis/pooled_detector.py`
- Test: `tests/unit/test_pooled_detector.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_pooled_detector.py
"""Pooled distance-blind detector (constitution v2.0.0, Principle III)."""
from __future__ import annotations

import numpy as np
import pytest

from phi3geom.analysis.pooled_detector import fit_pooled_detector
from phi3geom.analysis.types import PooledDetectorFit


def _separable(n=240, n_features=7, seed=0):
    rng = np.random.default_rng(seed)
    labels = np.zeros(n, dtype=bool)
    labels[::2] = True
    feats = rng.standard_normal((n, n_features)).astype(np.float64)
    feats[labels, 0] += 3.0  # feature 0 carries signal
    return feats, labels


def test_returns_pooled_detector_fit():
    feats, labels = _separable()
    fit = fit_pooled_detector(feats, labels, random_state=0, n_bootstrap=50)
    assert isinstance(fit, PooledDetectorFit)
    assert fit.coefficients.shape == (7,)
    assert fit.coefficients.dtype == np.float64


def test_recovers_signal_auroc():
    feats, labels = _separable()
    fit = fit_pooled_detector(feats, labels, random_state=0, n_bootstrap=200)
    assert fit.auroc > 0.9
    assert fit.beats_chance  # CI lower > 0.5


def test_rejects_non_float64():
    feats, labels = _separable()
    with pytest.raises(TypeError, match="float64"):
        fit_pooled_detector(feats.astype(np.float32), labels, random_state=0)


def test_takes_no_bin_id():
    # Distance-blind by construction: passing bin_id is a TypeError.
    feats, labels = _separable()
    with pytest.raises(TypeError):
        fit_pooled_detector(feats, labels, bin_id="B1", random_state=0)  # type: ignore[call-arg]


def test_imputes_nan_ricci_column():
    feats, labels = _separable()
    feats[:5, 6] = np.nan  # Ricci column may carry NaN on the baseline path
    fit = fit_pooled_detector(feats, labels, random_state=0, n_bootstrap=50)
    assert np.isfinite(fit.auroc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_pooled_detector.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'phi3geom.analysis.pooled_detector'`.

- [ ] **Step 3: Implement the detector**

Create `src/phi3geom/analysis/pooled_detector.py`:

```python
"""The headline pooled, distance-blind failure detector.

Constitution v2.0.0, Principle III: the PRIMARY analysis is a single
classifier fit over all events POOLED across evidence-distance bins, fed
ONLY attention-geometry features and BLIND to evidence distance. This module
intentionally takes no ``bin_id`` parameter — distance cannot enter the model.

The per-bin ``composite`` module is the SECONDARY diagnostic and lives apart.
"""

from __future__ import annotations

import numpy as np

from phi3geom.analysis.types import PooledDetectorFit

DEFAULT_N_BOOTSTRAP = 1000


def fit_pooled_detector(
    features: np.ndarray,
    labels: np.ndarray,
    *,
    feature_names: tuple[str, ...] | None = None,
    l2_penalty: float = 1.0,
    random_state: int,
    held_out_fraction: float = 0.2,
    n_bootstrap: int = DEFAULT_N_BOOTSTRAP,
) -> PooledDetectorFit:
    """Fit an L2-regularized logistic on events POOLED across all bins.

    Args:
        features: ``(n_events, n_features)`` float64. Geometry features only.
        labels: ``(n_events,)`` bool (True = failure).
        feature_names: Names for reporting (default ``f_0..f_{n-1}``).
        l2_penalty: L2 strength; ``C = 1/l2_penalty``.
        random_state: From ``seed_for_analysis("pooled_detector")``.
        held_out_fraction: Test split (default 0.2).
        n_bootstrap: Percentile-bootstrap resamples for the AUROC CI.
    """
    if features.ndim != 2:
        raise ValueError(f"features must be 2D; got shape {features.shape}")
    if features.dtype != np.float64:
        raise TypeError(
            f"features must be float64 (Principle IV); got {features.dtype}"
        )
    if labels.ndim != 1 or labels.shape[0] != features.shape[0]:
        raise ValueError(
            f"labels shape mismatch: {features.shape[0]} events vs {labels.shape}"
        )

    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split

    n_features = features.shape[1]
    if feature_names is None:
        feature_names = tuple(f"f_{i}" for i in range(n_features))

    # Median-impute NaN columns (Ricci column may be NaN on the baseline path).
    arr = features.copy()
    for col in range(n_features):
        column = arr[:, col]
        nan_mask = np.isnan(column)
        if nan_mask.any():
            median = float(np.nanmedian(column))
            column[nan_mask] = median if np.isfinite(median) else 0.0

    x_train, x_test, y_train, y_test = train_test_split(
        arr, labels.astype(int),
        test_size=held_out_fraction, random_state=random_state, stratify=labels,
    )
    model = LogisticRegression(
        C=1.0 / l2_penalty, solver="lbfgs", max_iter=1000, random_state=random_state,
    )
    model.fit(x_train, y_train)
    y_scores = model.predict_proba(x_test)[:, 1]
    auroc = float(roc_auc_score(y_test, y_scores))

    rng = np.random.default_rng(random_state)
    aurocs: list[float] = []
    n = len(y_test)
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        ys = y_test[idx]
        if len(np.unique(ys)) < 2:
            continue
        aurocs.append(float(roc_auc_score(ys, y_scores[idx])))
    aurocs.sort()
    lo = aurocs[int(0.025 * len(aurocs))] if aurocs else float("nan")
    hi = aurocs[int(0.975 * len(aurocs)) - 1] if aurocs else float("nan")

    return PooledDetectorFit(
        feature_names=feature_names,
        coefficients=model.coef_.ravel().astype(np.float64),
        intercept=float(model.intercept_[0]),
        auroc=auroc,
        auroc_ci_lower=lo,
        auroc_ci_upper=hi,
        n_events_train=len(x_train),
        n_events_held_out=len(x_test),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_pooled_detector.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phi3geom/analysis/pooled_detector.py tests/unit/test_pooled_detector.py
git commit -m "feat(analysis): pooled distance-blind detector (Principle III, v2.0.0)"
```

---

## Task 5: Add the Principle III v2.0.0 guard (no deletions)

Under v2.0.0 the pooled detector is primary and the per-bin `composite` is the diagnostic. The existing segregation test still passes as-is (composite still rejects pooling; the legacy `pooled_negative_control` module is untouched and still imported by the out-of-scope full-study scripts), so we don't gut it — we update its docstring and ADD a guard that the new primary, `pooled_detector`, is distance-blind and lives in its own module. Retiring `pooled_negative_control` is deferred (see "Out of scope for this plan").

**Files:**
- Modify: `tests/unit/test_principle_iii_segregation.py`

- [ ] **Step 1: Update the module docstring**

Replace the opening docstring of `tests/unit/test_principle_iii_segregation.py` (the lines from `"""Constitution Principle III segregation test.` through its closing `"""`) with:

```python
"""Constitution v2.0.0 architecture guard (Principle III).

The PRIMARY analysis is now the pooled, distance-blind detector
(``analysis.pooled_detector``); the per-bin composite (``analysis.composite``)
is a SECONDARY diagnostic. These tests guard that the per-bin composite still
refuses to be pooled (bin_id required) and that the pooled primary takes no
bin_id and lives in its own module. The legacy SC-003 ``pooled_negative_control``
checks below are retained until that module is retired in the full-study
reconciliation (out of this feature's scope).
"""
```

- [ ] **Step 2: Append the v2.0.0 primary-detector guard**

Append to the end of `tests/unit/test_principle_iii_segregation.py`:

```python
def test_pooled_detector_is_distance_blind_primary() -> None:
    """v2.0.0: the PRIMARY detector is pooled + distance-blind, in its own module."""
    from phi3geom.analysis import composite, pooled_detector
    from phi3geom.analysis.pooled_detector import fit_pooled_detector
    from phi3geom.analysis.types import PooledDetectorFit

    feats, labels = _well_shaped_features()
    # Distance cannot enter the primary model: bin_id is not a parameter.
    with pytest.raises(TypeError):
        fit_pooled_detector(feats, labels, bin_id="B1", random_state=0)  # type: ignore[call-arg]
    out = fit_pooled_detector(feats, labels, random_state=0, n_bootstrap=50)
    assert isinstance(out, PooledDetectorFit)
    # Primary (pooled) and diagnostic (per-bin) live in separate modules.
    assert composite.__file__ != pooled_detector.__file__
```

(`_well_shaped_features` and `pytest` are already defined/imported in this file.)

- [ ] **Step 3: Run the guard**

Run: `python -m pytest tests/unit/test_principle_iii_segregation.py -q`
Expected: PASS (all existing tests + 1 new).

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_principle_iii_segregation.py
git commit -m "test(analysis): guard pooled_detector as the v2.0.0 distance-blind primary"
```

---

## Task 6: Report writers — pooled AUROC, distance diagnostic, confound audit

**Files:**
- Modify: `src/phi3geom/reporting/pilot_reports.py`
- Test: `tests/unit/test_pilot_reports_pooled.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_pilot_reports_pooled.py
from __future__ import annotations

import json

import numpy as np

from phi3geom.analysis.pooled_detector import fit_pooled_detector
from phi3geom.reporting.pilot_reports import (
    write_pooled_auroc,
    write_distance_diagnostic,
    write_confound_audit,
)


def _data(n=240, seed=0):
    rng = np.random.default_rng(seed)
    labels = np.zeros(n, dtype=bool); labels[::2] = True
    feats = rng.standard_normal((n, 7)).astype(np.float64)
    feats[labels, 0] += 3.0
    distances = rng.integers(20, 3000, size=n)
    doc_lengths = rng.integers(100, 2000, size=n)
    return feats, labels, distances, doc_lengths


def test_pooled_auroc_report(tmp_path):
    feats, labels, *_ = _data()
    fit = fit_pooled_detector(feats, labels, random_state=0, n_bootstrap=100)
    p = write_pooled_auroc(fit, out_dir=tmp_path)
    payload = json.loads(p.read_text())
    assert payload["auroc"] == fit.auroc
    assert payload["beats_chance"] is fit.beats_chance
    assert "auroc_ci_lower" in payload


def test_distance_diagnostic_report(tmp_path):
    feats, labels, distances, _ = _data()
    fit = fit_pooled_detector(feats, labels, random_state=0, n_bootstrap=50)
    p = write_distance_diagnostic(
        coefficients=fit.coefficients, intercept=fit.intercept,
        feature_matrix=feats, distances=distances, labels=labels, out_dir=tmp_path,
    )
    payload = json.loads(p.read_text())
    # keys are diagnostic bin labels; each carries an auroc + n
    assert all("auroc" in v and "n" in v for v in payload.values())


def test_confound_audit_report(tmp_path):
    feats, labels, distances, doc_lengths = _data()
    fit = fit_pooled_detector(feats, labels, random_state=0, n_bootstrap=50)
    p = write_confound_audit(
        geometry_auroc=fit.auroc, labels=labels,
        doc_lengths=doc_lengths, distances=distances,
        random_state=0, out_dir=tmp_path,
    )
    payload = json.loads(p.read_text())
    assert "geometry_auroc" in payload
    assert "confound_only_auroc" in payload
    assert isinstance(payload["is_suspicious"], bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_pilot_reports_pooled.py -q`
Expected: FAIL with `ImportError: cannot import name 'write_pooled_auroc'`.

- [ ] **Step 3: Implement the three writers**

Add to `src/phi3geom/reporting/pilot_reports.py` (and import `numpy as np`, `PooledDetectorFit`, `diagnostic_bin` at the top):

```python
import numpy as np
from phi3geom.analysis.types import PooledDetectorFit
from phi3geom.dataset.distance import diagnostic_bin


def _impute_and_score(coefficients, intercept, feature_matrix):
    arr = feature_matrix.astype(np.float64).copy()
    for col in range(arr.shape[1]):
        m = np.isnan(arr[:, col])
        if m.any():
            med = float(np.nanmedian(arr[:, col]))
            arr[m, col] = med if np.isfinite(med) else 0.0
    z = arr @ np.asarray(coefficients, dtype=np.float64) + float(intercept)
    return 1.0 / (1.0 + np.exp(-z))


def write_pooled_auroc(
    fit: PooledDetectorFit, *, out_dir: Path = REPORTS_PILOT_DIR
) -> Path:
    """Headline result: the pooled distance-blind detector's AUROC + CI."""
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "auroc": fit.auroc,
        "auroc_ci_lower": fit.auroc_ci_lower,
        "auroc_ci_upper": fit.auroc_ci_upper,
        "beats_chance": bool(fit.beats_chance),
        "n_events_train": fit.n_events_train,
        "n_events_held_out": fit.n_events_held_out,
    }
    path = out_dir / "pooled_auroc.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return path


def write_distance_diagnostic(
    *, coefficients, intercept, feature_matrix, distances, labels,
    out_dir: Path = REPORTS_PILOT_DIR,
) -> Path:
    """SECONDARY diagnostic: pooled detector AUROC sliced by measured distance.

    Diagnostic only (Principle III) — never the headline. Scores all events
    with the fitted coefficients and reports per-diagnostic-bin AUROC.
    """
    from sklearn.metrics import roc_auc_score

    out_dir.mkdir(parents=True, exist_ok=True)
    scores = _impute_and_score(coefficients, intercept, feature_matrix)
    labels = np.asarray(labels).astype(int)
    bins = np.array([diagnostic_bin(int(d)) for d in distances])
    payload: dict[str, dict[str, object]] = {}
    for b in sorted(set(bins)):
        mask = bins == b
        y, s = labels[mask], scores[mask]
        auroc = float(roc_auc_score(y, s)) if len(np.unique(y)) == 2 else None
        payload[b] = {"auroc": auroc, "n": int(mask.sum())}
    path = out_dir / "distance_diagnostic.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return path


def write_confound_audit(
    *, geometry_auroc, labels, doc_lengths, distances, random_state,
    out_dir: Path = REPORTS_PILOT_DIR,
) -> Path:
    """Robustness check (not a filter): can document length + distance ALONE
    separate fail from control? If a length/position-only logistic matches the
    geometry detector, the 'signal' may be a confound proxy. CEM already
    balances template/density/answer-length, so we audit the unmatched ones.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split

    out_dir.mkdir(parents=True, exist_ok=True)
    x = np.column_stack([np.asarray(doc_lengths), np.asarray(distances)]).astype(np.float64)
    y = np.asarray(labels).astype(int)
    x_tr, x_te, y_tr, y_te = train_test_split(
        x, y, test_size=0.2, random_state=random_state, stratify=y
    )
    m = LogisticRegression(max_iter=1000, random_state=random_state).fit(x_tr, y_tr)
    confound_auroc = float(roc_auc_score(y_te, m.predict_proba(x_te)[:, 1]))
    payload = {
        "geometry_auroc": float(geometry_auroc),
        "confound_only_auroc": confound_auroc,
        "is_suspicious": bool(confound_auroc >= float(geometry_auroc) - 0.05),
    }
    path = out_dir / "confound_audit.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return path
```

- [ ] **Step 4: Repoint `write_pilot_summary`**

Replace `write_pilot_summary` in `src/phi3geom/reporting/pilot_reports.py` with the pooled version:

```python
def write_pilot_summary(
    *,
    detector_fit: PooledDetectorFit,
    feature_matrix,
    labels,
    distances,
    doc_lengths,
    strata_by_bin: dict[BinId, list[CEMStratum]],
    wall_time_sec: float,
    gpu_hours_estimate: float,
    n_events: int,
    matched_events: list[DocQAEvent],
    random_state: int,
    out_dir: Path = REPORTS_PILOT_DIR,
) -> dict[str, Path]:
    """Write all pilot reports: pooled headline + diagnostics + ops."""
    return {
        "pooled_auroc": write_pooled_auroc(detector_fit, out_dir=out_dir),
        "distance_diagnostic": write_distance_diagnostic(
            coefficients=detector_fit.coefficients, intercept=detector_fit.intercept,
            feature_matrix=feature_matrix, distances=distances, labels=labels,
            out_dir=out_dir,
        ),
        "confound_audit": write_confound_audit(
            geometry_auroc=detector_fit.auroc, labels=labels,
            doc_lengths=doc_lengths, distances=distances,
            random_state=random_state, out_dir=out_dir,
        ),
        "cem_yield": write_cem_yield(strata_by_bin, out_dir=out_dir),
        "runtime": write_runtime(
            wall_time_sec=wall_time_sec, gpu_hours_estimate=gpu_hours_estimate,
            n_events=n_events, out_dir=out_dir,
        ),
        "handcheck_sample": write_handcheck_sample(matched_events, out_dir=out_dir),
    }
```

Keep `write_per_bin_auroc` and the `PerRegimeCompositeFit` import as-is — `write_per_bin_auroc` is still imported by the out-of-scope full-study driver (`full_study_main.py`) and now serves as the per-bin *diagnostic* writer. Only `write_pilot_summary` changes signature here.

- [ ] **Step 5: Run report tests**

Run: `python -m pytest tests/unit/test_pilot_reports_pooled.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add src/phi3geom/reporting/pilot_reports.py tests/unit/test_pilot_reports_pooled.py
git commit -m "feat(reporting): pooled AUROC headline + distance-diagnostic + confound audit"
```

---

## Task 7: Re-point the pilot driver to one pooled fit

`pilot_main.py` already produces a balanced, CEM-matched `matched_events` list spanning the generation bins. Pool it into one distance-blind fit and write the new reports.

**Files:**
- Modify: `src/phi3geom/scripts/pilot_main.py`

- [ ] **Step 1: Swap imports**

In `src/phi3geom/scripts/pilot_main.py`, replace:

```python
from phi3geom.analysis.composite import (
    InsufficientDataError,
    fit_per_regime_composite,
)
from phi3geom.analysis.types import PerRegimeCompositeFit
```

with:

```python
from phi3geom.analysis.pooled_detector import fit_pooled_detector
```

- [ ] **Step 2: Replace the per-bin fit loop (step 6 in `main`)**

Replace the entire `# 6. Build feature matrix + fit per-regime composite per bin.` block (the `fits: dict[...] = {}` loop) with:

```python
    # 6. Pool ALL matched events into one distance-blind fit (Principle III,
    #    constitution v2.0.0). The detector never sees the bin or distance.
    import numpy as np
    features, labels = _build_feature_matrix(
        matched_events, cache_root=args.cache_root,
        expected_manifest_sha256=placeholder_sha,
    )
    distances = np.array([e.evidence_distance_tokens for e in matched_events])
    doc_lengths = np.array([len(e.document.split()) for e in matched_events])
    detector_fit = fit_pooled_detector(
        features, labels,
        feature_names=FEATURE_NAMES,
        random_state=seed_for_analysis("pooled_detector"),
    )
    print(
        f"[pilot] POOLED AUROC = {detector_fit.auroc:.3f} "
        f"(95% CI [{detector_fit.auroc_ci_lower:.3f}, "
        f"{detector_fit.auroc_ci_upper:.3f}]) "
        f"beats_chance={detector_fit.beats_chance} "
        f"on {len(matched_events)} pooled events"
    )
```

- [ ] **Step 3: Replace the report call (step 8 in `main`)**

Replace the `paths = write_pilot_summary(...)` call with:

```python
    paths = write_pilot_summary(
        detector_fit=detector_fit,
        feature_matrix=features,
        labels=labels,
        distances=distances,
        doc_lengths=doc_lengths,
        strata_by_bin=strata_by_bin,
        wall_time_sec=elapsed,
        gpu_hours_estimate=elapsed / 3600.0,
        n_events=len(matched_events),
        matched_events=matched_events,
        random_state=seed_for_analysis("confound_audit"),
        out_dir=args.reports_dir,
    )
```

- [ ] **Step 4: Update the module docstring**

Change the line `fits the per-regime composite logistic per bin, writes the 4 pilot reports.` to `fits ONE pooled distance-blind detector over all matched events (Principle III, v2.0.0), writes the pilot reports (pooled AUROC headline + distance/confound diagnostics + ops).`

- [ ] **Step 5: Byte-compile to catch syntax/name errors**

Run: `python -m py_compile src/phi3geom/scripts/pilot_main.py`
Expected: no output (success).

- [ ] **Step 6: Commit**

```bash
git add src/phi3geom/scripts/pilot_main.py
git commit -m "feat(pilot): fit one pooled distance-blind detector over matched events"
```

---

## Task 8: Update the GPU integration test for the new report API

**Files:**
- Modify: `tests/integration/test_pilot_pipeline.py`

- [ ] **Step 1: Rewrite `test_pilot_reports_writeable`**

Replace its body (the `fits = {...}` / `write_pilot_summary(...)` section) with a pooled-fit smoke test:

```python
def test_pilot_reports_writeable(tmp_path):
    """Report writers run end-to-end on a synthetic pooled fit (no GPU)."""
    import numpy as np
    from phi3geom.analysis.pooled_detector import fit_pooled_detector
    from phi3geom.dataset.types import CEMStratum
    from phi3geom.reporting.pilot_reports import write_pilot_summary

    rng = random.Random(0)
    events = [_toy_event(b, rng) for b in BIN_IDS]
    from dataclasses import replace
    events = [replace(e, model_generation="x", is_fail=(i % 2 == 0),
                      evidence_distance_tokens=200 + 100 * i)
              for i, e in enumerate(events)]

    n = 240
    gen = np.random.default_rng(0)
    labels = np.zeros(n, dtype=bool); labels[::2] = True
    feats = gen.standard_normal((n, 7)).astype(np.float64); feats[labels, 0] += 3.0
    distances = gen.integers(20, 3000, size=n)
    doc_lengths = gen.integers(100, 2000, size=n)
    fit = fit_pooled_detector(feats, labels, random_state=0, n_bootstrap=50)

    strata_by_bin = {b: [CEMStratum(b, "birthplace", "low", "1", 60, 60, 50)] for b in BIN_IDS}
    paths = write_pilot_summary(
        detector_fit=fit, feature_matrix=feats, labels=labels,
        distances=distances, doc_lengths=doc_lengths,
        strata_by_bin=strata_by_bin, wall_time_sec=3600.0 * 8,
        gpu_hours_estimate=8.0, n_events=n, matched_events=events,
        random_state=0, out_dir=tmp_path,
    )
    for name, p in paths.items():
        assert p.is_file(), f"{name} not written"
    headline = json.loads((tmp_path / "pooled_auroc.json").read_text())
    assert headline["auroc"] == fit.auroc
```

- [ ] **Step 2: Add a measured-distance assertion to the end-to-end test**

In `test_pilot_pipeline_end_to_end`, after the existing per-event assertions, add inside the loop:

```python
        assert isinstance(result.event.evidence_distance_tokens, int)
        assert result.event.evidence_distance_tokens > 0
```

- [ ] **Step 3: Run the non-GPU half**

Run: `python -m pytest tests/integration/test_pilot_pipeline.py::test_pilot_reports_writeable -q`
Expected: PASS (the GPU test stays skipped without `PHI3_RUN_GPU_TESTS=1`).

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_pilot_pipeline.py
git commit -m "test(pilot): pooled-fit report smoke test + measured-distance assertion"
```

---

## Task 9: Annotate specs/001 so it points at the v2.0.0 design

The speckit spec/tasks still describe per-regime methodology. Annotate (don't rewrite) so `/speckit-analyze` and future readers see the governing design.

**Files:**
- Modify: `specs/001-phi3-attention-geometry-v1/spec.md`, `specs/001-phi3-attention-geometry-v1/tasks.md`

- [ ] **Step 1: Add a banner to the top of `spec.md` (just under the title)**

```markdown
> **SUPERSEDED IN PART (2026-05-28, constitution v2.0.0):** The primary analysis
> is now a single POOLED, distance-blind detector; per-regime/per-bin analysis is
> a secondary diagnostic. See
> `docs/superpowers/specs/2026-05-28-distance-blind-failure-detector-design.md`.
> Sections describing per-regime composites as the headline are retained for
> history but are no longer the primary methodology.
```

- [ ] **Step 2: Add the same banner to the top of `tasks.md`.**

- [ ] **Step 3: Commit**

```bash
git add specs/001-phi3-attention-geometry-v1/spec.md specs/001-phi3-attention-geometry-v1/tasks.md
git commit -m "docs(spec): annotate 001 as partly superseded by v2.0.0 distance-blind design"
```

---

## Final verification

- [ ] **Run the full CPU suite**

Run: `python -m pytest tests/unit tests/contract -q`
Expected: PASS. New tests from Tasks 1, 2, 4, 5, 6 present; deleted negative-control test gone.

- [ ] **Confirm the GPU validation path is ready (on a RunPod box)**

Run: `PHI3_RUN_GPU_TESTS=1 python -m pytest tests/integration/test_pilot_pipeline.py -q`
Expected: 2 passed. Then `bash scripts/run_pilot.sh` writes `reports/pilot/pooled_auroc.json` (headline), `distance_diagnostic.json`, `confound_audit.json`, `cem_yield.json`, `runtime.json`, `handcheck_sample.jsonl`.
