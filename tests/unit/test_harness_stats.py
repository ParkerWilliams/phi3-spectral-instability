"""Unit tests for the harness statistics: null-evidence + transfer splitters (SP-0).

Statistical tests use fixed seeds + strong/zero planted signal with lenient bands
to stay deterministic.
"""

import numpy as np

from phi3geom.analysis.harness.null_evidence import null_evidence
from phi3geom.analysis.harness.transfer import (
    cross_corpus_split,
    leave_one_group_out,
)


def _make(n, d, signal, seed):
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, d))
    if signal:
        # y strongly driven by feature 0
        y = (X[:, 0] + 0.25 * rng.standard_normal(n) > 0).astype(int)
    else:
        y = rng.integers(0, 2, size=n)  # independent of X
    return X.astype(np.float64), y


def test_null_evidence_detects_real_signal():
    X, y = _make(200, 4, signal=True, seed=1)
    res = null_evidence(X, y, n_repeats=3, n_folds=4, n_perm=50, seed=0)
    assert res["cv_auroc_mean"] > 0.75
    assert res["permutation_p"] < 0.05
    assert res["null_mean"] < 0.65
    # feature 0 carries the effect
    assert abs(res["cohens_d"][0]) > abs(res["cohens_d"][1])


def test_null_evidence_rejects_noise():
    X, y = _make(200, 4, signal=False, seed=2)
    res = null_evidence(X, y, n_repeats=3, n_folds=4, n_perm=50, seed=0)
    assert 0.35 < res["cv_auroc_mean"] < 0.65
    assert res["permutation_p"] > 0.05


def test_null_evidence_width_generic():
    # works for any feature width with no hard-coded N_FEATURES
    X, y = _make(120, 11, signal=True, seed=3)
    res = null_evidence(X, y, n_repeats=2, n_folds=4, n_perm=20, seed=0)
    assert len(res["cohens_d"]) == 11


def test_leave_one_group_out_partitions_cleanly():
    groups = np.array(["a", "a", "b", "b", "c"])
    splits = list(leave_one_group_out(groups))
    assert len(splits) == 3  # one per unique group
    for train, test in splits:
        # no overlap; test is exactly one group
        assert set(train).isdisjoint(set(test))
        assert len(np.unique(groups[test])) == 1
        # train covers the other groups
        assert len(np.unique(groups[train])) == 2


def test_cross_corpus_split_is_leave_one_corpus_out():
    corpora = np.array(["hotpotqa", "squad2", "hotpotqa", "triviaqa_nq"])
    splits = list(cross_corpus_split(corpora))
    assert len(splits) == 3
