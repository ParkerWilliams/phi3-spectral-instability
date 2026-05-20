"""Adversariality policies for B1 (and possibly B2) low-failure-rate bins (FR-016).

Three policies from research.md §11:

1. **lexical**: distractor sentences share ≥2 content tokens with the
   question, increasing the model's potential confusion.
2. **sibling_entity**: distractor sentences assert facts about a different
   entity from the same Wikidata class (e.g., for "Where was X born?",
   inject "Y was born in Z" where Y is another person).
3. **self_contradiction**: insert a sentence that contradicts the evidence
   (asserts a different answer to the same question).

The policy used per bin is recorded in ``manifest_header.adversariality_policy_per_bin``
and applied identically across all events in that bin.
"""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import replace

from phi3geom.dataset.generation import (
    FACTS,
    TEMPLATES,
    QuestionTemplate,
    WikidataFact,
)
from phi3geom.dataset.types import AdversarialityPolicy, DocQAEvent

_CONTENT_TOKEN_MIN_OVERLAP = 2


def _content_tokens(text: str) -> set[str]:
    """Lowercased non-stopword token set. Cheap approximation: split on
    whitespace, lowercase, drop tokens of length ≤3 (which roughly excludes
    English function words like 'is', 'the', 'of').
    """
    return {t for t in text.lower().split() if len(t) > 3}


def lexical_distractor(question: str, candidate: str) -> bool:
    """Return True if ``candidate`` shares ≥2 long content tokens with
    ``question``."""
    q_tokens = _content_tokens(question)
    c_tokens = _content_tokens(candidate)
    return len(q_tokens & c_tokens) >= _CONTENT_TOKEN_MIN_OVERLAP


def select_lexical_distractors(
    question: str,
    candidate_sentences: Iterable[str],
    n: int,
    rng: random.Random,
) -> list[str]:
    """Pick up to ``n`` distractor sentences that lexically overlap the question."""
    candidates = [c for c in candidate_sentences if lexical_distractor(question, c)]
    rng.shuffle(candidates)
    return candidates[:n]


def select_sibling_entity_distractors(
    template: QuestionTemplate,
    target_fact: WikidataFact,
    n: int,
    rng: random.Random,
) -> list[str]:
    """Pick up to ``n`` "same predicate, different subject" distractor
    sentences.

    These reinforce the question's pattern with WRONG answers, making the
    model's job harder than with topic-unrelated distractors.
    """
    sibling_facts = [
        f for f in FACTS[template.template_id]
        if f.subject != target_fact.subject and f.object != target_fact.object
    ]
    rng.shuffle(sibling_facts)
    return [template.statement(f) for f in sibling_facts[:n]]


def select_self_contradiction(
    template: QuestionTemplate,
    target_fact: WikidataFact,
    rng: random.Random,
) -> str:
    """A single contradicting sentence: same subject, different object."""
    alt_objects = [
        f.object for f in FACTS[template.template_id]
        if f.subject != target_fact.subject and f.object != target_fact.object
    ]
    rng.shuffle(alt_objects)
    if not alt_objects:
        return ""
    fake_fact = WikidataFact(
        subject=target_fact.subject,
        predicate=target_fact.predicate,
        object=alt_objects[0],
    )
    return template.statement(fake_fact)


def apply_adversariality(
    event: DocQAEvent,
    policy: AdversarialityPolicy,
    *,
    rng: random.Random,
    n_adversarial: int = 3,
) -> DocQAEvent:
    """Apply an adversariality policy to an event, returning a new event
    with augmented ``document`` and the policy recorded.

    Args:
        event: Original event (from ``generate_event``).
        policy: One of "none", "lexical", "sibling_entity", "self_contradiction".
        rng: Seeded RNG.
        n_adversarial: Number of adversarial sentences to inject. Default 3.

    Returns:
        New ``DocQAEvent`` with updated ``document`` and
        ``adversariality_policy``. event_id is recomputed.
    """
    if policy == "none":
        return replace(event, adversariality_policy="none")

    template = next(t for t in TEMPLATES if t.template_id == event.question_template_id)
    fact = WikidataFact(
        subject=event.gold_answer,  # the question's subject. Imperfect: see note.
        predicate=template.template_id,
        object=event.gold_answer,
    )
    # The template's question_form has {subject}; reconstruct the actual
    # subject by reversing the template's statement_form. For v1 we
    # approximate: assume the subject string is in the question via the
    # template_id catalog. The full Wikidata-fact-recovery is left to the
    # caller via the event-id provenance chain.
    # For correctness in v1, look up the fact by gold_answer back-search:
    matching = [
        f for f in FACTS[template.template_id] if f.object == event.gold_answer
    ]
    if matching:
        fact = matching[0]

    extras: list[str] = []
    if policy == "lexical":
        # Pull candidate sentences from all templates and filter by overlap.
        all_sentences = [
            t.statement(f) for t in TEMPLATES for f in FACTS[t.template_id]
            if f.object != event.gold_answer
        ]
        extras = select_lexical_distractors(
            event.question, all_sentences, n=n_adversarial, rng=rng
        )
    elif policy == "sibling_entity":
        extras = select_sibling_entity_distractors(
            template, fact, n=n_adversarial, rng=rng
        )
    elif policy == "self_contradiction":
        contradiction = select_self_contradiction(template, fact, rng=rng)
        if contradiction:
            extras = [contradiction]
    else:
        raise ValueError(f"Unknown adversariality policy: {policy!r}")

    if not extras:
        # No distractors available — keep the event unchanged but record the
        # attempted policy for the manifest.
        return replace(event, adversariality_policy=policy)

    new_document = event.document + " " + " ".join(extras)

    # Recompute event_id since the document text changed.
    from phi3geom.dataset.manifest import compute_event_id
    new_event_id = compute_event_id(
        prompt_template_sha256="recomputed",  # caller must re-pass before persisting
        document=new_document,
        question=event.question,
        gold_answer=event.gold_answer,
    )
    # Note: event_id will be re-derived again by the manifest write step with
    # the actual prompt_template_sha256. The placeholder here is a deterministic
    # tag to prevent two different documents from sharing the original event_id.

    return replace(
        event,
        document=new_document,
        adversariality_policy=policy,
        event_id=new_event_id,
    )
