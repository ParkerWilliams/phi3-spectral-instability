"""Lookback indexing for the J=256 dense F window and log-spaced D positions.

Two index conventions consumed by the cache layer:

- **F (dense)**: ``J = 256`` relative positions ``[-255, -254, …, 0]`` mapped
  to absolute token indices ``[t_answer_commit - 255, …, t_answer_commit]``.
- **D (log-spaced)**: 10 relative positions ``j ∈ {0, 1, 2, 4, 8, 16, 32, 64,
  128, 256}`` mapped to ``[t_answer_commit - j]``. Index ``j=0`` is the
  answer-commit token itself.

These conventions are pinned for v1; changing them is a breaking change on
the cache layout (contracts/cache.md).
"""

from __future__ import annotations

import numpy as np

J_LOOKBACK = 256
D_LOG_POSITIONS: tuple[int, ...] = (0, 1, 2, 4, 8, 16, 32, 64, 128, 256)


class LookbackOutOfBoundsError(ValueError):
    """The lookback window would extend before token 0."""


def f_lookback_absolute_indices(t_answer_commit: int) -> np.ndarray:
    """Absolute token indices for the dense F lookback window.

    Args:
        t_answer_commit: Absolute index of the first generated answer token.

    Returns:
        ``(J=256,) int64`` array of absolute token indices, ordered from
        oldest to newest: ``[t_answer_commit - 255, …, t_answer_commit]``.

    Raises:
        LookbackOutOfBoundsError: If ``t_answer_commit < J - 1``.
    """
    if t_answer_commit < J_LOOKBACK - 1:
        raise LookbackOutOfBoundsError(
            f"t_answer_commit={t_answer_commit} must be ≥ {J_LOOKBACK - 1} "
            "for the J=256 lookback window."
        )
    return np.arange(
        t_answer_commit - (J_LOOKBACK - 1),
        t_answer_commit + 1,
        dtype=np.int64,
    )


def d_lookback_absolute_indices(t_answer_commit: int) -> np.ndarray:
    """Absolute token indices for the log-spaced D lookback positions.

    Args:
        t_answer_commit: Absolute index of the first generated answer token.

    Returns:
        ``(10,) int64`` array of absolute token indices, one per
        ``D_LOG_POSITIONS`` entry, ordered to match.

    Raises:
        LookbackOutOfBoundsError: If ``t_answer_commit < max(D_LOG_POSITIONS) == 256``.
    """
    max_lookback = max(D_LOG_POSITIONS)
    if t_answer_commit < max_lookback:
        raise LookbackOutOfBoundsError(
            f"t_answer_commit={t_answer_commit} must be ≥ {max_lookback} for D lookback."
        )
    return np.array(
        [t_answer_commit - j for j in D_LOG_POSITIONS],
        dtype=np.int64,
    )


def f_relative_positions() -> np.ndarray:
    """Relative positions in the F tensor's axis-0: ``[-255, …, 0]``."""
    return np.arange(-(J_LOOKBACK - 1), 1, dtype=np.int64)
