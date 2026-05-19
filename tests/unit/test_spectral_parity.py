"""1e-7 float64 parity tests vs the DCSBM reference implementation.

Constitution Principle IV mandates ``max_abs_diff ≤ 1e-7`` on 100 seeded
random float64 inputs.

This test file requires the ``dcsbm-transformer`` package (a dev dep pinned
in pyproject.toml to commit c06a4f8). If it's not installed (e.g., on a
machine without git+ pip extras), the tests are skipped with a clear
message — the CI / GPU-box workflow MUST install the dev extra and run
these tests before any geometry-dependent work proceeds.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from phi3geom.geometry.spectral import (
    spectral_entropy,
    stable_rank,
    top_k_grassmannian,
)

# Skip the entire module if the DCSBM reference is unavailable.
dcsbm_ref = pytest.importorskip(
    "dcsbm_transformer.spectral",
    reason="DCSBM reference not installed. Install with `pip install -e '.[dev]'`.",
)


pytestmark = pytest.mark.parity


PARITY_TOL = 1e-7
N_PARITY_EXAMPLES = 100


# Hypothesis strategy: 96x96 float64 matrices with finite values bounded away
# from extreme magnitudes (the SVD becomes numerically fragile at >1e15).
def _float64_matrices(n: int = 96, lo: float = -10.0, hi: float = 10.0):
    return arrays(
        dtype=np.float64,
        shape=(n, n),
        elements=st.floats(
            min_value=lo,
            max_value=hi,
            allow_nan=False,
            allow_infinity=False,
            width=64,
        ),
    )


@settings(
    max_examples=N_PARITY_EXAMPLES,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(m=_float64_matrices())
def test_stable_rank_parity_vs_dcsbm(m: np.ndarray) -> None:
    ours = stable_rank(m)
    theirs = float(dcsbm_ref.stable_rank(m))
    assert abs(ours - theirs) <= PARITY_TOL, (
        f"stable_rank diverged: ours={ours}, dcsbm={theirs}, "
        f"|diff|={abs(ours - theirs)}"
    )


@settings(
    max_examples=N_PARITY_EXAMPLES,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(m=_float64_matrices())
def test_spectral_entropy_parity_vs_dcsbm(m: np.ndarray) -> None:
    ours = spectral_entropy(m)
    theirs = float(dcsbm_ref.spectral_entropy(m))
    assert abs(ours - theirs) <= PARITY_TOL, (
        f"spectral_entropy diverged: ours={ours}, dcsbm={theirs}, "
        f"|diff|={abs(ours - theirs)}"
    )


@settings(
    max_examples=N_PARITY_EXAMPLES,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(m=_float64_matrices())
def test_top_k_grassmannian_parity_vs_dcsbm(m: np.ndarray) -> None:
    """Identity-aligned Grassmannian (per-atomic-unit call site) parity."""
    k = 8
    ours = top_k_grassmannian(m, k=k)
    theirs = float(dcsbm_ref.top_k_grassmannian(m, k=k))
    assert abs(ours - theirs) <= PARITY_TOL, (
        f"top_k_grassmannian diverged: ours={ours}, dcsbm={theirs}, "
        f"|diff|={abs(ours - theirs)}"
    )


@settings(
    max_examples=N_PARITY_EXAMPLES,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(m1=_float64_matrices(), m2=_float64_matrices())
def test_top_k_grassmannian_pairwise_parity_vs_dcsbm(
    m1: np.ndarray, m2: np.ndarray
) -> None:
    """Crossbar-call-site (paired) Grassmannian parity."""
    k = 8
    ours = top_k_grassmannian(m1, k=k, reference=m2)
    theirs = float(dcsbm_ref.top_k_grassmannian(m1, k=k, reference=m2))
    assert abs(ours - theirs) <= PARITY_TOL, (
        f"top_k_grassmannian (paired) diverged: ours={ours}, dcsbm={theirs}"
    )
