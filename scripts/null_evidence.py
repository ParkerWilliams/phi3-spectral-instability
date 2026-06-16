"""Negative-result evidence pack for the 7-dim mean geometry detector.

Makes the 'is this signal or noise?' question rigorous, on the 485-event cache:
 (A) Repeated stratified CV -> the honest AUROC (vs the lucky single-split 0.645).
 (B) Single-split seed distribution -> shows where 0.645 falls (split luck).
 (C) Permutation null -> empirical p-value for the observed CV mean.
 (D) Per-feature Cohen's d -> effect sizes.
CPU-only; uses the same 7-dim mean-over-(layers,heads) reduction as the headline.
"""
from __future__ import annotations
import argparse, json, pathlib, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold, train_test_split

FEATURES = ("qkt_stable_rank", "qkt_grass", "qkt_spec_entropy",
            "avwo_stable_rank", "avwo_grass", "avwo_spec_entropy",
            "forman_ricci_token")
HEADLINE_AUROC = 0.645


def load(cache_root: pathlib.Path):
    events, rows = [], []
    for ev_path in sorted(cache_root.rglob("event.json")):
        f = ev_path.parent / "F_summary.npy"
        if not f.exists():
            continue
        events.append(json.loads(ev_path.read_text()))
        arr = np.nan_to_num(np.load(f).astype(np.float64))   # (32,32,7,5)
        rows.append(arr[..., 0].mean(axis=(0, 1)))           # 7-dim mean reduction
    if not events:
        sys.exit(f"No event.json+F_summary.npy under {cache_root}")
    X = np.stack(rows)
    y = np.array([e["is_fail"] for e in events], dtype=int)
    return X, y


def cv_mean_auroc(X, y, *, seed):
    cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=20, random_state=seed)
    scores = []
    for tr, te in cv.split(X, y):
        clf = LogisticRegression(C=1.0, solver="lbfgs", max_iter=5000,
                                 class_weight="balanced", random_state=0)
        clf.fit(X[tr], y[tr])
        scores.append(roc_auc_score(y[te], clf.predict_proba(X[te])[:, 1]))
    return float(np.mean(scores)), float(np.std(scores))


def single_split_auroc(X, y, *, rs):
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.2, random_state=rs, stratify=y)
    clf = LogisticRegression(C=1.0, solver="lbfgs", max_iter=5000,
                             class_weight="balanced", random_state=rs)
    clf.fit(Xtr, ytr)
    return float(roc_auc_score(yte, clf.predict_proba(Xte)[:, 1]))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cache-root", type=pathlib.Path, required=True)
    p.add_argument("--out", type=pathlib.Path,
                   default=pathlib.Path("reports/null_evidence.json"))
    p.add_argument("--n-perm", type=int, default=200)
    args = p.parse_args()

    X, y = load(args.cache_root)
    print(f"Loaded {len(y)} events ({y.sum()} fails = {100*y.mean():.1f}%)")

    # (A) honest performance
    cv_m, cv_s = cv_mean_auroc(X, y, seed=0)
    print("\n(A) Repeated 5x20 stratified CV (the honest number):")
    print(f"    mean AUROC = {cv_m:.3f}  (sd {cv_s:.3f})   vs headline {HEADLINE_AUROC}")

    # (B) single-split luck
    seeds = [single_split_auroc(X, y, rs=i) for i in range(500)]
    seeds.sort()
    pct_ge = 100 * np.mean([s >= HEADLINE_AUROC for s in seeds])
    print("\n(B) 500 single 80/20 splits (what the headline is one draw from):")
    print(f"    median={np.median(seeds):.3f}  2.5%={seeds[12]:.3f}  97.5%={seeds[-13]:.3f}")
    print(f"    fraction of splits >= {HEADLINE_AUROC}: {pct_ge:.1f}%")

    # (C) permutation null on the CV mean
    rng = np.random.default_rng(0)
    null = []
    for _ in range(args.n_perm):
        yp = rng.permutation(y)
        m, _ = cv_mean_auroc(X, yp, seed=1)
        null.append(m)
    null.sort()
    p_val = (1 + sum(m >= cv_m for m in null)) / (1 + len(null))
    print(f"\n(C) Permutation null ({args.n_perm} label shuffles) on the CV mean:")
    print(f"    null mean={np.mean(null):.3f}  null 95%={null[int(.95*len(null))-1]:.3f}")
    print(f"    observed={cv_m:.3f}   empirical p-value = {p_val:.3f}")

    # (D) effect sizes
    print("\n(D) Per-feature Cohen's d (fail vs control):")
    d = {}
    for j, name in enumerate(FEATURES):
        a, b = X[y == 1, j], X[y == 0, j]
        sp = np.sqrt(((len(a)-1)*a.std(ddof=1)**2 + (len(b)-1)*b.std(ddof=1)**2)
                     / (len(a)+len(b)-2))
        dv = float((a.mean()-b.mean())/sp) if sp > 0 else 0.0
        d[name] = dv
        print(f"    {name:20s} d={dv:+.3f}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "n_events": len(y), "n_fails": int(y.sum()),
        "headline_auroc": HEADLINE_AUROC,
        "cv_mean_auroc": cv_m, "cv_std": cv_s,
        "single_split": {"median": float(np.median(seeds)),
                         "p2_5": seeds[12], "p97_5": seeds[-13],
                         "frac_ge_headline_pct": pct_ge},
        "permutation": {"n": args.n_perm, "null_mean": float(np.mean(null)),
                        "p_value": p_val},
        "cohens_d": d,
    }, indent=2))
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
