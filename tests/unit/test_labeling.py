"""Unit tests for correctness + 4-way hallucination labeling (SP-0)."""

import pytest

from phi3geom.dataset.labeling import (
    Label,
    alias_em,
    classify_4way,
    make_label,
    token_f1,
)


def test_alias_em_normalizes_and_maxes_over_aliases():
    assert alias_em("The Paris.", ["paris"]) is True
    assert alias_em("Barack Obama", ["Obama", "Barack Obama"]) is True
    assert alias_em("London", ["paris", "lyon"]) is False
    assert alias_em("anything", []) is False  # unanswerable: no aliases


def test_token_f1_partial_credit():
    # "Barack Obama" vs gold "Obama": P=1/2, R=1/1 -> F1 = 0.6667
    assert token_f1("Barack Obama", ["Obama"]) == pytest.approx(2 / 3, abs=1e-6)
    assert token_f1("Paris", ["Paris"]) == pytest.approx(1.0)
    assert token_f1("nope", ["Obama"]) == pytest.approx(0.0)
    assert token_f1("x", []) == pytest.approx(0.0)


def test_classify_4way_truth_table():
    assert classify_4way(True, True, False) == "correct-answer"
    assert classify_4way(True, False, False) == "wrong-answer"
    assert classify_4way(True, False, True) == "wrong-answer"  # abstain on answerable
    assert classify_4way(False, False, True) == "correct-abstention"
    assert classify_4way(False, False, False) == "hallucination"


def test_make_label_correct_answer():
    lab = make_label("Paris", ["paris"], is_answerable=True)
    assert isinstance(lab, Label)
    assert lab.class_4way == "correct-answer"
    assert lab.is_hallucination is False
    assert lab.em_match is True
    assert lab.token_f1 == pytest.approx(1.0)


def test_make_label_wrong_answer_is_positive():
    lab = make_label("London", ["paris"], is_answerable=True)
    assert lab.class_4way == "wrong-answer"
    assert lab.is_hallucination is True


def test_make_label_correct_abstention_is_safe():
    lab = make_label("I don't know.", [], is_answerable=False)
    assert lab.class_4way == "correct-abstention"
    assert lab.is_hallucination is False
    assert lab.abstained is True
    assert lab.abstention_evidence == "rule"


def test_make_label_hallucination_on_unanswerable():
    lab = make_label("The capital is Atlantis.", [], is_answerable=False)
    assert lab.class_4way == "hallucination"
    assert lab.is_hallucination is True
    assert lab.abstained is False


def test_make_label_backstop_recovers_paraphrase():
    # A paraphrase the rules miss; the injected classifier backstop catches it.
    def backstop(_text: str) -> bool:
        return True

    lab = make_label(
        "That detail is beyond what's given here.",
        [],
        is_answerable=False,
        abstention_backstop=backstop,
    )
    assert lab.class_4way == "correct-abstention"
    assert lab.abstention_evidence == "classifier"
