"""Tests for ``phi3geom.reproducibility.seeds`` — Constitution Principle I."""

from __future__ import annotations

import hashlib

from phi3geom.reproducibility.seeds import (
    seed_for_analysis,
    seed_for_event,
    seed_for_match,
    seed_for_split,
)


def _expected(prefix: str, key: str) -> int:
    return int(hashlib.sha1(f"{prefix}{key}".encode()).hexdigest()[:8], 16)


def test_seed_for_event_matches_sha1_rule() -> None:
    event_id = "a" * 64
    assert seed_for_event(event_id) == _expected("event:", event_id)


def test_seed_for_match_matches_sha1_rule() -> None:
    assert seed_for_match("B3") == _expected("match:", "B3")


def test_seed_for_split_default_v1() -> None:
    assert seed_for_split() == seed_for_split("v1")
    assert seed_for_split("v1") == _expected("split:", "v1")


def test_seed_for_analysis_namespaced() -> None:
    step = "per_regime_composite:B3"
    assert seed_for_analysis(step) == _expected("analysis:", step)


def test_seeds_are_deterministic() -> None:
    for _ in range(5):
        assert seed_for_event("deadbeef") == seed_for_event("deadbeef")


def test_seeds_fit_in_uint32() -> None:
    bound = 2**32
    assert 0 <= seed_for_event("a" * 64) < bound
    assert 0 <= seed_for_match("B6") < bound
    assert 0 <= seed_for_split("v1") < bound
    assert 0 <= seed_for_analysis("step") < bound


def test_distinct_keys_produce_distinct_seeds() -> None:
    # Not a guarantee, but with a 32-bit space and only a handful of keys the
    # collision probability is negligible. This catches accidental constant
    # outputs (e.g., if someone accidentally returned a fixed value).
    seeds = {
        seed_for_event("a" * 64),
        seed_for_event("b" * 64),
        seed_for_match("B1"),
        seed_for_match("B2"),
        seed_for_split("v1"),
        seed_for_split("v2"),
        seed_for_analysis("step_a"),
        seed_for_analysis("step_b"),
    }
    assert len(seeds) == 8


def test_namespaces_are_independent() -> None:
    # event:X and match:X must produce different seeds (different namespace).
    assert seed_for_event("XYZ") != seed_for_match("XYZ")
    assert seed_for_match("XYZ") != seed_for_split("XYZ")
    assert seed_for_split("XYZ") != seed_for_analysis("XYZ")
