"""Constitution Principle III segregation test.

Verifies that the per-regime composite API CANNOT be tricked into fitting on
cross-bin pooled data, and that the pooled negative control lives in a
separate module that is NOT re-exported through ``composite``.

These tests guard the architectural rule at the type-system + import-system
level. They MUST pass at the T029 skeleton stage and continue passing through
T044 (composite impl) and T069 (pooled impl).
"""

from __future__ import annotations

import importlib

import numpy as np
import pytest

from phi3geom.analysis import composite
from phi3geom.analysis.composite import fit_per_regime_composite
from phi3geom.analysis.types import PerRegimeCompositeFit


# ---------------------------------------------------------------------------
# Import-level segregation
# ---------------------------------------------------------------------------

def test_composite_module_does_not_re_export_pooled_fit() -> None:
    """``pooled_negative_control.fit`` is NOT accessible through ``composite``."""
    assert not hasattr(composite, "pooled_negative_control")
    # The module should not have a bare ``fit`` symbol either; the public
    # entrypoint is ``fit_per_regime_composite``.
    public_names = {n for n in dir(composite) if not n.startswith("_")}
    assert "pooled_negative_control" not in public_names
    assert "fit" not in public_names


def test_composite_module_does_not_import_pooled_internally() -> None:
    """Source-level inspection: composite.py does not import pooled_negative_control."""
    composite_source = importlib.import_module("phi3geom.analysis.composite")
    source_file = composite_source.__file__
    assert source_file is not None
    with open(source_file) as f:
        content = f.read()
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("from phi3geom.analysis.pooled_negative_control") or (
            stripped.startswith("import phi3geom.analysis.pooled_negative_control")
        ):
            raise AssertionError(
                f"composite imports pooled_negative_control: {stripped!r}"
            )


def test_pooled_module_does_not_import_composite_internally() -> None:
    """Source-level inspection: pooled_negative_control.py does not import composite."""
    pooled = importlib.import_module("phi3geom.analysis.pooled_negative_control")
    source_file = pooled.__file__
    assert source_file is not None
    with open(source_file) as f:
        content = f.read()
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("from phi3geom.analysis.composite") or (
            stripped.startswith("import phi3geom.analysis.composite")
        ):
            raise AssertionError(
                f"pooled_negative_control imports composite: {stripped!r}"
            )


# ---------------------------------------------------------------------------
# bin_id invariant at the function boundary
# ---------------------------------------------------------------------------

def _well_shaped_features(
    n: int = 200, n_features: int = 7, seed: int = 0
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    features = rng.standard_normal((n, n_features), dtype=np.float64)
    labels = rng.integers(0, 2, size=n).astype(bool)
    return features, labels


def test_fit_rejects_bin_id_none() -> None:
    features, labels = _well_shaped_features()
    with pytest.raises(ValueError, match="bin_id"):
        fit_per_regime_composite(
            features, labels, bin_id=None, random_state=42  # type: ignore[arg-type]
        )


def test_fit_rejects_bin_id_all() -> None:
    features, labels = _well_shaped_features()
    with pytest.raises(ValueError, match="ALL"):
        fit_per_regime_composite(
            features, labels, bin_id="ALL", random_state=42  # type: ignore[arg-type]
        )


def test_fit_rejects_unknown_bin_id() -> None:
    features, labels = _well_shaped_features()
    with pytest.raises(ValueError, match="bin_id"):
        fit_per_regime_composite(
            features, labels, bin_id="B7", random_state=42  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("bin_id", ["B1", "B2", "B3", "B4", "B5", "B6"])
def test_fit_accepts_each_valid_bin_id(bin_id: str) -> None:
    """All 6 valid bin_ids fit successfully (post-T044)."""
    features, labels = _well_shaped_features()
    result = fit_per_regime_composite(
        features, labels, bin_id=bin_id, random_state=42, n_bootstrap=50  # type: ignore[arg-type]
    )
    assert isinstance(result, PerRegimeCompositeFit)
    assert result.bin_id == bin_id


# ---------------------------------------------------------------------------
# Pooled module is importable only from its own path
# ---------------------------------------------------------------------------

def test_pooled_fit_importable_from_own_module() -> None:
    from phi3geom.analysis.pooled_negative_control import fit as pooled_fit
    assert callable(pooled_fit)


def test_pooled_fit_runs_post_t069() -> None:
    """At T069 (US4), pooled fit is implemented. Returns a PooledNegativeControl."""
    from phi3geom.analysis.pooled_negative_control import fit as pooled_fit
    from phi3geom.analysis.types import PooledNegativeControl

    features = np.random.default_rng(0).standard_normal((200, 7))
    labels = np.zeros(200, dtype=bool)
    labels[::2] = True
    result = pooled_fit(features, labels, random_state=0, n_bootstrap=50)
    assert isinstance(result, PooledNegativeControl)
