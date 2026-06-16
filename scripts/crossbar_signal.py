"""Cross-head RELATIONAL geometry detector — the D.npy crossbar, untested so far.

Everything analyzed to date used F_summary's PER-HEAD spectral features and came
back at chance. The D tensor is a different family: the pairwise Grassmannian
distance between every pair of heads' subspaces, per layer (how the heads relate
to each other, not each head in isolation). It's on the pod's disk (never pushed)
and needs no GPU.

D.npy shape: (10 D-positions, 32 layers, 32 head_i, 32 head_j, 2 edge-types).
The 10 positions are broadcast-equal (single-token v1), so we use position 0.
edge-type 0 = QKᵀ crossbar, 1 = AVWO crossbar.

Three reductions, each fit with the same L2-logistic + bootstrap-CI harness:
 1. full upper-triangle crossbar (31744-dim) — all head-pair distances,
 2. per-layer mean crossbar (64-dim) — the relational analog of the 7-dim mean,
 3. per-layer head-graph spectral gap (64-dim) — Fiedler value of the head graph
    (head-community structure the mean washes out).
"""
from __future__ import annotations
import argparse, json, pathlib, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

N_LAYERS, N_HEADS, N_EDGES = 32, 32, 2
_TRIU = np.triu_indices(N_HEADS, k=1)  # 496 head-pairs


def load(cache_root: pathlib.Path):
    events, mats = [], []
    for ev_path in sorted(cache_root.rglob("event.json")):
        d_path = ev_path.parent / "D.npy"
        if not d_path.exists():
            continue
        events.append(json.loads(ev_path.read_text()))
        arr = np.load(d_path).astype(np.float64)        # (10,32,32,32,2)
        mats.append(np.nan_to_num(arr[0]))              # (32,32,32,2) position 0
    if not events:
        sys.exit(f"No event.json+D.npy pairs under {cache_root} "
                 "(D.npy is the full cache, not the F_summary-only checkpoint).")
    D = np.stack(mats)                                  # (N,32,32,32,2)
    y = np.array([e["is_fail"] for e in events], dtype=int)
    return D, y


def _spectral_gap(w: np.ndarray) -> float:
    """Fiedler value (2nd-smallest Laplacian eigenvalue) of a 32x32 weight matrix."""
    w = np.nan_to_num(w).copy()
    np.fill_diagonal(w, 0.0)
    lap = np.diag(w.sum(axis=1)) - w
    ev = np.linalg.eigvalsh(lap)
    return float(ev[1]) if ev.size > 1 else 0.0


def feature_sets(D: np.ndarray):
    N = D.shape[0]
    # 1. full upper-triangle crossbar: (N, 32 layers * 496 pairs * 2 edges)
    full = D[:, :, _TRIU[0], _TRIU[1], :].reshape(N, -1)
    # 2. per-layer mean over head-pairs: (N, 32*2)
    per_layer_mean = D[:, :, _TRIU[0], _TRIU[1], :].mean(axis=2).reshape(N, -1)
    # 3. per-layer head-graph spectral gap: (N, 32*2)
    gap = np.empty((N, N_LAYERS, N_EDGES), dtype=np.float64)
    for i in range(N):
        for l in range(N_LAYERS):
            for e in range(N_EDGES):
                gap[i, l, e] = _spectral_gap(D[i, l, :, :, e])
    return {
        "full_crossbar_31744": full,
        "per_layer_mean_64": per_layer_mean,
        "spectral_gap_64": gap.reshape(N, -1),
    }


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
                   default=pathlib.Path("reports/crossbar_signal.json"))
    args = p.parse_args()

    D, y = load(args.cache_root)
    print(f"Loaded {len(y)} events ({y.sum()} fails = {100*y.mean():.1f}%)  "
          f"D[0] shape {D.shape[1:]}")
    fsets = feature_sets(D)
    # Strong regularization for the wide full set; mild for the 64-dim ones.
    cs = {"full_crossbar_31744": 0.001, "per_layer_mean_64": 0.1, "spectral_gap_64": 0.1}
    out = {"n_events": len(y), "n_fails": int(y.sum()), "fits": {}}
    print("\n=== cross-head RELATIONAL geometry detector (L2 logistic) ===")
    for name, X in fsets.items():
        a, lo, hi, nt = fit(X, y, C=cs[name])
        flag = "  <-- BEATS CHANCE" if lo > 0.5 else ""
        print(f"  {name:22s} dim={X.shape[1]:6d}: AUROC={a:.3f}  "
              f"CI[{lo:.3f},{hi:.3f}]  n_test={nt}{flag}")
        out["fits"][name] = {"dim": int(X.shape[1]), "auroc": a,
                             "ci_lo": lo, "ci_hi": hi, "n_test": nt}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
