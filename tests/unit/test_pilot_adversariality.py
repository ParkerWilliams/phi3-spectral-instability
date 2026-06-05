"""The pilot's --adversariality plumbing.

Verifies that ``_generate_candidate_events`` actually applies the requested
adversariality policy to every candidate, so the next pilot run produces a
harder dataset than the 2026-06-04 ``none`` run (which got 0.25% fail rate).
"""
from __future__ import annotations

import random

from phi3geom.extraction.pipeline import PROMPT_TEMPLATE_SHA256
from phi3geom.scripts.pilot_main import _generate_candidate_events


def test_default_policy_is_none():
    events = _generate_candidate_events(
        n_per_bin=2, rng=random.Random(0),
        prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
    )
    assert all(e.adversariality_policy == "none" for e in events)


def test_sibling_entity_policy_tags_every_event():
    events = _generate_candidate_events(
        n_per_bin=2, rng=random.Random(0),
        prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
        adversariality="sibling_entity",
        n_adversarial=3,
    )
    assert len(events) > 0
    assert all(e.adversariality_policy == "sibling_entity" for e in events)


def test_sibling_entity_lengthens_first_event_document():
    """Adversarial sentences should grow the doc. We compare the FIRST event
    of each run: rng state is identical until apply_adversariality consumes
    its first shuffle, so this is a deterministic same-input comparison.
    (Across all events the rng states diverge, making a sum-comparison flaky.)
    """
    seed = 42
    plain = _generate_candidate_events(
        n_per_bin=1, rng=random.Random(seed),
        prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
    )
    hard = _generate_candidate_events(
        n_per_bin=1, rng=random.Random(seed),
        prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
        adversariality="sibling_entity", n_adversarial=5,
    )
    assert len(hard[0].document) > len(plain[0].document), (
        f"plain[0] len={len(plain[0].document)}, hard[0] len={len(hard[0].document)}"
    )


def test_invalid_policy_raises():
    import pytest
    with pytest.raises(ValueError, match="Unknown adversariality policy"):
        _generate_candidate_events(
            n_per_bin=1, rng=random.Random(0),
            prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
            adversariality="bogus",  # type: ignore[arg-type]
        )
