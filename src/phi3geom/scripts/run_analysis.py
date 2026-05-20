"""Headline analysis driver (T072 deferred to GPU box; entry point for US4).

Given the full-study dataset + cache populated by ``run-full-study``, this
script fits FDA per (bin, head-graph), runs the pooled negative control
(SC-003), and writes the writeup artifacts under ``reports/full/``.

Per Constitution Principle V deviation note: the actual *running* of this
analysis on real data lives on the GPU box (T072 in tasks.md is deferred).
This script is the entry point that the box invokes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from phi3geom.analysis.fda import fit_functional_logistic
from phi3geom.analysis.pooled_negative_control import fit as fit_pooled
from phi3geom.analysis.types import FunctionalLogisticResult
from phi3geom.dataset.manifest import read_manifest
from phi3geom.dataset.types import BIN_IDS, BinId
from phi3geom.reporting.writeup import write_beta_layer_functions, write_full_writeup
from phi3geom.reproducibility.seeds import seed_for_analysis


def _build_spine_curves_per_bin(
    events,
    *,
    cache_root: Path,
    expected_manifest_sha256: str,
    edge_type: str,
) -> dict[BinId, tuple[np.ndarray, np.ndarray]]:
    """Read each event's cached D tensor and extract the spine-curve view.

    Returns ``{bin_id: (curves[n, 32], labels[n])}``.
    """
    from phi3geom.storage.cache import read_D

    by_bin: dict[BinId, list[tuple[np.ndarray, bool]]] = {b: [] for b in BIN_IDS}
    edge_axis = 0 if edge_type == "qkt_grassmannian" else 1
    for event in events:
        try:
            D = read_D(
                event.event_id,
                expected_manifest_sha256=expected_manifest_sha256,
                cache_root=cache_root,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[run-analysis] skip event {event.event_id[:8]}: {exc}", file=sys.stderr)
            continue
        # D shape (10, 32, 32, 32, 2) → spine over layers from j=0 lookback
        # Aggregate the 32x32 head-pair matrix to one mean Grassmannian per layer
        mean_per_layer = D[0, :, :, :, edge_axis].mean(axis=(1, 2)).astype(np.float64)
        by_bin[event.bin_id].append((mean_per_layer, event.is_fail))

    out: dict[BinId, tuple[np.ndarray, np.ndarray]] = {}
    for bin_id, rows in by_bin.items():
        if not rows:
            continue
        curves = np.stack([r[0] for r in rows], axis=0)
        labels = np.array([r[1] for r in rows], dtype=bool)
        out[bin_id] = (curves, labels)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=Path("dataset"))
    parser.add_argument("--cache-root", type=Path, default=Path("cache"))
    parser.add_argument("--reports-dir", type=Path, default=Path("reports/full"))
    parser.add_argument("--n-bootstrap", type=int, default=1000)
    args = parser.parse_args(argv)

    print("[run-analysis] Reading manifest...")
    header, events = read_manifest(args.dataset_dir)
    print(f"[run-analysis] {len(events)} events; manifest SHA = {header.manifest_sha256[:8]}")

    # 1. Per-(bin, edge_type) functional logistic regression on spine curves.
    fda_fits: dict[tuple[BinId, str], FunctionalLogisticResult] = {}
    for edge_type in ("qkt_grassmannian", "avwo_grassmannian"):
        spine_data = _build_spine_curves_per_bin(
            events,
            cache_root=args.cache_root,
            expected_manifest_sha256=header.manifest_sha256,
            edge_type=edge_type,
        )
        for bin_id, (curves, labels) in spine_data.items():
            if curves.shape[0] < 100:
                continue
            seed = seed_for_analysis(f"functional_logistic:{bin_id}:{edge_type}")
            try:
                fda_fits[(bin_id, edge_type)] = fit_functional_logistic(
                    curves, labels, bin_id=bin_id, edge_type=edge_type,
                    random_state=seed, n_bootstrap=args.n_bootstrap,
                )
                print(
                    f"[run-analysis] FDA {bin_id} {edge_type}: "
                    f"{len(fda_fits[(bin_id, edge_type)].discriminative_depth_intervals)} "
                    "discriminative interval(s)"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[run-analysis] {bin_id}/{edge_type} FDA failed: {exc}", file=sys.stderr)

    # 2. Pooled negative control on a per-event feature aggregate (uses the
    # same mean-aggregate built by the full-study driver).
    from phi3geom.scripts.pilot_main import _build_feature_matrix
    pooled_features, pooled_labels = _build_feature_matrix(
        list(events),
        cache_root=args.cache_root,
        expected_manifest_sha256=header.manifest_sha256,
    )
    pooled = fit_pooled(
        pooled_features, pooled_labels,
        random_state=seed_for_analysis("pooled_negative_control"),
        n_bootstrap=args.n_bootstrap,
    )
    print(
        f"[run-analysis] Pooled AUROC = {pooled.auroc:.3f} "
        f"(95% CI [{pooled.auroc_ci_lower:.3f}, {pooled.auroc_ci_upper:.3f}])"
    )

    # 3. Read per-bin AUROC report from the full-study run.
    from phi3geom.reporting.pilot_reports import REPORTS_PILOT_DIR  # convenience
    composite_fits = {}  # would normally be loaded from per_bin_auroc.json
    # For deferred T072 (actual execution on GPU box), this is filled in.
    # Here we re-read the JSON if present.
    auroc_json = args.reports_dir / "per_bin_auroc.json"
    if auroc_json.exists():
        import json
        from phi3geom.analysis.types import PerRegimeCompositeFit
        from phi3geom.geometry import FEATURE_NAMES
        raw = json.loads(auroc_json.read_text())
        for bin_id, entry in raw.items():
            composite_fits[bin_id] = PerRegimeCompositeFit(
                bin_id=bin_id,
                feature_names=FEATURE_NAMES,
                coefficients=np.zeros(7, dtype=np.float64),  # not stored in JSON
                intercept=0.0,
                auroc=entry["auroc"],
                auroc_ci_lower=entry["auroc_ci_lower"],
                auroc_ci_upper=entry["auroc_ci_upper"],
                n_events_train=entry.get("n_events_train", 0),
                n_events_held_out=entry.get("n_events_held_out", 0),
            )

    # 4. Write writeup artifacts.
    paths = write_full_writeup(
        composite_fits=composite_fits,
        fda_fits=fda_fits,
        pooled=pooled,
        out_dir=args.reports_dir,
    )
    write_beta_layer_functions(fda_fits, args.reports_dir / "beta_layer_functions")
    for name, p in paths.items():
        print(f"[run-analysis] {name} → {p}")

    _ = REPORTS_PILOT_DIR  # quiet unused-import
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
