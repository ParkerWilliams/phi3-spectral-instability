"""HotpotQA corpus adapter — pure dict → DocQAEvent conversion.

Tests the converter on synthetic HotpotQA-shaped dicts so they run without
needing to download the dataset. The HF-backed loader is exercised
separately when a pilot actually runs.
"""
from __future__ import annotations

import pytest

from phi3geom.dataset.hotpotqa import hotpotqa_to_event
from phi3geom.dataset.types import DocQAEvent


def _toy_example():
    """A minimal HotpotQA-shaped dict (parallel-array schema, HF default)."""
    return {
        "question": "Who directed the film that starred X?",
        "answer": "Christopher Nolan",
        "context": {
            "title": ["Movie A", "Person B"],
            "sentences": [
                ["X starred in Movie A.", "It was directed by Christopher Nolan."],
                ["Person B was born in 1970.", "Person B is unrelated."],
            ],
        },
        "supporting_facts": {
            "title": ["Movie A", "Movie A"],
            "sent_id": [0, 1],
        },
        "type": "bridge",
        "level": "medium",
    }


def test_returns_doc_qa_event_with_core_fields():
    event = hotpotqa_to_event(
        example=_toy_example(),
        prompt_template_sha256="0" * 64,
        per_event_seed=42,
    )
    assert isinstance(event, DocQAEvent)
    assert event.question == "Who directed the film that starred X?"
    assert event.gold_answer == "Christopher Nolan"
    assert event.gold_answer_normalized == "christopher nolan"
    assert event.adversariality_policy == "none"
    assert event.is_fail is False
    assert event.model_generation == ""


def test_question_template_id_uses_hotpot_type():
    event = hotpotqa_to_event(
        example=_toy_example(), prompt_template_sha256="0" * 64, per_event_seed=0,
    )
    assert event.question_template_id == "bridge"

    comp = _toy_example()
    comp["type"] = "comparison"
    event = hotpotqa_to_event(
        example=comp, prompt_template_sha256="0" * 64, per_event_seed=0,
    )
    assert event.question_template_id == "comparison"


def test_document_concatenates_all_paragraphs():
    event = hotpotqa_to_event(
        example=_toy_example(), prompt_template_sha256="0" * 64, per_event_seed=0,
    )
    # Every paragraph's sentences should appear in the document text.
    for sent in ("X starred in Movie A.", "Christopher Nolan", "Person B"):
        assert sent in event.document or sent.split()[0] in event.document


def test_evidence_position_is_end_of_last_supporting_sentence():
    """The last supporting fact in our toy example is Movie A's sentence 1
    (`It was directed by Christopher Nolan.`). The evidence terminus should
    sit AFTER those words but BEFORE Person B's sentences."""
    event = hotpotqa_to_event(
        example=_toy_example(), prompt_template_sha256="0" * 64, per_event_seed=0,
    )
    words = event.document.split()
    # Find position of "Nolan." in word list:
    nolan_idx = next(i for i, w in enumerate(words) if w.startswith("Nolan"))
    # evidence terminus should be at or just past Nolan's word position.
    assert event.evidence_position_token_idx >= nolan_idx
    # And should be BEFORE the Person B content (no Person B words after evidence_position).
    person_b_idx = next(
        (i for i, w in enumerate(words) if "Person" in w), len(words)
    )
    assert event.evidence_position_token_idx <= person_b_idx


def test_distractor_density_reflects_non_supporting_paragraphs():
    """Toy example: 1 supporting paragraph (Movie A) + 1 distractor (Person B)
    → density = 0.5."""
    event = hotpotqa_to_event(
        example=_toy_example(), prompt_template_sha256="0" * 64, per_event_seed=0,
    )
    assert event.distractor_density == pytest.approx(0.5)


def test_bin_id_is_a_valid_literal():
    event = hotpotqa_to_event(
        example=_toy_example(), prompt_template_sha256="0" * 64, per_event_seed=0,
    )
    assert event.bin_id in ("B1", "B2", "B3", "B4", "B5", "B6")


def test_handles_legacy_tuple_list_schema():
    """Some HotpotQA exports use list-of-tuples instead of parallel arrays."""
    legacy = {
        "question": "?",
        "answer": "yes",
        "context": [
            ["Title A", ["Sentence A1.", "Sentence A2."]],
            ["Title B", ["Sentence B1."]],
        ],
        "supporting_facts": [["Title A", 0]],
        "type": "comparison",
        "level": "hard",
    }
    event = hotpotqa_to_event(
        example=legacy, prompt_template_sha256="0" * 64, per_event_seed=7,
    )
    assert event.question_template_id == "comparison"
    assert "Sentence A1" in event.document
    assert "Sentence B1" in event.document


def test_deterministic_event_id_for_same_input():
    a = hotpotqa_to_event(
        example=_toy_example(), prompt_template_sha256="0" * 64, per_event_seed=42,
    )
    b = hotpotqa_to_event(
        example=_toy_example(), prompt_template_sha256="0" * 64, per_event_seed=42,
    )
    assert a.event_id == b.event_id


def test_different_seeds_produce_different_event_ids():
    a = hotpotqa_to_event(
        example=_toy_example(), prompt_template_sha256="0" * 64, per_event_seed=1,
    )
    b = hotpotqa_to_event(
        example=_toy_example(), prompt_template_sha256="0" * 64, per_event_seed=2,
    )
    assert a.event_id != b.event_id


def test_handles_empty_supporting_facts_gracefully():
    """A malformed example with no supporting facts should still produce
    a valid event (evidence_position = end of doc) rather than crashing."""
    bad = _toy_example()
    bad["supporting_facts"] = {"title": [], "sent_id": []}
    event = hotpotqa_to_event(
        example=bad, prompt_template_sha256="0" * 64, per_event_seed=0,
    )
    n_words = len(event.document.split())
    assert event.evidence_position_token_idx == n_words


# ---------------------------------------------------------------------------
# Lookback-floor filter (added 2026-06-10 after the 62% skip rate finding)
# ---------------------------------------------------------------------------

def _long_example(n_paragraphs=4, words_per_sentence=10, sents_per_paragraph=15):
    """Build a HotpotQA-shaped dict whose total doc word count is controlled."""
    return {
        "question": "?",
        "answer": "yes",
        "context": {
            "title": [f"Title{i}" for i in range(n_paragraphs)],
            "sentences": [
                [" ".join(["w"] * words_per_sentence) + "."]
                * sents_per_paragraph
                for _ in range(n_paragraphs)
            ],
        },
        "supporting_facts": {"title": ["Title0"], "sent_id": [0]},
        "type": "bridge",
        "level": "medium",
    }


def test_meets_floor_true_for_long_doc():
    """4 paragraphs × 15 sentences × 10 words = 600 words >> 350 default."""
    from phi3geom.dataset.hotpotqa import (
        DEFAULT_MIN_DOC_WORDS,
        hotpotqa_meets_lookback_floor,
    )
    assert hotpotqa_meets_lookback_floor(_long_example()) is True
    # The default floor is 350; verify we built > 350 words above.
    assert DEFAULT_MIN_DOC_WORDS == 350


def test_meets_floor_false_for_short_doc():
    """1 paragraph × 5 sentences × 5 words = 25 words << 350."""
    from phi3geom.dataset.hotpotqa import hotpotqa_meets_lookback_floor
    short = _long_example(
        n_paragraphs=1, words_per_sentence=5, sents_per_paragraph=5,
    )
    assert hotpotqa_meets_lookback_floor(short) is False


def test_meets_floor_respects_custom_threshold():
    """A 100-word doc passes a min_doc_words=50 floor but fails a 200 floor."""
    from phi3geom.dataset.hotpotqa import hotpotqa_meets_lookback_floor
    medium = _long_example(
        n_paragraphs=1, words_per_sentence=10, sents_per_paragraph=10,
    )  # ~100 words
    assert hotpotqa_meets_lookback_floor(medium, min_doc_words=50) is True
    assert hotpotqa_meets_lookback_floor(medium, min_doc_words=200) is False


def test_meets_floor_handles_legacy_tuple_schema():
    """Same filter works on the list-of-tuples context schema."""
    from phi3geom.dataset.hotpotqa import hotpotqa_meets_lookback_floor
    legacy = {
        "question": "?",
        "answer": "yes",
        "context": [
            [f"T{i}", [" ".join(["w"] * 10) + "."] * 15]
            for i in range(4)
        ],
        "supporting_facts": [["T0", 0]],
        "type": "bridge",
        "level": "easy",
    }
    assert hotpotqa_meets_lookback_floor(legacy) is True
