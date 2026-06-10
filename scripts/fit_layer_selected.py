"""Fit a pooled distance-blind detector on a SELECTED subset of layers.

Why this exists
---------------
The 2026-06-09 HotpotQA pilot's headline used a 7-dim mean-over-(layers, heads)
reduction and landed at AUROC=0.526 (CI [0.392, 0.669]) — at chance. The
follow-up per-layer scan (``analyze_per_layer.py``) found the signal lives
in specific depths (L06 strongest at multivariate AUROC=0.620), while
roughly half the layers are *anti-predictive* and bury the signal when you
stack everything (the 224-dim pooled fit hit 0.498).

This script lets you fit on a chosen layer subset (e.g. ``--layers 6,15,16``,
giving a 21-dim model) so the signal-bearing depths aren't drowned by noise
from layers carrying nothing.

Caveat — pre-selecting layers from one cut and fitting on the same cut is
exploratory. The principled use is: pick layers from THIS run, then validate
the resulting detector on **independently-extracted** events from a future
pilot. Don't read this output as a confirmed result on its own.

Run:
    python scripts/fit_layer_selected.py --cache-root /tmp/pilot-analysis/cache --layers 6,15,16
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


def load_per_layer(cache_root: pathlib.Path):
    """Return (events, F_per_layer (N, 32, 7), labels (N,))."""
    events: list[dict] = []
    per_layer: list[np.ndarray] = []
    for ev_path in sorted(cache_root.rglob("event.json")):
        fsum_path = ev_path.parent / "F_summary.npy"
        if not fsum_path.exists():
            continue
        ev = json.loads(ev_path.read_text())
        arr = np.load(fsum_path).astype(np.float64)
        mean_stat = arr[..., 0]  # (32 layer, 32 head, 7 feature)
        if not np.all(np.isfinite(mean_stat)):
            mean_stat = np.where(np.isnan(mean_stat), 0.0, mean_stat)
        events.append(ev)
        per_layer.append(mean_stat.mean(axis=1))  # head-mean → (32, 7)
    if not events:
        sys.exit(f"No event.json+F_summary.npy pairs found under {cache_root}")
    return (
        events,
        np.stack(per_layer),
        np.array([e["is_fail"] for e in events], dtype=int),
    )


def fit_with_bootstrap(
    X: np.ndarray,
    y: np.ndarray,
    *,
    random_state: int,
    n_bootstrap: int,
    C: float,
):
    """Stratified split + L2 logistic with class_weight='balanced' + percentile
    bootstrap CI. Returns (auroc, ci_lo, ci_hi, n_train, n_test, clf)."""
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=random_state, stratify=y,
    )
    clf = LogisticRegression(
        C=C, solver="lbfgs", max_iter=5000,
        class_weight="balanced", random_state=random_state,
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
    return auroc, lo, hi, len(X_tr), len(y_te), clf


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache-root", type=pathlib.Path, required=True)
    p.add_argument(
        "--layers", type=str, required=True,
        help="Comma-separated layer indices to include, e.g. '6,15,16'.",
    )
    p.add_argument(
        "--C", type=float, default=1.0,
        help="L2 regularization (sklearn's inverse C). Default 1.0; "
             "use 0.1 for >50 dims, 0.01 for >200.",
    )
    p.add_argument("--random-state", type=int, default=0)
    p.add_argument("--n-bootstrap", type=int, default=2000)
    p.add_argument(
        "--out", type=pathlib.Path,
        default=pathlib.Path("reports/layer_selected_fit.json"),
    )
    args = p.parse_args()

    layers = [int(s) for s in args.layers.split(",")]
    for ell in layers:
        if not 0 <= ell < N_LAYERS:
            sys.exit(f"layer index {ell} out of range [0, {N_LAYERS})")

    print(f"Loading from {args.cache_root} ...")
    events, F_per_layer, labels = load_per_layer(args.cache_root)
    print(
        f"  {len(events)} events; {labels.sum()} fails "
        f"({100*labels.mean():.1f}%)"
    )

    X = F_per_layer[:, layers, :].reshape(len(events), -1)
    print(f"  selected layers: {layers}")
    print(f"  feature matrix:  {X.shape}  (={len(layers)} layers × 7 features)")

    auroc, lo, hi, n_tr, n_te, clf = fit_with_bootstrap(
        X, labels,
        random_state=args.random_state,
        n_bootstrap=args.n_bootstrap, C=args.C,
    )

    print()
    print("=" * 70)
    print("LAYER-SELECTED FIT")
    print("=" * 70)
    print(f"  layers      : {layers}")
    print(f"  L2 C        : {args.C}")
    print(f"  n_train     : {n_tr}")
    print(f"  n_test      : {n_te}")
    print(f"  AUROC       : {auroc:.3f}")
    print(f"  95% CI      : [{lo:.3f}, {hi:.3f}]")
    print(f"  beats chance: {lo > 0.5}")

    # Confound baseline for comparison
    distances = np.array(
        [ev["evidence_distance_tokens"] for ev in events], dtype=np.float64
    )
    doc_lengths = np.array(
        [len(ev["document"].split()) for ev in events], dtype=np.float64
    )
    Xc = np.column_stack([doc_lengths, distances])
    cauroc, clo, chi, _, _, _ = fit_with_bootstrap(
        Xc, labels,
        random_state=args.random_state,
        n_bootstrap=args.n_bootstrap, C=1.0,
    )
    print()
    print(f"  vs confound (length+distance only): {cauroc:.3f}  CI [{clo:.3f}, {chi:.3f}]")
    print(f"  geometry − confound: {auroc - cauroc:+.3f}")

    # Per-coefficient breakdown — which (layer, feature) cells drive the fit?
    print()
    print("Per-coefficient breakdown (top 10 by |coef|):")
    coefs = clf.coef_.ravel()
    coef_labels = [
        f"L{ell:02d} / {FEATURE_NAMES[f]}"
        for ell in layers for f in range(7)
    ]
    top = np.argsort(np.abs(coefs))[::-1][:10]
    for idx in top:
        print(f"  {coef_labels[idx]:35s}  coef = {coefs[idx]:+.3f}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "layers": layers,
        "n_events": len(events),
        "n_fails": int(labels.sum()),
        "n_train": n_tr,
        "n_test": n_te,
        "L2_C": args.C,
        "auroc": auroc,
        "ci_lo": lo,
        "ci_hi": hi,
        "beats_chance": lo > 0.5,
        "confound_auroc": cauroc,
        "confound_ci_lo": clo,
        "confound_ci_hi": chi,
        "delta_vs_confound": auroc - cauroc,
        "coefficients": dict(zip(coef_labels, coefs.tolist())),
    }, indent=2))
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
