"""HotpotQA corpus adapter (SP-0, T019) — UNVALIDATED (pod: needs `datasets`).

Yields the common ``DocQAEventRecord``: the concatenated context as the document,
the gold answer (+ normalized alias) as ``gold_aliases``, and the supporting-sentence
token ranges as ``evidence_spans``. ``datasets`` is imported lazily.

⚠ The evidence-span token mapping is approximate (sentence text located in the
tokenized prompt); validate + tighten on the pod against a real tokenizer.
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterator

from phi3geom.dataset.normalization import normalize_em
from phi3geom.dataset.types import DocQAEventRecord
from phi3geom.extraction.pipeline import PROMPT_TEMPLATE_SHA256


def _event_id(document: str, question: str, gold: str) -> str:
    h = hashlib.sha256()
    for part in (PROMPT_TEMPLATE_SHA256, document, question, gold):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _evidence_spans(document: str, support_sentences: list[str], tokenizer: Any):
    """Approximate token ranges of the supporting sentences within the prompt.

    Locates each support sentence's character offset in the document, then maps to
    token indices via the tokenizer's offset mapping. Returns None if unavailable.
    """
    if tokenizer is None:
        return None
    try:
        enc = tokenizer(document, return_offsets_mapping=True)
        offsets = enc["offset_mapping"]
    except Exception:
        return None
    spans = []
    for sent in support_sentences:
        pos = document.find(sent)
        if pos < 0:
            continue
        start_char, end_char = pos, pos + len(sent)
        tok_idx = [i for i, (a, b) in enumerate(offsets) if a >= start_char and b <= end_char and b > a]
        if tok_idx:
            spans.append((min(tok_idx), max(tok_idx)))
    return spans or None


def iter_events(
    *, split: str = "validation", limit: int | None = None, tokenizer: Any = None
) -> Iterator[DocQAEventRecord]:
    """Yield HotpotQA events (distractor setting) as ``DocQAEventRecord``."""
    import datasets

    ds = datasets.load_dataset("hotpot_qa", "distractor", split=split)
    for i, row in enumerate(ds):
        if limit is not None and i >= limit:
            break
        titles = row["context"]["title"]
        sentences = row["context"]["sentences"]
        document = "\n".join(" ".join(s) for s in sentences)
        gold = row["answer"]
        support_titles = row["supporting_facts"]["title"]
        support_ids = row["supporting_facts"]["sent_id"]
        support_sents = []
        for t, sid in zip(support_titles, support_ids):
            if t in titles:
                ti = titles.index(t)
                if 0 <= sid < len(sentences[ti]):
                    support_sents.append(sentences[ti][sid])
        yield DocQAEventRecord(
            event_id=_event_id(document, row["question"], gold),
            corpus_id="hotpotqa",
            document=document,
            question=row["question"],
            gold_aliases=tuple({gold, normalize_em(gold)} - {""}) or (gold,),
            is_answerable=True,
            evidence_spans=_evidence_spans(document, support_sents, tokenizer),
            provenance={"split": split, "source_index": i},
        )
