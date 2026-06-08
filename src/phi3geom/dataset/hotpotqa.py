"""HotpotQA corpus adapter — DocQAEvent from real multi-hop QA examples.

Why this exists
---------------
The synthetic Wikidata-template corpus produces a 0.25% failure rate on
Phi-3-mini (2026-06-04 H100 pilot), too low to fit a failure detector or
even run CEM matching. HotpotQA is the empirically-validated alternative:
multi-hop questions over Wikipedia paragraphs where small models like
Phi-3-mini typically reach ~30–40% EM accuracy (so ~60–70% failure rate).
The dataset ships with **marked supporting-sentence spans**, which is
exactly what we need to compute a meaningful ``evidence_position_token_idx``.

What this module does
---------------------
Two functions:

- :func:`hotpotqa_to_event` (pure) converts one HF-shaped HotpotQA dict to
  a :class:`DocQAEvent`. Pure means: no I/O, no network — testable on a
  hand-built dict.
- :func:`load_hotpotqa_events` is a thin wrapper that calls
  ``datasets.load_dataset("hotpot_qa", "distractor", ...)`` and runs the
  converter over a deterministic sample. Only this function imports
  ``datasets`` (lazily), so unit tests of the converter don't need the
  HF datasets library installed.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

from phi3geom.dataset.distance import diagnostic_bin
from phi3geom.dataset.generation import coarsen_density, coarsen_length, count_word_tokens
from phi3geom.dataset.types import BinId, DocQAEvent


def _iter_paragraphs(context: Any) -> list[tuple[str, list[str]]]:
    """Normalize HotpotQA's context to a list of ``(title, sentences)`` pairs.

    HF's ``hotpot_qa`` exposes a parallel-array schema
    (``{"title": [...], "sentences": [[...], [...]]}``); some older exports
    use a list of ``[title, sentences]`` tuples. Support both.
    """
    if isinstance(context, dict):
        titles = context["title"]
        sentences = context["sentences"]
        return list(zip(titles, sentences))
    return [(t, s) for t, s in context]


def _iter_supporting(supporting: Any) -> list[tuple[str, int]]:
    """Normalize HotpotQA's supporting_facts to a list of ``(title, sent_id)``."""
    if isinstance(supporting, dict):
        titles = supporting.get("title", [])
        sent_ids = supporting.get("sent_id", [])
        return list(zip(titles, sent_ids))
    return [(t, int(i)) for t, i in supporting]


def _clamp_bin(b: str) -> BinId:
    """Clamp B0/B7 to the nearest valid BinId for the DocQAEvent type."""
    if b == "B0":
        return "B1"
    if b == "B7":
        return "B6"
    return b  # type: ignore[return-value]


def _make_event_id(
    *,
    question: str,
    gold_answer: str,
    document: str,
    prompt_template_sha256: str,
    seed: int,
) -> str:
    h = hashlib.sha256()
    h.update(question.encode("utf-8"))
    h.update(b"\x00")
    h.update(gold_answer.encode("utf-8"))
    h.update(b"\x00")
    h.update(document.encode("utf-8"))
    h.update(b"\x00")
    h.update(prompt_template_sha256.encode("ascii"))
    h.update(b"\x00")
    h.update(str(seed).encode("ascii"))
    return h.hexdigest()


def hotpotqa_to_event(
    *,
    example: dict,
    prompt_template_sha256: str,
    per_event_seed: int,
) -> DocQAEvent:
    """Convert one HotpotQA example to a :class:`DocQAEvent`.

    Args:
        example: One row from ``load_dataset("hotpot_qa", "distractor")``.
            Fields used: ``question``, ``answer``, ``context``,
            ``supporting_facts``, ``type``. Tolerates both the parallel-array
            HF schema and the legacy list-of-tuples schema.
        prompt_template_sha256: From
            ``phi3geom.extraction.pipeline.PROMPT_TEMPLATE_SHA256``.
        per_event_seed: Reproducibility seed; recorded on the event.

    Returns:
        A DocQAEvent with ``bin_id`` tentatively assigned from the
        word-level evidence distance (the pipeline measures the true
        tokenized distance later via
        :func:`phi3geom.extraction.pipeline.measure_evidence_distance_tokens`
        and overwrites ``evidence_distance_tokens``).
    """
    question = example["question"]
    gold_answer = example["answer"]

    paragraphs = _iter_paragraphs(example["context"])

    # Walk the paragraphs, recording the (title, sentence_idx) → end-of-sentence
    # word index so we can locate supporting facts in the concatenated document.
    doc_words: list[str] = []
    sent_word_ends: dict[tuple[str, int], int] = {}
    for title, sentences in paragraphs:
        for si, sentence in enumerate(sentences):
            sw = sentence.split()
            doc_words.extend(sw)
            sent_word_ends[(title, si)] = len(doc_words)
    document = " ".join(doc_words)

    # Evidence terminus = end of the LAST supporting sentence (max index).
    supporting = _iter_supporting(example.get("supporting_facts", []))
    if not supporting:
        evidence_position = len(doc_words)
    else:
        positions = [
            sent_word_ends[k] for k in supporting if k in sent_word_ends
        ]
        evidence_position = max(positions) if positions else len(doc_words)

    # Word-level "distance from evidence-end to document-end" — a tentative
    # value the pipeline overwrites with the true tokenizer distance.
    evidence_distance_words = max(0, len(doc_words) - evidence_position)
    bin_id = _clamp_bin(diagnostic_bin(evidence_distance_words))

    # HotpotQA's "type" field ("bridge" or "comparison") becomes the
    # CEM-stratifiable template id; comparison vs bridge questions differ
    # enough in difficulty profile that we want them in separate strata.
    template_id = example.get("type") or "bridge"

    # Distractor density: fraction of paragraphs that are NOT supporting.
    supporting_titles = {t for t, _ in supporting}
    n_paragraphs = len(paragraphs)
    n_distractor = sum(1 for t, _ in paragraphs if t not in supporting_titles)
    density = n_distractor / max(n_paragraphs, 1)

    n_gold_tokens = count_word_tokens(gold_answer)
    density_coarse = coarsen_density(density)
    length_coarse = coarsen_length(n_gold_tokens)
    stratum_id = f"{template_id}|{density_coarse}|{length_coarse}"

    event_id = _make_event_id(
        question=question,
        gold_answer=gold_answer,
        document=document,
        prompt_template_sha256=prompt_template_sha256,
        seed=per_event_seed,
    )

    return DocQAEvent(
        event_id=event_id,
        document=document,
        question=question,
        gold_answer=gold_answer,
        question_template_id=template_id,
        evidence_position_token_idx=evidence_position,
        evidence_distance_tokens=evidence_distance_words,
        bin_id=bin_id,
        distractor_density=density,
        distractor_density_coarsening=density_coarse,
        gold_answer_length_tokens=n_gold_tokens,
        gold_answer_length_coarsening=length_coarse,
        cem_stratum_id=stratum_id,
        adversariality_policy="none",
        model_generation="",
        model_generation_normalized="",
        gold_answer_normalized=gold_answer.lower().strip(),
        is_fail=False,
        per_event_seed=per_event_seed,
    )


def load_hotpotqa_events(
    *,
    n: int,
    rng: random.Random,
    prompt_template_sha256: str,
    split: str = "train",
) -> list[DocQAEvent]:
    """Load ``n`` HotpotQA examples (deterministically sampled) as DocQAEvents.

    Imports ``datasets`` lazily so unit tests of the converter don't need it.
    """
    from datasets import load_dataset

    ds = load_dataset("hotpot_qa", "distractor", split=split)
    indices = list(range(len(ds)))
    rng.shuffle(indices)
    indices = indices[:n]
    return [
        hotpotqa_to_event(
            example=ds[i],
            prompt_template_sha256=prompt_template_sha256,
            per_event_seed=i,
        )
        for i in indices
    ]
