"""Tests for ``phi3geom.dataset.distance`` (Spec FR-001)."""

from __future__ import annotations

import pytest

from phi3geom.dataset.distance import (
    EvidenceDistanceOutOfRangeError,
    assign_bin,
    compute_evidence_distance,
)


def test_compute_distance_basic() -> None:
    assert compute_evidence_distance(100, 200) == 100
    assert compute_evidence_distance(0, 1) == 1


def test_compute_distance_rejects_non_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        compute_evidence_distance(200, 200)  # zero
    with pytest.raises(ValueError, match="positive"):
        compute_evidence_distance(200, 100)  # negative


@pytest.mark.parametrize(
    ("distance", "expected_bin"),
    [
        # Lower boundary (inclusive) of each bin.
        (128, "B1"),
        (256, "B2"),
        (512, "B3"),
        (1024, "B4"),
        (2048, "B5"),
        (3072, "B6"),
        # Just inside the upper boundary (exclusive) of each bin.
        (255, "B1"),
        (511, "B2"),
        (1023, "B3"),
        (2047, "B4"),
        (3071, "B5"),
        (4095, "B6"),
        # Mid-bin values.
        (192, "B1"),
        (384, "B2"),
        (768, "B3"),
        (1536, "B4"),
        (2560, "B5"),
        (3584, "B6"),
    ],
)
def test_assign_bin_correctness(distance: int, expected_bin: str) -> None:
    assert assign_bin(distance) == expected_bin


@pytest.mark.parametrize("distance", [0, 1, 64, 127])
def test_assign_bin_below_range_raises(distance: int) -> None:
    with pytest.raises(EvidenceDistanceOutOfRangeError):
        assign_bin(distance)


@pytest.mark.parametrize("distance", [4096, 5000, 100_000])
def test_assign_bin_above_range_raises(distance: int) -> None:
    with pytest.raises(EvidenceDistanceOutOfRangeError):
        assign_bin(distance)


def test_bins_are_disjoint_and_contiguous() -> None:
    """Every integer in [128, 4096) maps to exactly one bin."""
    seen = set()
    for d in range(128, 4096):
        b = assign_bin(d)
        seen.add(b)
    assert seen == {"B1", "B2", "B3", "B4", "B5", "B6"}
