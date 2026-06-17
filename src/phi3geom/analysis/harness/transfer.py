"""Cross-corpus / cross-model transfer splitters (SP-0 harness interface).

Leave-one-group-out splits — train on one corpus/model, test on another — the
headline differentiator that separates a real correctness geometry from a
corpus/length/confound artifact (constitution Principle III v3.0.0). Cross-model
transfer operates at the scalar-geometric-feature level (comparable across
differing d_model/n_heads).
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np


def leave_one_group_out(groups) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Yield ``(train_idx, test_idx)`` with each unique group held out as test."""
    groups = np.asarray(groups)
    idx = np.arange(len(groups))
    for g in np.unique(groups):
        test = idx[groups == g]
        train = idx[groups != g]
        if len(train) and len(test):
            yield train, test


def cross_corpus_split(corpus_ids) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Leave-one-corpus-out."""
    return leave_one_group_out(corpus_ids)


def cross_model_split(model_ids) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Leave-one-model-out."""
    return leave_one_group_out(model_ids)
