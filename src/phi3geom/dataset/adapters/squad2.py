"""SQuAD2 corpus adapter (SP-0, T038) — UNVALIDATED (pod: needs `datasets`).

Answerable rows → `is_answerable=True` with gold answer spans; unanswerable rows →
`is_answerable=False`, empty `gold_aliases`, no spans (the hallucination testbed).
"""

from __future__ import annotations

from typing import Any, Iterator

from phi3geom.dataset.adapters._common import char_span_to_tokens, event_id
from phi3geom.dataset.normalization import normalize_em
from phi3geom.dataset.types import DocQAEventRecord


def iter_events(
    *, split: str = "validation", limit: int | None = None, tokenizer: Any = None
) -> Iterator[DocQAEventRecord]:
    import datasets

    ds = datasets.load_dataset("squad_v2", split=split)
    for i, row in enumerate(ds):
        if limit is not None and i >= limit:
            break
        answers = row["answers"]["text"]
        is_answerable = len(answers) > 0
        spans = None
        if is_answerable:
            start = row["answers"]["answer_start"][0]
            s = char_span_to_tokens(row["context"], start, start + len(answers[0]), tokenizer)
            spans = (s,) if s else None
        aliases = (
            tuple({a for a in answers} | {normalize_em(a) for a in answers} - {""})
            if is_answerable
            else ()
        )
        yield DocQAEventRecord(
            event_id=event_id(row["context"], row["question"], answers[0] if is_answerable else ""),
            corpus_id="squad2",
            document=row["context"],
            question=row["question"],
            gold_aliases=aliases or ((answers[0],) if is_answerable else ()),
            is_answerable=is_answerable,
            evidence_spans=spans,
            provenance={"split": split, "source_index": i, "qid": row.get("id")},
        )
