"""Tests for ``phi3geom.dataset.generation``."""

from __future__ import annotations

import random

from phi3geom.dataset.generation import (
    FACTS,
    TEMPLATES,
    coarsen_density,
    coarsen_length,
    count_word_tokens,
    generate_event,
)
from phi3geom.dataset.manifest import verify_event_id


def test_ten_templates_enumerated() -> None:
    assert len(TEMPLATES) == 10
    template_ids = {t.template_id for t in TEMPLATES}
    assert template_ids == set(FACTS.keys())
    # Each template has ≥10 facts (per spec assumption).
    for tid, facts in FACTS.items():
        assert len(facts) >= 10, f"template {tid} has only {len(facts)} facts"


def test_coarsen_density() -> None:
    assert coarsen_density(0.0) == "low"
    assert coarsen_density(0.24) == "low"
    assert coarsen_density(0.25) == "med"
    assert coarsen_density(0.5) == "med"
    assert coarsen_density(0.74) == "med"
    assert coarsen_density(0.75) == "high"
    assert coarsen_density(1.0) == "high"


def test_coarsen_length() -> None:
    assert coarsen_length(1) == "1"
    assert coarsen_length(2) == "2-3"
    assert coarsen_length(3) == "2-3"
    assert coarsen_length(4) == "4+"
    assert coarsen_length(10) == "4+"


def test_generate_event_basic() -> None:
    template = TEMPLATES[0]  # birthplace
    fact = FACTS[template.template_id][0]  # Marie Curie / Warsaw
    rng = random.Random(0)
    event = generate_event(
        template=template,
        fact=fact,
        target_evidence_distance_words=20,
        distractor_density=0.5,
        prompt_template_sha256="c" * 64,
        bin_id="B1",
        rng=rng,
    )
    assert event.gold_answer == "Warsaw"
    assert "Warsaw" in event.document
    assert event.question == "Where was Marie Curie born?"
    assert event.question_template_id == "birthplace"
    assert event.cem_stratum_id == "birthplace|med|1"
    assert event.distractor_density_coarsening == "med"
    assert event.gold_answer_length_coarsening == "1"


def test_generate_event_id_is_canonical() -> None:
    template = TEMPLATES[1]  # capital_of
    fact = FACTS[template.template_id][0]  # France / Paris
    rng = random.Random(7)
    event = generate_event(
        template=template,
        fact=fact,
        target_evidence_distance_words=15,
        distractor_density=0.3,
        prompt_template_sha256="d" * 64,
        bin_id="B2",
        rng=rng,
    )
    assert verify_event_id(event, prompt_template_sha256="d" * 64)


def test_generate_event_deterministic_given_rng_seed() -> None:
    template = TEMPLATES[2]
    fact = FACTS[template.template_id][0]
    e1 = generate_event(
        template=template, fact=fact, target_evidence_distance_words=30,
        distractor_density=0.4, prompt_template_sha256="e" * 64,
        bin_id="B3", rng=random.Random(42),
    )
    e2 = generate_event(
        template=template, fact=fact, target_evidence_distance_words=30,
        distractor_density=0.4, prompt_template_sha256="e" * 64,
        bin_id="B3", rng=random.Random(42),
    )
    assert e1.event_id == e2.event_id
    assert e1.document == e2.document


def test_generate_event_gold_normalized_set() -> None:
    template = TEMPLATES[0]  # birthplace
    fact = FACTS[template.template_id][0]  # Warsaw
    rng = random.Random(0)
    event = generate_event(
        template=template, fact=fact, target_evidence_distance_words=10,
        distractor_density=0.2, prompt_template_sha256="f" * 64,
        bin_id="B1", rng=rng,
    )
    # Gold "Warsaw" already canonical
    assert event.gold_answer_normalized == "warsaw"


def test_generate_event_distractor_density_affects_document_length() -> None:
    template = TEMPLATES[0]
    fact = FACTS[template.template_id][0]

    low = generate_event(
        template=template, fact=fact, target_evidence_distance_words=10,
        distractor_density=0.05, prompt_template_sha256="g" * 64,
        bin_id="B1", rng=random.Random(0),
    )
    high = generate_event(
        template=template, fact=fact, target_evidence_distance_words=10,
        distractor_density=0.95, prompt_template_sha256="g" * 64,
        bin_id="B1", rng=random.Random(0),
    )
    assert count_word_tokens(high.document) > count_word_tokens(low.document)


def test_evidence_present_in_document() -> None:
    """The evidence sentence (containing the gold answer) is always in the
    document, regardless of distractor density."""
    template = TEMPLATES[3]  # author_of
    fact = FACTS[template.template_id][0]  # Hamlet / William Shakespeare
    for density in (0.05, 0.5, 0.95):
        event = generate_event(
            template=template, fact=fact, target_evidence_distance_words=10,
            distractor_density=density, prompt_template_sha256="h" * 64,
            bin_id="B2", rng=random.Random(0),
        )
        assert "William Shakespeare" in event.document
