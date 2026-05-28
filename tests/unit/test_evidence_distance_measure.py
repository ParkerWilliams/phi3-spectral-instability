"""measure_evidence_distance_tokens uses the tokenizer to recover the true
distance from end-of-evidence to the answer-commit position."""
from __future__ import annotations

from dataclasses import replace

from phi3geom.extraction.pipeline import measure_evidence_distance_tokens, build_prompt
from phi3geom.dataset.generation import FACTS, TEMPLATES, generate_event
from phi3geom.extraction.pipeline import PROMPT_TEMPLATE_SHA256


class WhitespaceTokenizer:
    """Minimal stand-in: HF-style FLAT input_ids, one id per word (matches
    what a real HF tokenizer returns for a single string with no return_tensors)."""

    def __call__(self, text, return_tensors=None):
        return {"input_ids": text.split()}


def _toy_event(evidence_word_idx: int):
    tmpl = TEMPLATES[0]
    fact = FACTS[tmpl.template_id][0]
    ev = generate_event(
        template=tmpl, fact=fact, target_evidence_distance_words=20,
        distractor_density=0.3, prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
        bin_id="B1", rng=__import__("random").Random(0),
    )
    return replace(ev, evidence_position_token_idx=evidence_word_idx)


def test_distance_is_full_minus_prefix_tokens():
    tok = WhitespaceTokenizer()
    ev = _toy_event(evidence_word_idx=3)
    full = len(build_prompt(ev.document, ev.question).split())
    from phi3geom.extraction.pipeline import PROMPT_TEMPLATE
    preamble = PROMPT_TEMPLATE.split("{document}")[0]
    prefix = len((preamble + " ".join(ev.document.split()[:3])).split())
    expected = full - prefix
    assert measure_evidence_distance_tokens(ev, tok) == expected


def test_distance_is_positive_for_early_evidence():
    tok = WhitespaceTokenizer()
    ev = _toy_event(evidence_word_idx=1)
    assert measure_evidence_distance_tokens(ev, tok) > 0
