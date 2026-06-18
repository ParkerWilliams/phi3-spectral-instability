"""Corpus-adapter contract test (SP-0, T037) — CPU via a fake `datasets` module.

Validates the common-record construction for every corpus without a real download:
answerable↔aliases, unanswerable↔empty-aliases, closed-book↔empty-document, and that
the records satisfy the DocQAEventRecord invariants. RULER is read from a tmp jsonl.
"""

import json
import sys
from types import SimpleNamespace

_ROWS = {
    "hotpot_qa": [
        {
            "context": {
                "title": ["A", "B"],
                "sentences": [
                    ["Paris is the capital of France.", "It is large."],
                    ["Berlin is in Germany."],
                ],
            },
            "question": "What is the capital of France?",
            "answer": "Paris",
            "supporting_facts": {"title": ["A"], "sent_id": [0]},
        }
    ],
    "squad_v2": [
        {
            "id": "q1", "context": "Paris is the capital of France.",
            "question": "What is the capital?",
            "answers": {"text": ["Paris"], "answer_start": [0]},
        },
        {
            "id": "q2", "context": "An unrelated passage about cats.",
            "question": "What is the capital of Mars?",
            "answers": {"text": [], "answer_start": []},  # unanswerable
        },
    ],
    "trivia_qa": [
        {
            "question": "Who painted the Mona Lisa?",
            "answer": {
                "value": "Leonardo da Vinci",
                "aliases": ["Leonardo da Vinci", "Da Vinci"],
                "normalized_aliases": ["leonardo da vinci", "da vinci"],
            },
        }
    ],
}


def _install_fake_datasets(monkeypatch):
    def load_dataset(name, *args, **kwargs):
        return _ROWS[name]

    monkeypatch.setitem(sys.modules, "datasets", SimpleNamespace(load_dataset=load_dataset))


def test_hotpotqa_record(monkeypatch):
    _install_fake_datasets(monkeypatch)
    from phi3geom.dataset.adapters import hotpotqa

    rec = next(hotpotqa.iter_events(limit=1))
    assert rec.corpus_id == "hotpotqa"
    assert rec.document and rec.is_answerable
    assert rec.gold_aliases  # non-empty
    assert rec.evidence_spans is None  # tokenizer=None -> spans unavailable


def test_squad2_answerable_and_unanswerable(monkeypatch):
    _install_fake_datasets(monkeypatch)
    from phi3geom.dataset.adapters import squad2

    recs = list(squad2.iter_events(limit=2))
    ans, unans = recs[0], recs[1]
    assert ans.is_answerable and ans.gold_aliases
    assert not unans.is_answerable
    assert unans.gold_aliases == ()  # invariant: unanswerable -> no aliases
    assert unans.evidence_spans is None


def test_triviaqa_closed_book(monkeypatch):
    _install_fake_datasets(monkeypatch)
    from phi3geom.dataset.adapters import triviaqa_nq

    rec = next(triviaqa_nq.iter_events(limit=1))
    assert rec.document == ""  # closed-book
    assert rec.evidence_spans is None
    assert rec.is_answerable and len(rec.gold_aliases) >= 2


def test_ruler_from_jsonl(tmp_path):
    from phi3geom.dataset.adapters import ruler

    p = tmp_path / "ruler.jsonl"
    p.write_text(json.dumps({
        "input": "lots of haystack ... the magic number is 42 ... more haystack",
        "outputs": ["42"], "token_position_answer": 10, "length": 4096,
    }) + "\n")
    rec = next(ruler.iter_events(data_path=str(p), needle_token_len=8))
    assert rec.corpus_id == "ruler" and rec.document
    assert rec.gold_aliases == ("42",)
    assert rec.evidence_spans == ((10, 17),)  # pos .. pos+needle_len-1
