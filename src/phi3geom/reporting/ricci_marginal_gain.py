"""Ricci marginal-gain report (T052).

Given the spectral-only per-bin AUROC report from a US1 pilot and the
Ricci-augmented per-bin AUROC report from a US2 pilot, compute per-bin
marginal gain (Ricci AUROC - Spectral AUROC) with 95% CI on the difference
via the union-of-bootstrap-resamples heuristic.

Output: ``reports/pilot/ricci_marginal_gain.json`` with the per-bin
delta + the threshold-flag for "marginal gain ≥ 0.02 (research.md §5
decision rule)".
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from phi3geom.dataset.types import BIN_IDS, BinId

MARGINAL_GAIN_THRESHOLD = 0.02  # Forman-Ricci "wins per bin" threshold


def load_auroc_report(path: Path) -> dict[BinId, dict[str, float]]:
    """Load a ``per_bin_auroc.json`` and return the parsed structure."""
    raw = json.loads(path.read_text())
    return {b: raw[b] for b in BIN_IDS if b in raw}


def compute_marginal_gain(
    spectral: dict[BinId, dict[str, float]],
    augmented: dict[BinId, dict[str, float]],
) -> dict[BinId, dict[str, float]]:
    """Per-bin marginal AUROC gain.

    Args:
        spectral: Per-bin spectral-only AUROC + CI.
        augmented: Per-bin spectral+Ricci AUROC + CI.

    Returns:
        ``{bin_id: {delta_auroc, ci_lower_approx, ci_upper_approx,
        is_significant_at_02}}``. The CI on the difference uses the
        ``(ci_lower_aug - ci_upper_sp, ci_upper_aug - ci_lower_sp)`` worst-
        case envelope, which is conservative but doesn't require joint
        bootstrap samples to be saved.
    """
    out: dict[BinId, dict[str, float]] = {}
    for b in BIN_IDS:
        if b not in spectral or b not in augmented:
            continue
        sp = spectral[b]
        au = augmented[b]
        delta = au["auroc"] - sp["auroc"]
        ci_lo = au["auroc_ci_lower"] - sp["auroc_ci_upper"]
        ci_hi = au["auroc_ci_upper"] - sp["auroc_ci_lower"]
        out[b] = {
            "delta_auroc": float(delta),
            "ci_lower_approx": float(ci_lo),
            "ci_upper_approx": float(ci_hi),
            "is_significant_at_02": bool(delta >= MARGINAL_GAIN_THRESHOLD),
            "spectral_auroc": float(sp["auroc"]),
            "augmented_auroc": float(au["auroc"]),
        }
    return out


def write_marginal_gain_report(
    *,
    spectral_path: Path,
    augmented_path: Path,
    out_path: Path,
) -> Path:
    """Compute + write the marginal-gain report."""
    spectral = load_auroc_report(spectral_path)
    augmented = load_auroc_report(augmented_path)
    per_bin = compute_marginal_gain(spectral, augmented)

    bins_significant = sum(
        1 for v in per_bin.values() if v.get("is_significant_at_02")
    )
    deltas = [v["delta_auroc"] for v in per_bin.values()]
    median_delta = sorted(deltas)[len(deltas) // 2] if deltas else math.nan
    payload: dict[str, Any] = {
        "per_bin": per_bin,
        "n_bins_marginal_gain_at_02": bins_significant,
        "median_delta_auroc": median_delta,
        "decision_rule_threshold": MARGINAL_GAIN_THRESHOLD,
        "ricci_load_bearing": bins_significant >= 4,  # research.md §5 4/6 rule
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return out_path
