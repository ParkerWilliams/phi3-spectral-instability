"""Tolerant post-hoc diagnostic binning (constitution v2.0.0, Principle III)."""
from __future__ import annotations

from phi3geom.dataset.distance import diagnostic_bin


def test_below_b1_floor_is_b0():
    assert diagnostic_bin(10) == "B0"
    assert diagnostic_bin(127) == "B0"


def test_in_range_matches_bin_ranges():
    assert diagnostic_bin(128) == "B1"
    assert diagnostic_bin(255) == "B1"
    assert diagnostic_bin(2048) == "B5"


def test_at_or_above_ceiling_is_b7():
    assert diagnostic_bin(4096) == "B7"
    assert diagnostic_bin(99999) == "B7"


def test_never_raises_on_negative():
    # A malformed/zero distance must bucket, not crash a diagnostic.
    assert diagnostic_bin(0) == "B0"
    assert diagnostic_bin(-5) == "B0"
