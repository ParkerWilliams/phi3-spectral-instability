"""Per-layer analysis of attention-geometry features.

The 7-dim mean reduction in pilot_main averages over 32 layers × 32 heads,
which throws away ~99.9% of the F tensor's content. This script tests
whether the signal that mean-reduction missed lives in specific depths
(per-layer) or in specific heads (per-(layer, head)) — entirely CPU-side
work on a cached pilot run, no GPU required.

Inputs: a directory of ``cache/<id_prefix>/<event_id>/{F_summary.npy,event.json}``
files as produced by the pilot (this is what the resilient checkpoint pushes
to an experiment branch).

Outputs:
1. **Univariate AUROC scan**: 32 × 7 cells, each is the AUROC of that
   single (layer, feature) value used as a raw score. Reveals if any
   single depth/feature combination is on its own discriminative.
2. **Per-layer multivariate**: fit a 7-dim L2 logistic on each layer
   individually. Tests if any single layer's 7-tuple beats chance.
3. **Pooled 224-dim**: fit a 224-dim L2 logistic on the full
   (32 layers × 7 features) stacked vector — the natural step up from
   the 7-dim mean.
4. **Optional 7168-dim per-(layer, head)**: with --with-full-lh, fit on
   the full (32 × 32 × 7) flattened vector under strong L2.

Each fit uses class_weight='balanced' (no CEM needed) + percentile-bootstrap
AUROC CIs over 2000 resamples.

Run:
    python scripts/analyze_per_layer.py --cache-root cache/
    python scripts/analyze_per_layer.py --cache-root /tmp/pilot-analysis/cache --with-full-lh
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

FEATURE_NAMES: tuple[str, ...] = (
    "qkt_stable_rank",
    "qkt_grass",
    "qkt_spec_entropy",
    "avwo_stable_rank",
    "avwo_grass",
    "avwo_spec_entropy",
    "forman_ricci_token",
)
N_LAYERS = 32
N_HEADS = 32
N_FEATURES = 7


def load_dataset(cache_root: pathlib.Path):
    """Load every event where both F_summary.npy AND event.json exist.

    Returns:
        events:      list of dicts (parsed event.json)
        F_per_layer: (N, 32, 7)        — mean-over-heads of stat 0
        F_per_lh:    (N, 32, 32, 7)    — full stat 0
        labels:      (N,) int          — is_fail
    """
    events: list[dict] = []
    per_layer: list[np.ndarray] = []
    per_lh: list[np.ndarray] = []
    for ev_path in sorted(cache_root.rglob("event.json")):
        fsum_path = ev_path.parent / "F_summary.npy"
        if not fsum_path.exists():
            continue
        ev = json.loads(ev_path.read_text())
        arr = np.load(fsum_path).astype(np.float64)
        # F_summary shape: (32 layer, 32 head, 7 feature, 5 stat)
        mean_stat = arr[..., 0]  # take stat 0 (mean), shape (32, 32, 7)
        if not np.all(np.isfinite(mean_stat)):
            mean_stat = np.where(np.isnan(mean_stat), 0.0, mean_stat)
        events.append(ev)
        per_layer.append(mean_stat.mean(axis=1))  # (32, 7)
        per_lh.append(mean_stat)                  # (32, 32, 7)

    if not events:
        sys.exit(f"No event.json+F_summary.npy pairs found under {cache_root}")
    return (
        events,
        np.stack(per_layer),
        np.stack(per_lh),
        np.array([ev["is_fail"] for ev in events], dtype=int),
    )


def fit_pooled(
    X: np.ndarray,
    y: np.ndarray,
    *,
    random_state: int = 0,
    n_bootstrap: int = 2000,
    class_weight: str = "balanced",
    C: float = 1.0,
):
    """Stratified train/test split + L2 logistic + percentile-bootstrap CI.
    Returns (auroc, ci_lo, ci_hi, n_test)."""
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=random_state, stratify=y,
    )
    clf = LogisticRegression(
        C=C, solver="lbfgs", max_iter=5000,
        class_weight=class_weight, random_state=random_state,
    )
    clf.fit(X_tr, y_tr)
    scores = clf.predict_proba(X_te)[:, 1]
    auroc = float(roc_auc_score(y_te, scores))

    rng = np.random.default_rng(random_state)
    aurocs: list[float] = []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, len(y_te), size=len(y_te))
        if len(np.unique(y_te[idx])) < 2:
            continue
        aurocs.append(float(roc_auc_score(y_te[idx], scores[idx])))
    aurocs.sort()
    lo = aurocs[int(0.025 * len(aurocs))]
    hi = aurocs[int(0.975 * len(aurocs)) - 1]
    return auroc, lo, hi, len(y_te)


def univariate_scan(F_per_layer: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """32 × 7 univariate AUROC, max(a, 1-a) so values are all ≥ 0.5."""
    out = np.full((N_LAYERS, N_FEATURES), 0.5)
    for ell in range(N_LAYERS):
        for f in range(N_FEATURES):
            x = F_per_layer[:, ell, f]
            if np.std(x) < 1e-12:
                continue
            a = float(roc_auc_score(labels, x))
            out[ell, f] = max(a, 1 - a)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache-root", type=pathlib.Path, required=True,
                   help="Directory containing <prefix>/<event_id>/{F_summary.npy,event.json}")
    p.add_argument("--out", type=pathlib.Path,
                   default=pathlib.Path("reports/per_layer_analysis.json"))
    p.add_argument("--with-full-lh", action="store_true",
                   help="Also fit the full 7168-dim per-(layer,head) detector.")
    args = p.parse_args()

    print(f"Loading from {args.cache_root} ...")
    events, F_per_layer, F_per_lh, labels = load_dataset(args.cache_root)
    print(f"Loaded {len(events)} events ({labels.sum()} fails = {100*labels.mean():.1f}%)")
    print(f"  F_per_layer shape: {F_per_layer.shape}")
    print(f"  F_per_lh shape:    {F_per_lh.shape}")

    # --- 1. Univariate scan ---
    print("\n" + "=" * 78)
    print("1) UNIVARIATE AUROC SCAN — each cell = AUROC of that single value as score")
    print("   .500 = no signal, .56 = weak, .60+ = noteworthy, .65+ = strong")
    print("=" * 78)
    scan = univariate_scan(F_per_layer, labels)
    header = "layer  " + " ".join(f"{n[:7]:>8s}" for n in FEATURE_NAMES) + "   max"
    print(header)
    for ell in range(N_LAYERS):
        row = " ".join(f"{scan[ell, f]:>8.3f}" for f in range(N_FEATURES))
        marker = "  ←" if scan[ell].max() >= 0.60 else ""
        print(f" L{ell:02d}   {row}   {scan[ell].max():.3f}{marker}")

    print("\nTOP 10 (layer, feature) cells by |AUROC - 0.5|:")
    flat_idx = np.argsort(scan.ravel())[::-1][:10]
    for k, idx in enumerate(flat_idx):
        ell, f = idx // N_FEATURES, idx % N_FEATURES
        print(f"  #{k+1}: L{ell:02d} / {FEATURE_NAMES[f]:24s} AUROC={scan[ell, f]:.3f}")

    # --- 2. Per-layer multivariate ---
    print("\n" + "=" * 78)
    print("2) PER-LAYER MULTIVARIATE — fit a 7-dim L2 logistic ON EACH LAYER alone")
    print("   (does any single layer's 7-tuple beat chance?)")
    print("=" * 78)
    per_layer_results: list[dict] = []
    for ell in range(N_LAYERS):
        X = F_per_layer[:, ell, :]
        auroc, lo, hi, n_te = fit_pooled(X, labels)
        per_layer_results.append(
            {"layer": ell, "auroc": auroc, "ci_lo": lo, "ci_hi": hi, "n_test": n_te}
        )
        flag = "  ← BEATS CHANCE" if lo > 0.5 else ""
        print(f" L{ell:02d}: AUROC={auroc:.3f}  CI [{lo:.3f}, {hi:.3f}]  n_test={n_te}{flag}")

    # --- 3. Pooled 224-dim ---
    print("\n" + "=" * 78)
    print("3) POOLED 224-dim — all 32 layers × 7 features stacked, L2 logistic (C=0.01)")
    print("=" * 78)
    X_pooled = F_per_layer.reshape(len(events), -1)
    auroc_p, lo_p, hi_p, n_te_p = fit_pooled(X_pooled, labels, C=0.01)
    flag_p = "  ← BEATS CHANCE" if lo_p > 0.5 else ""
    print(f"  AUROC={auroc_p:.3f}  CI [{lo_p:.3f}, {hi_p:.3f}]  n_test={n_te_p}{flag_p}")

    # --- 4. Optional full per-(layer, head) ---
    full_result = None
    if args.with_full_lh:
        print("\n" + "=" * 78)
        print("4) FULL 7168-dim per-(layer, head) — L2 logistic (C=0.001, strong)")
        print("=" * 78)
        X_full = F_per_lh.reshape(len(events), -1)
        auroc_f, lo_f, hi_f, n_te_f = fit_pooled(X_full, labels, C=0.001)
        flag_f = "  ← BEATS CHANCE" if lo_f > 0.5 else ""
        print(f"  AUROC={auroc_f:.3f}  CI [{lo_f:.3f}, {hi_f:.3f}]  n_test={n_te_f}{flag_f}")
        full_result = {
            "auroc": auroc_f, "ci_lo": lo_f, "ci_hi": hi_f, "n_test": n_te_f,
        }

    # Save JSON
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "n_events": len(events),
        "n_fails": int(labels.sum()),
        "fail_rate": float(labels.mean()),
        "feature_names": list(FEATURE_NAMES),
        "univariate_scan": scan.tolist(),
        "per_layer_multivariate": per_layer_results,
        "pooled_224dim": {
            "auroc": auroc_p, "ci_lo": lo_p, "ci_hi": hi_p, "n_test": n_te_p,
        },
        "full_per_lh_7168dim": full_result,
    }
    args.out.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
