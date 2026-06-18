"""Closed-book TriviaQA / NQ-Open corpus adapter (SP-0, T039) — UNVALIDATED (pod).

No document (`document=""`, `evidence_spans=None`); the gold alias set drives EM
(TriviaQA ships `aliases` / `normalized_aliases`). Routing/attention-to-evidence
metrics are not applicable for this regime. `datasets` imported lazily.
"""

from __future__ import annotations

from typing import Any, Iterator

from phi3geom.dataset.adapters._common import event_id
from phi3geom.dataset.normalization import normalize_em
from phi3geom.dataset.types import DocQAEventRecord


def iter_events(
    *,
    split: str = "validation",
    limit: int | None = None,
    source: str = "trivia_qa",
    tokenizer: Any = None,  # unused (closed-book); kept for a uniform adapter signature
) -> Iterator[DocQAEventRecord]:
    import datasets

    if source == "trivia_qa":
        ds = datasets.load_dataset("trivia_qa", "rc.nocontext", split=split)
        for i, row in enumerate(ds):
            if limit is not None and i >= limit:
                break
            ans = row["answer"]
            aliases = (
                set(ans.get("aliases", []))
                | set(ans.get("normalized_aliases", []))
                | {ans["value"], normalize_em(ans["value"])}
            )
            yield DocQAEventRecord(
                event_id=event_id("", row["question"], ans["value"]),
                corpus_id="triviaqa_nq", document="", question=row["question"],
                gold_aliases=tuple(a for a in aliases if a),
                is_answerable=True, evidence_spans=None,
                provenance={"split": split, "source_index": i, "source": "trivia_qa"},
            )
    elif source == "nq_open":
        ds = datasets.load_dataset("nq_open", split=split)
        for i, row in enumerate(ds):
            if limit is not None and i >= limit:
                break
            answers = row["answer"]  # list of accepted short answers
            aliases = set(answers) | {normalize_em(a) for a in answers}
            yield DocQAEventRecord(
                event_id=event_id("", row["question"], answers[0] if answers else ""),
                corpus_id="triviaqa_nq", document="", question=row["question"],
                gold_aliases=tuple(a for a in aliases if a),
                is_answerable=True, evidence_spans=None,
                provenance={"split": split, "source_index": i, "source": "nq_open"},
            )
    else:
        raise ValueError(f"unknown closed-book source: {source!r}")
