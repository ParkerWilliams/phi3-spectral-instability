"""Correctness + 4-way hallucination labeling (SP-0).

Builds on the constitution-aligned ``normalize_em`` (the 6-step EM pipeline) and
adds: alias exact-match (max over references), SQuAD-style token-F1 as a *reported
robustness cross-check*, and the 4-way label {correct-answer, wrong-answer,
correct-abstention, hallucination} with the hallucination-vs-safe headline binary
(research.md R3.2; data-model.md Label).

EM is the headline; token-F1 is never the headline (constitution Failure-event
contract v3.0.0).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Callable, Literal

from phi3geom.dataset.abstention import detect_abstention
from phi3geom.dataset.normalization import normalize_em

Class4Way = Literal[
    "correct-answer", "wrong-answer", "correct-abstention", "hallucination"
]


@dataclass(frozen=True, slots=True)
class Label:
    """The per-event supervised target (data-model.md)."""

    class_4way: Class4Way
    is_hallucination: bool  # headline positive = {wrong-answer, hallucination}
    em_match: bool
    token_f1: float
    abstained: bool
    abstention_evidence: str  # "rule" | "classifier" | "judge" | "none"


def alias_em(prediction: str, gold_aliases: list[str]) -> bool:
    """Exact-match-after-normalization, max over the alias set."""
    pred = normalize_em(prediction)
    return any(pred == normalize_em(g) for g in gold_aliases)


def _f1(pred_norm: str, gold_norm: str) -> float:
    pred_tokens = pred_norm.split()
    gold_tokens = gold_norm.split()
    if not pred_tokens and not gold_tokens:
        return 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0
    common = Counter(pred_tokens) & Counter(gold_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    precision = num_same / len(pred_tokens)
    recall = num_same / len(gold_tokens)
    return 2.0 * precision * recall / (precision + recall)


def token_f1(prediction: str, gold_aliases: list[str]) -> float:
    """SQuAD-style token-F1, max over the alias set (robustness cross-check)."""
    pred = normalize_em(prediction)
    return max((_f1(pred, normalize_em(g)) for g in gold_aliases), default=0.0)


def classify_4way(is_answerable: bool, em_match: bool, abstained: bool) -> Class4Way:
    """The 4-way truth table (research.md R3.2).

    On answerable items abstention is irrelevant to the class — an abstention on
    an answerable question is a (wrongful) failure, i.e. wrong-answer.
    """
    if is_answerable:
        return "correct-answer" if em_match else "wrong-answer"
    return "correct-abstention" if abstained else "hallucination"


def make_label(
    prediction: str,
    gold_aliases: list[str],
    is_answerable: bool,
    *,
    abstention_backstop: Callable[[str], bool] | None = None,
) -> Label:
    """Assemble the full 4-way ``Label`` for one (greedy) generation."""
    abstained, evidence = detect_abstention(prediction, backstop=abstention_backstop)
    em = alias_em(prediction, gold_aliases) if is_answerable else False
    f1 = token_f1(prediction, gold_aliases) if (is_answerable and gold_aliases) else 0.0
    cls = classify_4way(is_answerable, em, abstained)
    return Label(
        class_4way=cls,
        is_hallucination=cls in ("wrong-answer", "hallucination"),
        em_match=em,
        token_f1=f1,
        abstained=abstained,
        abstention_evidence=evidence if abstained else "none",
    )
