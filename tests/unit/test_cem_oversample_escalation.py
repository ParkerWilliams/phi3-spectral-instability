"""Tests for ``phi3geom.dataset.oversample`` (T056, FR-015)."""

from __future__ import annotations

import random

import pytest

from phi3geom.dataset.oversample import (
    CEMYieldEscalationError,
    cem_match_with_escalation,
)
from phi3geom.dataset.types import BinId, DocQAEvent


def _make_event(
    seq: int,
    *,
    template_id: str = "tplA",
    density: str = "low",
    length: str = "1",
    is_fail: bool,
    bin_id: BinId = "B3",
) -> DocQAEvent:
    return DocQAEvent(
        event_id=f"{seq:064x}",
        document="doc",
        question="q?",
        gold_answer="gold",
        question_template_id=template_id,
        evidence_position_token_idx=0,
        evidence_distance_tokens=600,
        bin_id=bin_id,
        distractor_density=0.1,
        distractor_density_coarsening=density,  # type: ignore[arg-type]
        gold_answer_length_tokens=1,
        gold_answer_length_coarsening=length,  # type: ignore[arg-type]
        cem_stratum_id=f"{template_id}|{density}|{length}",
        adversariality_policy="none",
        model_generation="gen",
        model_generation_normalized="gen",
        gold_answer_normalized="gold",
        is_fail=is_fail,
        per_event_seed=seq,
    )


def _good_pool_generator(target_size: int) -> list[DocQAEvent]:
    """Generates a fresh, balanced pool every call."""
    events: list[DocQAEvent] = []
    per_class = target_size // 2
    for i in range(per_class):
        events.append(_make_event(i * 2, is_fail=True))
    for i in range(per_class):
        events.append(_make_event(i * 2 + 1, is_fail=False))
    return events


def test_escalation_succeeds_at_1_5x_when_pool_is_healthy() -> None:
    result = cem_match_with_escalation(
        event_generator=_good_pool_generator,
        bin_id="B3",
        target_per_class=20,
        rng=random.Random(0),
    )
    assert result.oversample_factor == 1.5
    assert not result.is_compromised
    assert result.yield_pct >= 50.0


def test_escalates_to_3x_when_pool_is_thin() -> None:
    """A pool where 1.5× barely produces 50 pairs but 3× recovers more."""
    call_count = {"n": 0}

    def thin_generator(target_size: int) -> list[DocQAEvent]:
        call_count["n"] += 1
        # Always return many events so cem_match succeeds at target_per_class,
        # but constrain the yield by making fewer fail than ctrl.
        events: list[DocQAEvent] = []
        n_fail = 30  # always 30 fail
        n_ctrl = target_size // 2
        for i in range(n_fail):
            events.append(_make_event(i * 2, is_fail=True))
        for i in range(n_ctrl):
            events.append(_make_event(i * 2 + 1, is_fail=False))
        return events

    result = cem_match_with_escalation(
        event_generator=thin_generator,
        bin_id="B3",
        target_per_class=20,
        rng=random.Random(0),
    )
    # 1.5× yielded enough (30 fail vs 30 ctrl ≥ 20 each); should succeed at 1.5×
    assert result.oversample_factor in (1.5, 3.0)
    assert result.matched_events


def test_escalates_to_user_when_3x_fails() -> None:
    def starving_generator(target_size: int) -> list[DocQAEvent]:
        # Always return only 5 fail events; can't possibly match 50 pairs
        events: list[DocQAEvent] = []
        for i in range(5):
            events.append(_make_event(i * 2, is_fail=True))
        for i in range(target_size):
            events.append(_make_event(i * 2 + 1, is_fail=False))
        return events

    with pytest.raises(CEMYieldEscalationError):
        cem_match_with_escalation(
            event_generator=starving_generator,
            bin_id="B1",
            target_per_class=50,
            rng=random.Random(0),
        )
