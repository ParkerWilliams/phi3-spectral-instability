"""Per-(layer,head) linear fit on EACH F_summary stat, not just the mean.

F_summary[...,s] stats: 0=mean 1=p10 2=p50 3=p90 4=std (over token position).
The 0.645 headline + analyze_per_layer used only stat 0 (mean). This tests
whether the tails/spread (p10/p90/std) carry the signal the mean washes out.
CPU-only, reads the cached pilot tensors.
"""
from __future__ import annotations
import argparse, json, pathlib, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

STATS = ["mean", "p10", "p50", "p90", "std"]


def load(cache_root: pathlib.Path):
    events, mats = [], []
    for ev_path in sorted(cache_root.rglob("event.json")):
        f = ev_path.parent / "F_summary.npy"
        if not f.exists():
            continue
        events.append(json.loads(ev_path.read_text()))
        arr = np.load(f).astype(np.float64)            # (32,32,7,5)
        mats.append(np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0))
    if not events:
        sys.exit(f"No event.json+F_summary.npy under {cache_root}")
    X = np.stack(mats)                                  # (N,32,32,7,5)
    y = np.array([e["is_fail"] for e in events], dtype=int)
    return X, y


def fit(X, y, *, C, rs=0, nb=2000):
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.2, random_state=rs, stratify=y)
    clf = LogisticRegression(C=C, solver="lbfgs", max_iter=5000,
                             class_weight="balanced", random_state=rs)
    clf.fit(Xtr, ytr)
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
                   default=pathlib.Path("reports/stat_scan.json"))
    args = p.parse_args()

    X, y = load(args.cache_root)
    N = len(y)
    print(f"Loaded {N} events ({y.sum()} fails = {100*y.mean():.1f}%)  "
          f"F_summary {X.shape[1:]}")
    out = {"n_events": N, "n_fails": int(y.sum()), "per_stat": {}, "all_stats": None}

    print("\n=== per-(layer,head) 7168-dim L2 logistic (C=0.001), ONE stat at a time ===")
    for s, name in enumerate(STATS):
        Xs = X[..., s].reshape(N, -1)                   # (N, 32*32*7)
        a, lo, hi, nt = fit(Xs, y, C=0.001)
        flag = "  <-- BEATS CHANCE" if lo > 0.5 else ""
        print(f"  stat {s} {name:4s}: AUROC={a:.3f}  CI[{lo:.3f},{hi:.3f}]  n_test={nt}{flag}")
        out["per_stat"][name] = {"auroc": a, "ci_lo": lo, "ci_hi": hi, "n_test": nt}

    print("\n=== all 5 stats stacked, 35840-dim L2 logistic (C=0.0005) ===")
    Xa = X.reshape(N, -1)
    a, lo, hi, nt = fit(Xa, y, C=0.0005)
    flag = "  <-- BEATS CHANCE" if lo > 0.5 else ""
    print(f"  AUROC={a:.3f}  CI[{lo:.3f},{hi:.3f}]  n_test={nt}{flag}")
    out["all_stats"] = {"auroc": a, "ci_lo": lo, "ci_hi": hi, "n_test": nt}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
