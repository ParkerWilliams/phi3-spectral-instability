"""Synthetic Wikidata-templated DocQA generation (FR-001).

Generates `DocQAEvent` instances by:

1. Sampling a `(question_template, fact)` pair from the v1 template catalog.
2. Building a document with the evidence sentence positioned at a chosen
   token offset (which lands the event in a target evidence-distance bin).
3. Filling the rest of the document with distractor sentences from other
   facts (achieving a chosen `distractor_density`).
4. Computing the canonical fields: `event_id` via SHA256, CEM coarsenings,
   bin assignment, per-event seed.

The model output (`model_generation`, `is_fail`) is populated downstream
by ``phi3geom.extraction.pipeline`` after the forward pass.

The template catalog is intentionally small (10 templates) so the v1
study is reproducible without an external Wikidata dump. Each template
ships with a stock of ~20 facts; combined this gives ~200 distinct
(question, gold) pairs before distractor variation — sufficient for
4800 events with substantial within-template repetition (CEM matches
within template, so repetition is expected).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from phi3geom.dataset.distance import assign_bin
from phi3geom.dataset.manifest import compute_event_id
from phi3geom.dataset.normalization import normalize_em
from phi3geom.dataset.types import (
    AdversarialityPolicy,
    BinId,
    DensityCoarsening,
    DocQAEvent,
    LengthCoarsening,
)
from phi3geom.reproducibility.seeds import seed_for_event


@dataclass(frozen=True, slots=True)
class WikidataFact:
    subject: str
    predicate: str  # one of the template ids
    object: str  # canonical gold answer


@dataclass(frozen=True, slots=True)
class QuestionTemplate:
    template_id: str
    question_form: str  # contains "{subject}"
    statement_form: str  # contains "{subject}" and "{object}"

    def question(self, fact: WikidataFact) -> str:
        return self.question_form.format(subject=fact.subject)

    def statement(self, fact: WikidataFact) -> str:
        return self.statement_form.format(subject=fact.subject, object=fact.object)


# ---------------------------------------------------------------------------
# Template catalog (v1, 10 templates with ~20 facts each)
# ---------------------------------------------------------------------------

TEMPLATES: tuple[QuestionTemplate, ...] = (
    QuestionTemplate(
        "birthplace",
        question_form="Where was {subject} born?",
        statement_form="{subject} was born in {object}.",
    ),
    QuestionTemplate(
        "capital_of",
        question_form="What is the capital of {subject}?",
        statement_form="The capital of {subject} is {object}.",
    ),
    QuestionTemplate(
        "death_year",
        question_form="In what year did {subject} die?",
        statement_form="{subject} died in {object}.",
    ),
    QuestionTemplate(
        "author_of",
        question_form="Who wrote {subject}?",
        statement_form="{subject} was written by {object}.",
    ),
    QuestionTemplate(
        "country_of",
        question_form="Which country is {subject} in?",
        statement_form="{subject} is in {object}.",
    ),
    QuestionTemplate(
        "language_of",
        question_form="What language is spoken in {subject}?",
        statement_form="The language spoken in {subject} is {object}.",
    ),
    QuestionTemplate(
        "inventor_of",
        question_form="Who invented {subject}?",
        statement_form="{subject} was invented by {object}.",
    ),
    QuestionTemplate(
        "founded_year",
        question_form="In what year was {subject} founded?",
        statement_form="{subject} was founded in {object}.",
    ),
    QuestionTemplate(
        "occupation_of",
        question_form="What was the occupation of {subject}?",
        statement_form="{subject} was a {object}.",
    ),
    QuestionTemplate(
        "material_of",
        question_form="What is {subject} made of?",
        statement_form="{subject} is made of {object}.",
    ),
)
"""The 10 v1 question templates. Pinned; adding/removing templates is a v2
ablation."""


# Facts per template — synthetic but coherent. Object strings are in canonical
# form (no leading articles/prepositions; bare entity name, date, or word).
FACTS: dict[str, tuple[WikidataFact, ...]] = {
    "birthplace": tuple(
        WikidataFact(s, "birthplace", o) for s, o in [
            ("Marie Curie", "Warsaw"), ("Albert Einstein", "Ulm"),
            ("Isaac Newton", "Woolsthorpe"), ("Ada Lovelace", "London"),
            ("Charles Darwin", "Shrewsbury"), ("Nikola Tesla", "Smiljan"),
            ("Galileo Galilei", "Pisa"), ("Stephen Hawking", "Oxford"),
            ("Rosalind Franklin", "London"), ("Dmitri Mendeleev", "Tobolsk"),
            ("Alan Turing", "London"), ("Carl Sagan", "Brooklyn"),
            ("Niels Bohr", "Copenhagen"), ("Pierre Curie", "Paris"),
            ("Werner Heisenberg", "Wurzburg"), ("Erwin Schrodinger", "Vienna"),
            ("Linus Pauling", "Portland"), ("Barbara McClintock", "Hartford"),
            ("Lise Meitner", "Vienna"), ("John von Neumann", "Budapest"),
        ]
    ),
    "capital_of": tuple(
        WikidataFact(s, "capital_of", o) for s, o in [
            ("France", "Paris"), ("Germany", "Berlin"), ("Japan", "Tokyo"),
            ("Brazil", "Brasilia"), ("Australia", "Canberra"), ("Egypt", "Cairo"),
            ("Mexico", "Mexico City"), ("Turkey", "Ankara"), ("Kenya", "Nairobi"),
            ("Vietnam", "Hanoi"), ("Iceland", "Reykjavik"), ("Chile", "Santiago"),
            ("Morocco", "Rabat"), ("Greece", "Athens"), ("Portugal", "Lisbon"),
            ("Finland", "Helsinki"), ("Argentina", "Buenos Aires"),
            ("Thailand", "Bangkok"), ("Norway", "Oslo"), ("Poland", "Warsaw"),
        ]
    ),
    "death_year": tuple(
        WikidataFact(s, "death_year", o) for s, o in [
            ("Albert Einstein", "1955"), ("Isaac Newton", "1727"),
            ("Marie Curie", "1934"), ("Charles Darwin", "1882"),
            ("Galileo Galilei", "1642"), ("Nikola Tesla", "1943"),
            ("Ada Lovelace", "1852"), ("Alan Turing", "1954"),
            ("Stephen Hawking", "2018"), ("Carl Sagan", "1996"),
            ("Niels Bohr", "1962"), ("Pierre Curie", "1906"),
            ("Werner Heisenberg", "1976"), ("Erwin Schrodinger", "1961"),
            ("Linus Pauling", "1994"), ("Barbara McClintock", "1992"),
            ("Lise Meitner", "1968"), ("John von Neumann", "1957"),
            ("Rosalind Franklin", "1958"), ("Dmitri Mendeleev", "1907"),
        ]
    ),
    "author_of": tuple(
        WikidataFact(s, "author_of", o) for s, o in [
            ("Hamlet", "William Shakespeare"), ("Don Quixote", "Miguel de Cervantes"),
            ("Pride and Prejudice", "Jane Austen"),
            ("War and Peace", "Leo Tolstoy"),
            ("Beloved", "Toni Morrison"), ("Ulysses", "James Joyce"),
            ("Beloved", "Toni Morrison"), ("Frankenstein", "Mary Shelley"),
            ("Madame Bovary", "Gustave Flaubert"),
            ("The Brothers Karamazov", "Fyodor Dostoevsky"),
            ("Anna Karenina", "Leo Tolstoy"),
            ("Crime and Punishment", "Fyodor Dostoevsky"),
            ("Moby Dick", "Herman Melville"),
            ("The Great Gatsby", "F Scott Fitzgerald"),
            ("Beloved", "Toni Morrison"), ("Middlemarch", "George Eliot"),
            ("Heart of Darkness", "Joseph Conrad"),
            ("Things Fall Apart", "Chinua Achebe"),
            ("The Stranger", "Albert Camus"), ("Lolita", "Vladimir Nabokov"),
            ("Brave New World", "Aldous Huxley"),
        ]
    ),
    "country_of": tuple(
        WikidataFact(s, "country_of", o) for s, o in [
            ("Mount Fuji", "Japan"), ("Eiffel Tower", "France"),
            ("Statue of Liberty", "United States"), ("Taj Mahal", "India"),
            ("Great Wall", "China"), ("Big Ben", "United Kingdom"),
            ("Pyramids of Giza", "Egypt"), ("Machu Picchu", "Peru"),
            ("Sydney Opera House", "Australia"), ("Acropolis", "Greece"),
            ("Christ the Redeemer", "Brazil"), ("Petra", "Jordan"),
            ("Angkor Wat", "Cambodia"), ("Mont Blanc", "France"),
            ("Kilimanjaro", "Tanzania"), ("Lake Baikal", "Russia"),
            ("Mount Everest", "Nepal"), ("Amazon River", "Brazil"),
            ("Niagara Falls", "Canada"), ("Stonehenge", "United Kingdom"),
        ]
    ),
    "language_of": tuple(
        WikidataFact(s, "language_of", o) for s, o in [
            ("France", "French"), ("Germany", "German"), ("Japan", "Japanese"),
            ("Brazil", "Portuguese"), ("Russia", "Russian"), ("China", "Mandarin"),
            ("Iran", "Persian"), ("Egypt", "Arabic"), ("Vietnam", "Vietnamese"),
            ("Sweden", "Swedish"), ("Greece", "Greek"), ("Turkey", "Turkish"),
            ("Thailand", "Thai"), ("Korea", "Korean"), ("Finland", "Finnish"),
            ("Poland", "Polish"), ("Hungary", "Hungarian"), ("Israel", "Hebrew"),
            ("Iceland", "Icelandic"), ("Mongolia", "Mongolian"),
        ]
    ),
    "inventor_of": tuple(
        WikidataFact(s, "inventor_of", o) for s, o in [
            ("the telephone", "Alexander Graham Bell"),
            ("the light bulb", "Thomas Edison"),
            ("the airplane", "the Wright brothers"),
            ("dynamite", "Alfred Nobel"),
            ("the steam engine", "James Watt"),
            ("the printing press", "Johannes Gutenberg"),
            ("the World Wide Web", "Tim Berners-Lee"),
            ("the cotton gin", "Eli Whitney"),
            ("the radio", "Guglielmo Marconi"),
            ("the polio vaccine", "Jonas Salk"),
            ("the periodic table", "Dmitri Mendeleev"),
            ("the helicopter", "Igor Sikorsky"),
            ("the photograph", "Louis Daguerre"),
            ("the dynamo", "Michael Faraday"),
            ("the transistor", "William Shockley"),
            ("the laser", "Theodore Maiman"),
            ("DNA fingerprinting", "Alec Jeffreys"),
            ("the World Wide Web", "Tim Berners-Lee"),
            ("the computer mouse", "Douglas Engelbart"),
            ("the elevator brake", "Elisha Otis"),
        ]
    ),
    "founded_year": tuple(
        WikidataFact(s, "founded_year", o) for s, o in [
            ("Microsoft", "1975"), ("Apple", "1976"), ("Google", "1998"),
            ("Amazon", "1994"), ("Facebook", "2004"), ("Twitter", "2006"),
            ("Tesla", "2003"), ("SpaceX", "2002"), ("Netflix", "1997"),
            ("Oxford University", "1096"), ("Harvard University", "1636"),
            ("Stanford University", "1885"), ("MIT", "1861"),
            ("Toyota", "1937"), ("Sony", "1946"), ("Samsung", "1938"),
            ("Nestle", "1866"), ("Coca-Cola", "1892"), ("Ford", "1903"),
            ("IBM", "1911"),
        ]
    ),
    "occupation_of": tuple(
        WikidataFact(s, "occupation_of", o) for s, o in [
            ("Marie Curie", "physicist"), ("Frida Kahlo", "painter"),
            ("Beethoven", "composer"), ("Cleopatra", "queen"),
            ("Pythagoras", "mathematician"), ("Aristotle", "philosopher"),
            ("Confucius", "philosopher"), ("Hippocrates", "physician"),
            ("Joan of Arc", "soldier"), ("Charles Dickens", "novelist"),
            ("Mahatma Gandhi", "lawyer"), ("Sigmund Freud", "psychoanalyst"),
            ("Pablo Picasso", "painter"), ("Mozart", "composer"),
            ("Galileo Galilei", "astronomer"), ("Sappho", "poet"),
            ("Hypatia", "mathematician"), ("Augustus", "emperor"),
            ("Genghis Khan", "conqueror"), ("Niccolo Machiavelli", "diplomat"),
        ]
    ),
    "material_of": tuple(
        WikidataFact(s, "material_of", o) for s, o in [
            ("the Eiffel Tower", "iron"), ("Stonehenge", "stone"),
            ("the Statue of Liberty", "copper"),
            ("the Pyramids of Giza", "limestone"),
            ("a wedding ring", "gold"), ("a violin", "wood"),
            ("a window pane", "glass"), ("a circuit board", "silicon"),
            ("a battery cathode", "lithium"),
            ("a clarinet", "wood"), ("a horseshoe", "iron"),
            ("a roof tile", "clay"), ("a wine bottle", "glass"),
            ("a copper wire", "copper"), ("a clay pot", "clay"),
            ("a porcelain cup", "porcelain"), ("a steel beam", "steel"),
            ("a wool sweater", "wool"), ("a leather belt", "leather"),
            ("a plastic bottle", "plastic"),
        ]
    ),
}


# ---------------------------------------------------------------------------
# Coarsening utilities
# ---------------------------------------------------------------------------

def coarsen_density(density: float) -> DensityCoarsening:
    if density < 0.25:
        return "low"
    if density < 0.75:
        return "med"
    return "high"


def coarsen_length(n_tokens: int) -> LengthCoarsening:
    if n_tokens <= 1:
        return "1"
    if n_tokens <= 3:
        return "2-3"
    return "4+"


def count_word_tokens(text: str) -> int:
    """Approximate token count via whitespace split. Real tokenization uses
    the Phi-3 tokenizer; this approximation is acceptable for CEM coarsening
    since the coarsening is robust to off-by-one tokenization differences."""
    return len(text.split())


# ---------------------------------------------------------------------------
# Document construction
# ---------------------------------------------------------------------------

def _build_document(
    fact: WikidataFact,
    template: QuestionTemplate,
    *,
    distractor_facts: list[WikidataFact],
    distractor_templates: list[QuestionTemplate],
    target_evidence_position_words: int,
    rng: random.Random,
) -> tuple[str, int]:
    """Build a document with the evidence statement positioned near
    ``target_evidence_position_words`` (in word-token count).

    Returns ``(document_text, evidence_end_word_idx)``.
    """
    evidence_sentence = template.statement(fact)
    distractor_sentences = [
        dt.statement(df)
        for dt, df in zip(distractor_templates, distractor_facts, strict=False)
    ]

    # Build the document by stacking distractor sentences before the evidence
    # until we reach the target evidence-position word count, then append the
    # evidence sentence, then continue stacking distractors.
    pre_sentences: list[str] = []
    pre_words = 0
    di = 0
    while pre_words < target_evidence_position_words and di < len(distractor_sentences):
        pre_sentences.append(distractor_sentences[di])
        pre_words += count_word_tokens(distractor_sentences[di])
        di += 1

    pre_text = " ".join(pre_sentences)
    pre_words = count_word_tokens(pre_text)
    evidence_words = count_word_tokens(evidence_sentence)
    evidence_end_idx = pre_words + evidence_words

    post_sentences = distractor_sentences[di:]
    rng.shuffle(post_sentences)
    post_text = " ".join(post_sentences)

    parts = []
    if pre_text:
        parts.append(pre_text)
    parts.append(evidence_sentence)
    if post_text:
        parts.append(post_text)

    document = " ".join(parts)
    return document, evidence_end_idx


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_event(
    *,
    template: QuestionTemplate,
    fact: WikidataFact,
    target_evidence_distance_words: int,
    distractor_density: float,
    prompt_template_sha256: str,
    bin_id: BinId,
    adversariality_policy: AdversarialityPolicy = "none",
    rng: random.Random,
) -> DocQAEvent:
    """Generate one ``DocQAEvent`` with placeholder model output fields.

    The pipeline downstream fills ``model_generation``,
    ``model_generation_normalized``, and ``is_fail`` after the forward pass.

    Args:
        template: One of the 10 templates.
        fact: A WikidataFact whose ``predicate == template.template_id``.
        target_evidence_distance_words: Desired evidence-distance in word
            tokens (approximate, refined by tokenizer at pipeline time).
        distractor_density: Float in [0, 1]; coarsened to low/med/high.
        prompt_template_sha256: SHA256 of the prompt template string (FR-011).
        bin_id: Pre-assigned bin (caller responsibility).
        adversariality_policy: Per-bin policy (B1 may use non-"none").
        rng: Seeded RNG for distractor selection.
    """
    # Pick distractors: pull facts from OTHER templates so the distractor
    # sentences are off-topic relative to the question.
    other_facts: list[WikidataFact] = []
    other_templates: list[QuestionTemplate] = []
    for other in TEMPLATES:
        if other.template_id == template.template_id:
            continue
        for f in FACTS[other.template_id]:
            other_facts.append(f)
            other_templates.append(other)
    # Shuffle and trim to the target density.
    paired = list(zip(other_templates, other_facts, strict=True))
    rng.shuffle(paired)
    n_distractors = max(1, int(distractor_density * len(paired)))
    paired = paired[:n_distractors]
    distractor_templates = [p[0] for p in paired]
    distractor_facts = [p[1] for p in paired]

    document, evidence_end_idx = _build_document(
        fact, template,
        distractor_facts=distractor_facts,
        distractor_templates=distractor_templates,
        target_evidence_position_words=max(0, target_evidence_distance_words),
        rng=rng,
    )

    question = template.question(fact)
    gold = fact.object

    event_id = compute_event_id(
        prompt_template_sha256=prompt_template_sha256,
        document=document,
        question=question,
        gold_answer=gold,
    )

    distance_coarse = coarsen_density(distractor_density)
    gold_len = count_word_tokens(gold)
    length_coarse = coarsen_length(gold_len)
    stratum_id = f"{template.template_id}|{distance_coarse}|{length_coarse}"

    return DocQAEvent(
        event_id=event_id,
        document=document,
        question=question,
        gold_answer=gold,
        question_template_id=template.template_id,
        evidence_position_token_idx=evidence_end_idx,  # word approximation
        evidence_distance_tokens=target_evidence_distance_words,  # set precisely by pipeline
        bin_id=bin_id,
        distractor_density=distractor_density,
        distractor_density_coarsening=distance_coarse,
        gold_answer_length_tokens=gold_len,
        gold_answer_length_coarsening=length_coarse,
        cem_stratum_id=stratum_id,
        adversariality_policy=adversariality_policy,
        model_generation="",  # filled by pipeline
        model_generation_normalized="",  # filled by pipeline
        gold_answer_normalized=normalize_em(gold),
        is_fail=False,  # filled by pipeline
        per_event_seed=seed_for_event(event_id),
    )
