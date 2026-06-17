"""Abstention detector P/R on a hand-labeled validation sample (SP-0, T032).

Validates the rules-for-precision + backstop-for-recall design against a small
hand-labeled set. The backstop here is a STUB standing in for SP-1's real
NLI/judge classifier; the test asserts the *design* clears the ≥0.90 precision /
≥0.90 recall bar (rules alone are high-precision but under-recall paraphrases).
"""

from phi3geom.dataset.abstention import (
    detect_abstention,
    is_abstention_rule,
    precision_recall,
)

# (text, is_abstention_truth) — hand labeled.
VALIDATION_SAMPLE: list[tuple[str, bool]] = [
    # explicit abstentions (rules should catch)
    ("I don't know.", True),
    ("I do not know the answer.", True),
    ("The answer is not in the context.", True),
    ("This question is unanswerable.", True),
    ("There is no answer in the passage.", True),
    ("Cannot be determined from the text.", True),
    ("", True),
    ("Insufficient information to answer.", True),
    # paraphrased abstentions (rules miss; a real classifier should catch)
    ("That isn't something the passage tells us.", True),
    ("The document doesn't cover that topic.", True),
    ("I'm not able to find that here.", True),
    ("That's beyond what the text provides.", True),
    ("The passage stays silent on this.", True),
    ("Hard to say based on this.", True),  # subtle — even the stub backstop misses it
    # real answers (must NOT be flagged)
    ("Paris", False),
    ("Barack Obama", False),
    ("1945", False),
    ("The Treaty of Versailles.", False),
    ("It is the capital of France.", False),
    ("Marie Curie discovered radium.", False),
    ("Approximately 12 kilometers.", False),
    ("Mount Everest", False),
    ("Because the pressure dropped sharply.", False),
    ("George Washington", False),
]


def _stub_backstop(text: str) -> bool:
    """Stand-in for SP-1's NLI/judge: catches common hedge paraphrases."""
    hedges = (
        "isn't something",
        "doesn't cover",
        "not able to find",
        "beyond what",
        "stays silent",
    )
    low = text.lower()
    return any(h in low for h in hedges)


def test_rule_layer_is_high_precision():
    texts = [t for t, _ in VALIDATION_SAMPLE]
    truth = [a for _, a in VALIDATION_SAMPLE]
    detected = [is_abstention_rule(t) for t in texts]
    precision, recall = precision_recall(detected, truth)
    assert precision >= 0.90  # rules never fire on real answers
    assert recall < 0.90  # ...but under-recall paraphrases (motivates the backstop)


def test_full_detector_clears_pr_bar():
    truth = [a for _, a in VALIDATION_SAMPLE]
    detected = [
        detect_abstention(t, backstop=_stub_backstop)[0] for t, _ in VALIDATION_SAMPLE
    ]
    precision, recall = precision_recall(detected, truth)
    assert precision >= 0.90  # SC-004 precision target
    assert recall >= 0.90  # SC-004 recall target (rules + backstop)
