"""Natural-difficulty balance sampling (SP-0, T042).

Brings each corpus's positive (fail/hallucination) rate into a target band by
**downsampling the majority class only** — never synthetic inflation (the v1
"too-accurate synthetic" lesson, [[project_001_phi3_too_accurate_for_cem_matching]]).
A single-class corpus cannot be balanced by downsampling, so all its events are
kept (the caller/pilot reports the imbalance).
"""

from __future__ import annotations

import numpy as np


def balance_corpus(
    is_positive, *, low: float = 0.25, high: float = 0.75, seed: int = 0
) -> np.ndarray:
    """KEEP indices that bring the positive rate into ``[low, high]``.

    Returns indices into the input array; ``len(result) ≤ len(input)`` always
    (downsampling only).
    """
    is_positive = np.asarray(is_positive, dtype=bool)
    n = is_positive.size
    if n == 0:
        return np.array([], dtype=int)
    pos = np.flatnonzero(is_positive)
    neg = np.flatnonzero(~is_positive)
    npos, nneg = pos.size, neg.size
    if npos == 0 or nneg == 0:
        return np.arange(n)  # single class: cannot balance by downsampling
    rng = np.random.default_rng(seed)
    p = npos / n
    if p < low:
        target_neg = int(np.floor(npos * (1.0 - low) / low))
        keep_neg = rng.choice(neg, size=min(nneg, target_neg), replace=False)
        kept = np.concatenate([pos, keep_neg])
    elif p > high:
        target_pos = int(np.floor(nneg * high / (1.0 - high)))
        keep_pos = rng.choice(pos, size=min(npos, target_pos), replace=False)
        kept = np.concatenate([keep_pos, neg])
    else:
        kept = np.arange(n)
    return np.sort(kept)


def balance_dataset(
    corpus_ids, is_positive, *, low: float = 0.25, high: float = 0.75, seed: int = 0
) -> np.ndarray:
    """Balance each corpus independently; return global KEEP indices."""
    corpus_ids = np.asarray(corpus_ids)
    is_positive = np.asarray(is_positive, dtype=bool)
    kept: list[np.ndarray] = []
    for ci, c in enumerate(np.unique(corpus_ids)):
        idx = np.flatnonzero(corpus_ids == c)
        local = balance_corpus(is_positive[idx], low=low, high=high, seed=seed + ci)
        kept.append(idx[local])
    return np.sort(np.concatenate(kept)) if kept else np.array([], dtype=int)
