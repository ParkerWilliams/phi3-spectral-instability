"""Tests for ``phi3geom.dataset.matching`` (Spec FR-003)."""

from __future__ import annotations

import random

import pytest

from phi3geom.dataset.matching import (
    MatchingFailedError,
    cem_match,
    partition_by_stratum,
)
from phi3geom.dataset.types import BinId, DocQAEvent


def _event(
    event_id: str,
    template_id: str,
    density: str,
    length: str,
    is_fail: bool,
    bin_id: BinId = "B3",
) -> DocQAEvent:
    stratum_id = f"{template_id}|{density}|{length}"
    return DocQAEvent(
        event_id=event_id.ljust(64, "0"),
        document="doc",
        question="q?",
        gold_answer="gold",
        question_template_id=template_id,
        evidence_position_token_idx=0,
        evidence_distance_tokens=600,
        bin_id=bin_id,
        distractor_density=0.3,
        distractor_density_coarsening=density,  # type: ignore[arg-type]
        gold_answer_length_tokens=2,
        gold_answer_length_coarsening=length,  # type: ignore[arg-type]
        cem_stratum_id=stratum_id,
        adversariality_policy="none",
        model_generation="gen",
        model_generation_normalized="gen",
        gold_answer_normalized="gold",
        is_fail=is_fail,
        per_event_seed=0,
    )


def test_partition_groups_by_stratum_and_label() -> None:
    events = [
        _event("a", "tplA", "low", "1", is_fail=True),
        _event("b", "tplA", "low", "1", is_fail=False),
        _event("c", "tplA", "med", "1", is_fail=True),
    ]
    cells = partition_by_stratum(events)
    assert set(cells.keys()) == {"tplA|low|1", "tplA|med|1"}
    assert len(cells["tplA|low|1"][True]) == 1
    assert len(cells["tplA|low|1"][False]) == 1
    assert len(cells["tplA|med|1"][True]) == 1
    assert len(cells["tplA|med|1"][False]) == 0


def test_cem_match_perfectly_balanced_input() -> None:
    # 3 strata × 5 fail × 5 ctrl = 30 events → target 10/class → 30 events out
    events: list[DocQAEvent] = []
    for stratum in ("low|1", "med|1", "high|1"):
        density, length = stratum.split("|")
        for i in range(5):
            events.append(_event(f"f{stratum}{i}", "tplA", density, length, True))
            events.append(_event(f"c{stratum}{i}", "tplA", density, length, False))

    rng = random.Random(42)
    matched, strata = cem_match(events, bin_id="B3", target_per_class=10, rng=rng)

    # 10 fail + 10 ctrl
    assert sum(e.is_fail for e in matched) == 10
    assert sum(not e.is_fail for e in matched) == 10

    # Each stratum contributes 5 matched pairs of the 5 available
    for s in strata:
        assert s.n_matched_pairs == 5


def test_cem_match_drops_cells_with_only_one_label() -> None:
    # Cell 1: 5 fail + 0 ctrl → dropped
    # Cell 2: 5 fail + 5 ctrl → contributes 5 pairs
    events: list[DocQAEvent] = []
    for i in range(5):
        events.append(_event(f"f1{i}", "tplA", "low", "1", True))
    for i in range(5):
        events.append(_event(f"f2{i}", "tplA", "med", "1", True))
        events.append(_event(f"c2{i}", "tplA", "med", "1", False))

    rng = random.Random(7)
    matched, strata = cem_match(events, bin_id="B2", target_per_class=5, rng=rng)
    assert sum(e.is_fail for e in matched) == 5
    assert sum(not e.is_fail for e in matched) == 5
    # All matched events came from the 'med' stratum (the only viable cell).
    assert all(e.distractor_density_coarsening == "med" for e in matched)


def test_cem_match_raises_when_insufficient_pairs() -> None:
    # Total achievable: 2 pairs. Requesting 10 → MatchingFailedError.
    events = [
        _event("f1", "tplA", "low", "1", True),
        _event("c1", "tplA", "low", "1", False),
        _event("f2", "tplA", "med", "1", True),
        _event("c2", "tplA", "med", "1", False),
    ]
    rng = random.Random(0)
    with pytest.raises(MatchingFailedError) as exc_info:
        cem_match(events, bin_id="B1", target_per_class=10, rng=rng)
    assert exc_info.value.bin_id == "B1"
    assert exc_info.value.requested == 10
    assert exc_info.value.achieved == 2


def test_cem_match_deterministic_given_seed() -> None:
    events: list[DocQAEvent] = []
    for stratum in ("low|1", "med|1"):
        density, length = stratum.split("|")
        for i in range(10):
            events.append(_event(f"f{stratum}{i}", "tplA", density, length, True))
            events.append(_event(f"c{stratum}{i}", "tplA", density, length, False))

    matched_a, _ = cem_match(
        events, bin_id="B4", target_per_class=8, rng=random.Random(123)
    )
    matched_b, _ = cem_match(
        events, bin_id="B4", target_per_class=8, rng=random.Random(123)
    )
    assert [e.event_id for e in matched_a] == [e.event_id for e in matched_b]
