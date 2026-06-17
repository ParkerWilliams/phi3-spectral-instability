"""Unit tests for the v2 common event record (SP-0, T008)."""

import pytest

from phi3geom.dataset.types import DocQAEventRecord


def test_answerable_with_evidence_spans():
    rec = DocQAEventRecord(
        event_id="e1", corpus_id="hotpotqa", document="some doc", question="q?",
        gold_aliases=("paris",), is_answerable=True,
        evidence_spans=((10, 14),), provenance={"split": "train"},
    )
    assert rec.is_answerable
    assert rec.evidence_spans == ((10, 14),)


def test_closed_book_has_empty_doc_and_no_spans():
    rec = DocQAEventRecord(
        event_id="e2", corpus_id="triviaqa_nq", document="", question="q?",
        gold_aliases=("obama", "barack obama"), is_answerable=True,
    )
    assert rec.document == ""
    assert rec.evidence_spans is None


def test_unanswerable_must_have_empty_aliases():
    rec = DocQAEventRecord(
        event_id="e3", corpus_id="squad2", document="passage", question="q?",
        gold_aliases=(), is_answerable=False,
    )
    assert not rec.is_answerable
    assert rec.gold_aliases == ()


def test_answerable_requires_alias():
    with pytest.raises(ValueError):
        DocQAEventRecord(
            event_id="e", corpus_id="hotpotqa", document="d", question="q",
            gold_aliases=(), is_answerable=True,
        )


def test_unanswerable_rejects_aliases():
    with pytest.raises(ValueError):
        DocQAEventRecord(
            event_id="e", corpus_id="squad2", document="d", question="q",
            gold_aliases=("x",), is_answerable=False,
        )


def test_closed_book_rejects_spans():
    with pytest.raises(ValueError):
        DocQAEventRecord(
            event_id="e", corpus_id="triviaqa_nq", document="", question="q",
            gold_aliases=("x",), is_answerable=True, evidence_spans=((0, 1),),
        )


def test_rejects_inverted_span():
    with pytest.raises(ValueError):
        DocQAEventRecord(
            event_id="e", corpus_id="ruler", document="d", question="q",
            gold_aliases=("x",), is_answerable=True, evidence_spans=((5, 2),),
        )
