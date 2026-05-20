"""Full-study writeup generator (FR-014, T070).

Produces 4 markdown artifacts under ``reports/full/``:

- ``per_bin_auroc.md`` — headline per-bin AUROC table.
- ``beta_layer_functions/{bin_id}_{edge_type}.json`` — β(ℓ) functions
  with 95% CI bands per (bin, head-graph).
- ``pooled_negative_control.md`` — SC-003 demonstration.
- ``head_graph_comparison.md`` — QKᵀ vs AVWO qualitative comparison
  (SC-009).
- ``discriminative_depths.md`` — naming the layer intervals identified
  by β(ℓ) per bin (SC-002).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from phi3geom.analysis.types import (
    FunctionalLogisticResult,
    PerRegimeCompositeFit,
    PooledNegativeControl,
)
from phi3geom.dataset.types import BIN_IDS, BinId


def write_per_bin_auroc_md(
    fits: dict[BinId, PerRegimeCompositeFit],
    out_path: Path,
) -> Path:
    """Markdown table of per-bin AUROC + CI."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Per-Regime Composite AUROC (Headline)",
        "",
        "Per-bin AUROC for the L2-regularized composite logistic on the 7-scalar",
        "atomic-unit features. SC-001 target: ≥4 of 6 bins with AUROC > 0.80 and",
        "95% CI not crossing 0.50.",
        "",
        "| Bin | AUROC | 95% CI Lower | 95% CI Upper | n_train | n_held_out | Passes SC-001? |",
        "|-----|-------|--------------|--------------|---------|------------|----------------|",
    ]
    n_passing = 0
    for bin_id in BIN_IDS:
        if bin_id not in fits:
            lines.append(f"| {bin_id} | — | — | — | — | — | (no fit) |")
            continue
        f = fits[bin_id]
        passes = f.auroc > 0.80 and f.auroc_ci_lower > 0.50
        if passes:
            n_passing += 1
        lines.append(
            f"| {bin_id} | {f.auroc:.3f} | {f.auroc_ci_lower:.3f} | "
            f"{f.auroc_ci_upper:.3f} | {f.n_events_train} | "
            f"{f.n_events_held_out} | {'✓' if passes else '✗'} |"
        )
    lines.append("")
    lines.append(
        f"**SC-001 verdict**: {n_passing} of 6 bins pass. "
        f"({'PASSES' if n_passing >= 4 else 'FAILS'} the ≥4-of-6 threshold.)"
    )
    lines.append("")
    out_path.write_text("\n".join(lines))
    return out_path


def write_beta_layer_functions(
    fda_fits: dict[tuple[BinId, str], FunctionalLogisticResult],
    out_dir: Path,
) -> list[Path]:
    """One JSON per (bin, edge_type) with β(ℓ) and CI bands."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for (bin_id, edge_type), f in fda_fits.items():
        payload = {
            "bin_id": bin_id,
            "edge_type": edge_type,
            "n_fpcs": f.n_fpcs,
            "fpc_variance_explained": f.fpc_variance_explained.tolist(),
            "beta_function": f.beta_function.tolist(),
            "beta_ci_lower": f.beta_ci_lower.tolist(),
            "beta_ci_upper": f.beta_ci_upper.tolist(),
            "discriminative_depth_intervals": [
                list(iv) for iv in f.discriminative_depth_intervals
            ],
        }
        p = out_dir / f"{bin_id}_{edge_type}.json"
        p.write_text(json.dumps(payload, indent=2))
        paths.append(p)
    return paths


def write_pooled_negative_control_md(
    pooled: PooledNegativeControl,
    out_path: Path,
) -> Path:
    """SC-003 demonstration: pooled AUROC collapses below the per-regime threshold."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    passes = pooled.auroc < 0.75 or pooled.auroc_ci_lower < 0.55
    lines = [
        "# Pooled Negative Control (SC-003)",
        "",
        "Logistic regression fit on events POOLED across all 6 evidence-distance",
        "bins. Per Constitution Principle III and the DCSBM-R2 lesson, this fit is",
        "expected to COLLAPSE relative to the per-regime composites (SC-001).",
        "",
        "| AUROC | 95% CI Lower | 95% CI Upper | n_train | n_held_out |",
        "|-------|--------------|--------------|---------|------------|",
        f"| {pooled.auroc:.3f} | {pooled.auroc_ci_lower:.3f} | "
        f"{pooled.auroc_ci_upper:.3f} | {pooled.n_events_train} | "
        f"{pooled.n_events_held_out} |",
        "",
        f"**SC-003 verdict**: {'PASSES (pooled fit collapses; per-regime signal confirmed).' if passes else 'FAILS (pooled fit retains discriminative power; the R2 lesson does not transfer cleanly).'}",
        "",
    ]
    out_path.write_text("\n".join(lines))
    return out_path


def write_head_graph_comparison_md(
    fda_fits: dict[tuple[BinId, str], FunctionalLogisticResult],
    out_path: Path,
) -> Path:
    """Compare QKᵀ-Grassmannian and AVWO-Grassmannian results per bin (SC-009)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Head-Graph Comparison: QKᵀ vs AVWO (SC-009)",
        "",
        "Per-bin comparison of discriminative-depth intervals derived from the",
        "two parallel head-graphs.",
        "",
        "| Bin | QKᵀ Intervals | AVWO Intervals | Overlap? |",
        "|-----|---------------|----------------|----------|",
    ]
    for bin_id in BIN_IDS:
        qkt = fda_fits.get((bin_id, "qkt_grassmannian"))
        avwo = fda_fits.get((bin_id, "avwo_grassmannian"))
        qkt_ivs = qkt.discriminative_depth_intervals if qkt else []
        avwo_ivs = avwo.discriminative_depth_intervals if avwo else []
        # Naive overlap: do any QKᵀ interval and any AVWO interval intersect?
        overlap = any(
            not (a[1] < b[0] or b[1] < a[0])
            for a in qkt_ivs
            for b in avwo_ivs
        )
        lines.append(
            f"| {bin_id} | {qkt_ivs or '—'} | {avwo_ivs or '—'} | "
            f"{'✓' if overlap else '✗'} |"
        )
    lines.append("")
    out_path.write_text("\n".join(lines))
    return out_path


def write_discriminative_depths_md(
    fda_fits: dict[tuple[BinId, str], FunctionalLogisticResult],
    out_path: Path,
) -> Path:
    """Naming the discriminative depths per bin (SC-002)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Discriminative Depths Per Bin (SC-002)",
        "",
        "Layer intervals where β(ℓ)'s 95% confidence band excludes zero.",
        "Reading: for each (bin, head-graph), the listed layer ranges are the",
        "depths whose attention geometry discriminates fail from control events.",
        "",
    ]
    n_passing = 0
    for bin_id in BIN_IDS:
        lines.append(f"## {bin_id}")
        lines.append("")
        has_signal = False
        for edge_type in ("qkt_grassmannian", "avwo_grassmannian"):
            f = fda_fits.get((bin_id, edge_type))
            if f is None:
                lines.append(f"- **{edge_type}**: no fit")
                continue
            if f.discriminative_depth_intervals:
                has_signal = True
                intervals_str = ", ".join(
                    f"layers {lo}–{hi}" for lo, hi in f.discriminative_depth_intervals
                )
                lines.append(f"- **{edge_type}**: {intervals_str}")
            else:
                lines.append(f"- **{edge_type}**: no discriminative depth (CI crosses 0)")
        if has_signal:
            n_passing += 1
        lines.append("")
    lines.append(
        f"**SC-002 verdict**: {n_passing} of 6 bins have ≥1 discriminative depth. "
        f"({'PASSES' if n_passing >= 4 else 'FAILS'} the ≥4-of-6 threshold.)"
    )
    lines.append("")
    out_path.write_text("\n".join(lines))
    return out_path


def write_full_writeup(
    *,
    composite_fits: dict[BinId, PerRegimeCompositeFit],
    fda_fits: dict[tuple[BinId, str], FunctionalLogisticResult],
    pooled: PooledNegativeControl,
    out_dir: Path,
) -> dict[str, Path]:
    """Convenience: write all writeup artifacts."""
    return {
        "per_bin_auroc": write_per_bin_auroc_md(composite_fits, out_dir / "per_bin_auroc.md"),
        "beta_layer_functions": out_dir / "beta_layer_functions",  # directory
        "pooled_negative_control": write_pooled_negative_control_md(
            pooled, out_dir / "pooled_negative_control.md"
        ),
        "head_graph_comparison": write_head_graph_comparison_md(
            fda_fits, out_dir / "head_graph_comparison.md"
        ),
        "discriminative_depths": write_discriminative_depths_md(
            fda_fits, out_dir / "discriminative_depths.md"
        ),
    }


# Quiet unused-import warning
_ = np
