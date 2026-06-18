"""Shared helpers for the corpus adapters (SP-0).

``event_id`` is CPU-pure (hashlib); ``char_span_to_tokens`` needs a tokenizer with
offset mapping (pod). Used by hotpotqa / squad2 / triviaqa_nq / ruler.
"""

from __future__ import annotations

import hashlib
from typing import Any

from phi3geom.extraction.pipeline import PROMPT_TEMPLATE_SHA256


def event_id(document: str, question: str, gold: str) -> str:
    """Constitution-I content hash: SHA256(prompt_template ‖ doc ‖ question ‖ gold)."""
    h = hashlib.sha256()
    for part in (PROMPT_TEMPLATE_SHA256, document, question, gold):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def char_span_to_tokens(
    text: str, start_char: int, end_char: int, tokenizer: Any
) -> tuple[int, int] | None:
    """Map a character span to a token range via the tokenizer's offset mapping."""
    if tokenizer is None:
        return None
    try:
        offsets = tokenizer(text, return_offsets_mapping=True)["offset_mapping"]
    except Exception:
        return None
    idx = [
        i for i, (a, b) in enumerate(offsets)
        if a >= start_char and b <= end_char and b > a
    ]
    return (min(idx), max(idx)) if idx else None
