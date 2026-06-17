"""Unit tests for natural-difficulty balance sampling (SP-0, T042)."""

import numpy as np

from phi3geom.dataset.balance import balance_corpus, balance_dataset


def _rate(is_pos, keep):
    sub = np.asarray(is_pos, bool)[keep]
    return sub.mean() if sub.size else 0.0


def test_already_balanced_keeps_all():
    is_pos = np.array([True, False] * 50)  # p = 0.5
    keep = balance_corpus(is_pos)
    assert len(keep) == 100


def test_too_few_positives_downsamples_negatives_into_band():
    is_pos = np.array([True] * 10 + [False] * 90)  # p = 0.1
    keep = balance_corpus(is_pos, seed=1)
    assert 0.25 <= _rate(is_pos, keep) <= 0.75
    assert len(keep) <= 100  # no synthetic inflation
    assert is_pos[keep].sum() == 10  # all positives retained


def test_too_many_positives_downsamples_positives_into_band():
    is_pos = np.array([True] * 90 + [False] * 10)  # p = 0.9
    keep = balance_corpus(is_pos, seed=2)
    assert 0.25 <= _rate(is_pos, keep) <= 0.75
    assert (~is_pos[keep]).sum() == 10  # all negatives retained


def test_single_class_cannot_balance_keeps_all():
    is_pos = np.array([True] * 20)
    keep = balance_corpus(is_pos)
    assert len(keep) == 20  # honest: impossible to balance by downsampling


def test_balance_dataset_per_corpus():
    corpora = np.array(["a"] * 100 + ["b"] * 100)
    is_pos = np.array([True] * 10 + [False] * 90 + [True] * 90 + [False] * 10)
    keep = balance_dataset(corpora, is_pos, seed=0)
    for c in ("a", "b"):
        idx = keep[corpora[keep] == c]
        assert 0.25 <= is_pos[idx].mean() <= 0.75
    assert len(keep) <= 200  # downsampling only
