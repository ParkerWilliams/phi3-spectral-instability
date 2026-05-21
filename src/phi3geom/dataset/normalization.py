"""Exact-match normalization for failure-event grading (Spec FR-002).

Six-step pipeline applied to both the model's generated answer and the
canonical gold answer:

    1. NFKC unicode normalize
    2. lowercase
    3. strip leading whitespace and punctuation
    4. strip leading articles ("a", "an", "the")
    5. collapse internal whitespace to single spaces
    6. strip trailing punctuation and whitespace

Match criterion is exact string equality after applying this pipeline to
both sides. LLM-as-judge, F1, substring, and semantic similarity are
forbidden by the constitution and the spec.
"""

from __future__ import annotations

import re
import string
import unicodedata

# Articles to strip from the leading position; case is already lowered.
_LEADING_ARTICLES: tuple[str, ...] = ("the ", "an ", "a ")

# Punctuation characters to strip from leading/trailing positions.
_PUNCT = string.punctuation

# Regex for collapsing runs of whitespace.
_WS_RUN = re.compile(r"\s+")


def normalize_em(text: str) -> str:
    """Apply the 6-step EM normalization pipeline.

    Args:
        text: Raw string. May be empty.

    Returns:
        Normalized form. Two strings that normalize to the same output are
        considered equal under exact-match-after-normalization.
    """
    # 1. NFKC
    text = unicodedata.normalize("NFKC", text)
    # 2. lowercase
    text = text.lower()
    # 3. strip leading whitespace + punctuation
    text = text.lstrip()
    text = text.lstrip(_PUNCT)
    text = text.lstrip()
    # 4. strip leading articles + any whitespace they leave behind
    for article in _LEADING_ARTICLES:
        if text.startswith(article):
            text = text[len(article):].lstrip()
            break
    # 5. collapse internal whitespace
    text = _WS_RUN.sub(" ", text)
    # 6. strip trailing punctuation + whitespace
    text = text.rstrip()
    text = text.rstrip(_PUNCT)
    text = text.rstrip()
    return text


def is_fail(model_generation: str, gold_answer: str) -> bool:
    """Return True iff the normalized model generation does NOT match the
    normalized gold answer.

    A failure is the *positive* outcome (the geometry that predicts it).
    """
    return normalize_em(model_generation) != normalize_em(gold_answer)
