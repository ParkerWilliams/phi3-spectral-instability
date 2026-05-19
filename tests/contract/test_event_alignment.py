"""Contract test for lookback indexing (Spec FR-013, T035).

Ports the DCSBM event-alignment tests. Verifies that:

- ``f_lookback_absolute_indices(t)`` returns ``[t - 255, …, t]`` (length 256).
- ``d_lookback_absolute_indices(t)`` returns ``[t - 0, t - 1, t - 2, …, t - 256]``
  matching the ``D_LOG_POSITIONS`` ordering.
- Both functions raise ``LookbackOutOfBoundsError`` for too-early answer
  commits.
"""

from __future__ import annotations

import numpy as np
import pytest

from phi3geom.extraction.lookback import (
    D_LOG_POSITIONS,
    J_LOOKBACK,
    LookbackOutOfBoundsError,
    d_lookback_absolute_indices,
    f_lookback_absolute_indices,
    f_relative_positions,
)


def test_j_lookback_constant_is_256() -> None:
    assert J_LOOKBACK == 256


def test_d_log_positions() -> None:
    assert D_LOG_POSITIONS == (0, 1, 2, 4, 8, 16, 32, 64, 128, 256)


def test_f_lookback_length_is_256() -> None:
    idx = f_lookback_absolute_indices(t_answer_commit=500)
    assert idx.shape == (256,)


def test_f_lookback_endpoints() -> None:
    idx = f_lookback_absolute_indices(t_answer_commit=500)
    # Earliest position is t - (J-1); latest is t (inclusive).
    assert idx[0] == 245
    assert idx[-1] == 500


def test_f_lookback_monotone() -> None:
    idx = f_lookback_absolute_indices(t_answer_commit=1000)
    assert np.all(np.diff(idx) == 1)


def test_f_lookback_at_minimum_valid_t() -> None:
    # t_answer_commit = J - 1 = 255 is the minimum valid value.
    idx = f_lookback_absolute_indices(t_answer_commit=255)
    assert idx[0] == 0
    assert idx[-1] == 255


def test_f_lookback_below_minimum_raises() -> None:
    with pytest.raises(LookbackOutOfBoundsError, match="256"):
        f_lookback_absolute_indices(t_answer_commit=254)


def test_d_lookback_length_is_10() -> None:
    idx = d_lookback_absolute_indices(t_answer_commit=500)
    assert idx.shape == (10,)


def test_d_lookback_values_match_positions() -> None:
    idx = d_lookback_absolute_indices(t_answer_commit=500)
    expected = [500 - j for j in D_LOG_POSITIONS]
    assert idx.tolist() == expected


def test_d_lookback_at_minimum_valid_t() -> None:
    # max(D_LOG_POSITIONS) == 256, so t=256 is the minimum.
    idx = d_lookback_absolute_indices(t_answer_commit=256)
    assert idx[0] == 256
    assert idx[-1] == 0


def test_d_lookback_below_minimum_raises() -> None:
    with pytest.raises(LookbackOutOfBoundsError, match="D lookback"):
        d_lookback_absolute_indices(t_answer_commit=255)


def test_f_relative_positions() -> None:
    rel = f_relative_positions()
    assert rel.shape == (256,)
    assert rel[0] == -255
    assert rel[-1] == 0


def test_alignment_at_answer_commit() -> None:
    """Position 0 of F (rel) and j=0 of D both reference the answer-commit token."""
    t = 1000
    f_idx = f_lookback_absolute_indices(t)
    d_idx = d_lookback_absolute_indices(t)
    assert f_idx[-1] == t  # F's last position is the answer-commit token
    assert d_idx[0] == t  # D's j=0 position is the answer-commit token
