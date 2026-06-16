"""Nonlinear (gradient-boosted trees) detector on the geometry features.

The linear L2-logistic put per-(layer,head) at 0.494 (chance). If the signal
is interaction-shaped rather than linear, a tree model could see what logistic
cannot. Tests HistGradientBoostingClassifier on three feature sets. CPU-only.
"""
from __future__ import annotations
import argparse, json, pathlib, sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_sample_weight

STATS = ["mean", "p10", "p50", "p90", "std"]


def load(cache_root: pathlib.Path):
    events, mats = [], []
    for ev_path in sorted(cache_root.rglob("event.json")):
        f = ev_path.parent / "F_summary.npy"
        if not f.exists():
            continue
        events.append(json.loads(ev_path.read_text()))
        arr = np.load(f).astype(np.float64)
        mats.append(np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0))
    if not events:
        sys.exit(f"No event.json+F_summary.npy under {cache_root}")
    X = np.stack(mats)
    y = np.array([e["is_fail"] for e in events], dtype=int)
    return X, y


def fit_gbt(X, y, *, rs=0, nb=2000):
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.2, random_state=rs, stratify=y)
    clf = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.05, max_depth=3,
        l2_regularization=1.0, random_state=rs)
    clf.fit(Xtr, ytr, sample_weight=compute_sample_weight("balanced", ytr))
    s = clf.predict_proba(Xte)[:, 1]
    a = float(roc_auc_score(yte, s))
    rng = np.random.default_rng(rs)
    bs = []
    for _ in range(nb):
        idx = rng.integers(0, len(yte), len(yte))
        if len(np.unique(yte[idx])) < 2:
            continue
        bs.append(float(roc_auc_score(yte[idx], s[idx])))
    bs.sort()
    return a, bs[int(.025 * len(bs))], bs[int(.975 * len(bs)) - 1], len(yte)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cache-root", type=pathlib.Path, required=True)
    p.add_argument("--out", type=pathlib.Path,
                   default=pathlib.Path("reports/nonlinear_fit.json"))
    args = p.parse_args()

    X, y = load(args.cache_root)
    N = len(y)
    print(f"Loaded {N} events ({y.sum()} fails = {100*y.mean():.1f}%)")

    feature_sets = {
        "per_layer_224_mean": X[..., 0].mean(axis=2).reshape(N, -1),  # (N,32*7)
        "per_lh_7168_mean": X[..., 0].reshape(N, -1),                 # (N,32*32*7)
        "all_stats_35840": X.reshape(N, -1),                          # (N,32*32*7*5)
    }
    out = {"n_events": N, "n_fails": int(y.sum()), "gbt": {}}
    print("\n=== HistGradientBoosting (depth=3, 300 trees, balanced) ===")
    for name, Xs in feature_sets.items():
        a, lo, hi, nt = fit_gbt(Xs, y)
        flag = "  <-- BEATS CHANCE" if lo > 0.5 else ""
        print(f"  {name:22s} dim={Xs.shape[1]:6d}: AUROC={a:.3f}  "
              f"CI[{lo:.3f},{hi:.3f}]  n_test={nt}{flag}")
        out["gbt"][name] = {"dim": int(Xs.shape[1]), "auroc": a,
                            "ci_lo": lo, "ci_hi": hi, "n_test": nt}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
