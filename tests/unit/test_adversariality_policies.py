"""Tests for ``phi3geom.dataset.adversarial`` (T054)."""

from __future__ import annotations

import random

import pytest

from phi3geom.dataset.adversarial import (
    apply_adversariality,
    lexical_distractor,
    select_lexical_distractors,
    select_self_contradiction,
    select_sibling_entity_distractors,
)
from phi3geom.dataset.generation import FACTS, TEMPLATES, generate_event


def _make_event(bin_id: str = "B1") -> object:
    template = TEMPLATES[0]  # birthplace
    fact = FACTS[template.template_id][0]  # Marie Curie / Warsaw
    return generate_event(
        template=template, fact=fact,
        target_evidence_distance_words=20, distractor_density=0.2,
        prompt_template_sha256="c" * 64, bin_id=bin_id,  # type: ignore[arg-type]
        rng=random.Random(0),
    )


def test_lexical_distractor_detects_overlap() -> None:
    assert lexical_distractor("Where was Marie Curie born?", "Marie Curie discovered radium.")
    # No long-content overlap
    assert not lexical_distractor("Where was Marie Curie born?", "The sky is blue today.")


def test_select_lexical_distractors() -> None:
    candidates = [
        "Marie Curie discovered radium and polonium.",  # 2 content overlap
        "The cat sat on the mat.",  # 0 overlap
        "Curie won two Nobel prizes for her research.",  # 2 overlap
    ]
    rng = random.Random(0)
    picked = select_lexical_distractors(
        "Where was Marie Curie born?", candidates, n=5, rng=rng
    )
    # Both lexically-overlapping sentences are picked.
    assert len(picked) == 2


def test_sibling_entity_distractors() -> None:
    template = TEMPLATES[0]  # birthplace
    target_fact = FACTS[template.template_id][0]
    rng = random.Random(0)
    distractors = select_sibling_entity_distractors(
        template, target_fact, n=3, rng=rng
    )
    assert len(distractors) == 3
    for d in distractors:
        # Each is a birthplace-template statement for a different subject
        assert "was born in" in d
        assert target_fact.subject not in d


def test_self_contradiction_returns_same_subject_different_object() -> None:
    template = TEMPLATES[0]  # birthplace: "Marie Curie / Warsaw"
    target_fact = FACTS[template.template_id][0]
    rng = random.Random(0)
    sentence = select_self_contradiction(template, target_fact, rng=rng)
    assert target_fact.subject in sentence
    assert target_fact.object not in sentence


def test_apply_adversariality_none_is_identity() -> None:
    event = _make_event()
    result = apply_adversariality(event, "none", rng=random.Random(0))
    assert result.document == event.document
    assert result.adversariality_policy == "none"


def test_apply_adversariality_lexical_appends_distractors() -> None:
    event = _make_event()
    result = apply_adversariality(event, "lexical", rng=random.Random(0))
    assert result.adversariality_policy == "lexical"
    # New document is at least as long
    assert len(result.document) >= len(event.document)


def test_apply_adversariality_sibling_appends_distractors() -> None:
    event = _make_event()
    result = apply_adversariality(event, "sibling_entity", rng=random.Random(0))
    assert result.adversariality_policy == "sibling_entity"
    assert len(result.document) > len(event.document)


def test_apply_adversariality_self_contradiction_appends() -> None:
    event = _make_event()
    result = apply_adversariality(event, "self_contradiction", rng=random.Random(0))
    assert result.adversariality_policy == "self_contradiction"
    assert len(result.document) > len(event.document)


def test_apply_adversariality_unknown_policy_raises() -> None:
    event = _make_event()
    with pytest.raises(ValueError, match="Unknown adversariality policy"):
        apply_adversariality(event, "garbage", rng=random.Random(0))  # type: ignore[arg-type]


def test_apply_adversariality_changes_event_id_when_document_changes() -> None:
    event = _make_event()
    result = apply_adversariality(event, "sibling_entity", rng=random.Random(0))
    # event_id changes because document changed
    assert result.event_id != event.event_id
