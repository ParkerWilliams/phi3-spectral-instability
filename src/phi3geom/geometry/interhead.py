"""Inter-head attention-configuration primitives (SP-0, §5.6).

The per-cell summary `S(t, ℓ)` of the inter-head attention-drift family: given the
`H` heads' attention distributions over the `T` source tokens at one (query token,
layer) cell, summarize their *configuration* two complementary ways — a transport
view (pairwise Jensen–Shannon / Hellinger dispersion) and a spectral view (the
head-head overlap matrix's effective rank / Fiedler value / top eigenvalue) — plus a
with-context evidence-coverage scalar.

All computation is float64 at the spectral seam (Constitution IV); the in-pass
capture downcasts the stored surface at the cache boundary. Verified by analytic
property tests (identical heads ⇒ dispersion 0 / rank-1 overlap; disjoint-support
heads ⇒ max dispersion / identity overlap). Design:
docs/superpowers/specs/2026-06-18-interhead-attention-drift-family-design.md.
"""

from __future__ import annotations

import numpy as np

_EPS = 1e-12


def _check(attn: np.ndarray) -> np.ndarray:
    if not isinstance(attn, np.ndarray):
        raise TypeError(f"attn must be a numpy array; got {type(attn).__name__}")
    if attn.dtype != np.float64:
        raise TypeError(
            f"attn must be float64 (Constitution IV); got {attn.dtype}"
        )
    if attn.ndim != 2:
        raise ValueError(f"attn must be 2D (H, T); got shape {attn.shape}")
    # Defensive renormalization (rows are post-softmax distributions).
    row = attn.sum(axis=1, keepdims=True)
    row = np.where(row > _EPS, row, 1.0)
    return attn / row


def _kl_bits(p: np.ndarray, q: np.ndarray) -> float:
    mask = p > _EPS
    return float(np.sum(p[mask] * np.log2(p[mask] / q[mask])))


def js_distance(p: np.ndarray, q: np.ndarray) -> float:
    """Jensen–Shannon distance (√JSD, base-2) between two distributions, in [0, 1]."""
    m = 0.5 * (p + q)
    jsd = 0.5 * _kl_bits(p, m) + 0.5 * _kl_bits(q, m)
    return float(np.sqrt(max(0.0, jsd)))


def hellinger_distance(p: np.ndarray, q: np.ndarray) -> float:
    """Hellinger distance between two distributions, in [0, 1]."""
    return float(np.sqrt(max(0.0, 1.0 - float(np.sum(np.sqrt(p * q))))))


def pairwise_dispersion(attn: np.ndarray, *, metric: str = "js") -> float:
    """Mean pairwise distance between the `H` heads' attention distributions.

    ``metric="js"`` (Jensen–Shannon distance) or ``"hellinger"``. 0 for ``H < 2``.
    """
    a = _check(attn)
    h = a.shape[0]
    if h < 2:
        return 0.0
    dist = js_distance if metric == "js" else hellinger_distance
    total = 0.0
    n_pairs = 0
    for i in range(h):
        for j in range(i + 1, h):
            total += dist(a[i], a[j])
            n_pairs += 1
    return total / n_pairs


def overlap_matrix(attn: np.ndarray) -> np.ndarray:
    """`H×H` head-head similarity ``M_{ij} = 1 − JS_distance(A_i, A_j)`` (float64)."""
    a = _check(attn)
    h = a.shape[0]
    m = np.ones((h, h), dtype=np.float64)
    for i in range(h):
        for j in range(i + 1, h):
            s = 1.0 - js_distance(a[i], a[j])
            m[i, j] = m[j, i] = s
    return m


def effective_rank(m: np.ndarray) -> float:
    """Effective rank (Roy–Vetterli) of a matrix from its singular-value entropy."""
    s = np.linalg.svd(m, compute_uv=False)
    s = s[s > _EPS]
    if s.size == 0:
        return 0.0
    p = s / s.sum()
    return float(np.exp(-np.sum(p * np.log(p))))


def fiedler_value(m: np.ndarray) -> float:
    """Algebraic connectivity (2nd-smallest Laplacian eigenvalue) of the similarity
    graph with edge weights ``max(M, 0)`` and zero diagonal. 0 for ``H < 2``."""
    h = m.shape[0]
    if h < 2:
        return 0.0
    w = np.clip(m.copy(), 0.0, None)
    np.fill_diagonal(w, 0.0)
    lap = np.diag(w.sum(axis=1)) - w
    ev = np.linalg.eigvalsh(lap)
    return float(ev[1])


def top_eigenvalue(m: np.ndarray) -> float:
    """Largest eigenvalue of the (symmetric) overlap matrix."""
    return float(np.linalg.eigvalsh(m)[-1])


def evidence_coverage(attn: np.ndarray, span: tuple[int, int]) -> float:
    """Mean over heads of attention mass on the gold span ``[start, end]`` inclusive.

    With-context diagnostic only; raises if the span is out of range.
    """
    a = _check(attn)
    start, end = span
    if not (0 <= start <= end < a.shape[1]):
        raise ValueError(f"span {span} out of range for T={a.shape[1]}")
    return float(a[:, start : end + 1].sum(axis=1).mean())


# Canonical order of the corpus-agnostic per-cell scalars.
CELL_FEATURES: tuple[str, ...] = (
    "dispersion_js",
    "dispersion_hellinger",
    "effective_rank",
    "fiedler",
    "top_eigenvalue",
)


def cell_summary(
    attn: np.ndarray, *, evidence_span: tuple[int, int] | None = None
) -> dict[str, float]:
    """The full per-cell `S(t, ℓ)` summary (one cell of the drift surface).

    Returns the corpus-agnostic scalars in ``CELL_FEATURES`` order, plus
    ``evidence_coverage`` when a span is supplied (with-context).
    """
    a = _check(attn)
    m = overlap_matrix(a)
    out = {
        "dispersion_js": pairwise_dispersion(a, metric="js"),
        "dispersion_hellinger": pairwise_dispersion(a, metric="hellinger"),
        "effective_rank": effective_rank(m),
        "fiedler": fiedler_value(m),
        "top_eigenvalue": top_eigenvalue(m),
    }
    if evidence_span is not None:
        out["evidence_coverage"] = evidence_coverage(a, evidence_span)
    return out
