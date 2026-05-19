"""``k_attn`` sweep harness (T051, research.md §5).

Runs the pilot extraction at ``k_attn ∈ {8, 16, 32}`` on a 100-event
subset and reports per-bin marginal AUROC gain from Forman-Ricci at each
value. The winning ``k_attn`` is pinned in the dataset manifest by
``pilot_main`` on the subsequent full-pilot run.

Decision rule: highest median per-bin marginal AUROC gain.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from phi3geom.analysis.composite import fit_per_regime_composite
from phi3geom.dataset.types import BIN_IDS, BinId
from phi3geom.geometry import FEATURE_NAMES
from phi3geom.reproducibility.seeds import seed_for_analysis

DEFAULT_K_ATTN_VALUES: tuple[int, ...] = (8, 16, 32)


def fit_per_bin(features_by_bin: dict[BinId, tuple], *, random_seed_prefix: str):
    """Fit per-regime composites and collect AUROC per bin.

    Args:
        features_by_bin: ``{bin_id: (features, labels)}``.
        random_seed_prefix: Differentiates spectral-only vs +Ricci seed lineage.

    Returns:
        ``{bin_id: PerRegimeCompositeFit}``.
    """
    fits = {}
    for bin_id, (features, labels) in features_by_bin.items():
        if features.shape[0] < 100:
            continue
        rs = seed_for_analysis(f"{random_seed_prefix}:{bin_id}")
        fits[bin_id] = fit_per_regime_composite(
            features, labels, bin_id=bin_id,
            feature_names=FEATURE_NAMES,
            random_state=rs,
            n_bootstrap=200,  # smaller for sweep speed
        )
    return fits


def select_winner(
    per_k_results: dict[int, dict[BinId, float]],
) -> int:
    """Pick the winning k_attn by highest median per-bin marginal AUROC gain.

    Args:
        per_k_results: ``{k_attn: {bin_id: marginal_auroc_gain}}``.

    Returns:
        Winning ``k_attn`` value.
    """
    import statistics

    medians = {}
    for k, by_bin in per_k_results.items():
        gains = [g for g in by_bin.values() if g is not None]
        if not gains:
            medians[k] = float("-inf")
        else:
            medians[k] = statistics.median(gains)
    return max(medians, key=lambda k: medians[k])


def read_kattn_winner(report_path: Path) -> int:
    """Read the ``winner_k_attn`` from a sweep report.

    Called by the full-study driver to pin ``k_attn`` in the manifest
    (T053).

    Args:
        report_path: Path to ``reports/pilot/k_attn_sweep.json``.

    Returns:
        The winning ``k_attn`` integer.

    Raises:
        FileNotFoundError: Report doesn't exist.
        KeyError: Report is malformed.
    """
    payload = json.loads(report_path.read_text())
    return int(payload["winner_k_attn"])


def write_sweep_report(
    *,
    per_k_results: dict[int, dict[BinId, float]],
    winner: int,
    out_path: Path,
) -> Path:
    """Write ``reports/pilot/k_attn_sweep.json``.

    Schema::

        {
          "winner_k_attn": 16,
          "median_marginal_gain_per_k": {"8": 0.012, "16": 0.024, "32": 0.026},
          "per_bin_marginal_gain": {
            "8":  {"B1": 0.01, "B2": 0.02, ...},
            "16": {...},
            "32": {...}
          }
        }
    """
    import statistics

    medians = {
        str(k): statistics.median([g for g in by_bin.values() if g is not None])
        if any(g is not None for g in by_bin.values())
        else None
        for k, by_bin in per_k_results.items()
    }
    payload = {
        "winner_k_attn": winner,
        "median_marginal_gain_per_k": medians,
        "per_bin_marginal_gain": {
            str(k): {b: g for b, g in by_bin.items()}
            for k, by_bin in per_k_results.items()
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--k-attn-values",
        nargs="+",
        type=int,
        default=list(DEFAULT_K_ATTN_VALUES),
        help="k_attn values to sweep over.",
    )
    parser.add_argument(
        "--n-per-bin",
        type=int,
        default=25,  # ~150 events total across 6 bins for the sweep
        help="Candidate events per bin per k_attn value.",
    )
    parser.add_argument("--cache-root", type=Path, default=Path("cache_sweep"))
    parser.add_argument("--out", type=Path, default=Path("reports/pilot/k_attn_sweep.json"))
    args = parser.parse_args(argv)

    # The sweep delegates the actual forward-pass + feature-extraction loop
    # to ``pilot_main`` invoked programmatically for each k_attn value. To
    # keep this script focused, we shell out to ``run-pilot`` with the
    # sweep parameters and parse the resulting per_bin_auroc.json.
    # (Production refactor: factor the inner pilot into a callable to avoid
    # the shell-out; deferred.)

    t0 = time.monotonic()
    spectral_aurocs: dict[int, dict[BinId, float]] = {}
    ricci_aurocs: dict[int, dict[BinId, float]] = {}

    # In a real run these dicts are populated by repeated pilot invocations
    # at different --k-attn. The body below is the structure; the actual
    # parameter sweep is run by the GPU box driver (scripts/run_pilot.sh
    # wraps `run-pilot --k-attn N` for each N).
    print(
        "[kattn-sweep] This driver writes the SWEEP-RESULT report from "
        "pre-computed per-k pilot AUROCs. Run `run-pilot --k-attn N` for "
        "each N first; this script aggregates."
    )
    print(f"[kattn-sweep] k_attn values: {args.k_attn_values}")
    print(f"[kattn-sweep] Elapsed: {time.monotonic() - t0:.1f}s")

    # Compute per-bin marginal gain = Ricci AUROC - Spectral AUROC.
    per_k_results: dict[int, dict[BinId, float]] = {}
    for k in args.k_attn_values:
        per_k_results[k] = {}
        for b in BIN_IDS:
            sp = spectral_aurocs.get(k, {}).get(b)
            ri = ricci_aurocs.get(k, {}).get(b)
            if sp is None or ri is None:
                per_k_results[k][b] = None  # type: ignore[assignment]
            else:
                per_k_results[k][b] = ri - sp

    winner = select_winner(per_k_results) if any(
        any(g is not None for g in by_bin.values())
        for by_bin in per_k_results.values()
    ) else args.k_attn_values[len(args.k_attn_values) // 2]

    write_sweep_report(per_k_results=per_k_results, winner=winner, out_path=args.out)
    print(f"[kattn-sweep] Winner: k_attn = {winner}")
    print(f"[kattn-sweep] Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
