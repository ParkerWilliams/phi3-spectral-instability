"""Tests for ``phi3geom.dataset.normalization`` (Spec FR-002).

Golden table of inputs → expected normalized outputs, exercising each step of
the 6-step pipeline independently and end-to-end.
"""

from __future__ import annotations

import pytest

from phi3geom.dataset.normalization import is_fail, normalize_em


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Identity on a clean canonical answer.
        ("eiffel tower", "eiffel tower"),
        # Step 1 (NFKC) — full-width digit collapses to ASCII.
        ("１２３", "123"),
        # Step 1 (NFKC) — ligature.
        ("ﬁle", "file"),
        # Step 2 (lowercase).
        ("EIFFEL TOWER", "eiffel tower"),
        # Step 3 (strip leading whitespace + punctuation).
        ("   Eiffel Tower", "eiffel tower"),
        ('"Eiffel Tower"', "eiffel tower"),
        ("...Eiffel Tower", "eiffel tower"),
        # Step 4 (strip leading articles).
        ("The Eiffel Tower", "eiffel tower"),
        ("A cat", "cat"),
        ("an apple", "apple"),
        # Step 4: articles only stripped when followed by space (word boundary).
        # "the" is the prefix here, not the article, so it should remain.
        ("theory", "theory"),
        # Step 5 (collapse whitespace).
        ("Eiffel    Tower", "eiffel tower"),
        ("Eiffel\tTower", "eiffel tower"),
        ("Eiffel\n\nTower", "eiffel tower"),
        # Step 6 (strip trailing punctuation + whitespace).
        ("Eiffel Tower.", "eiffel tower"),
        ("Eiffel Tower!!!", "eiffel tower"),
        ("Eiffel Tower   ", "eiffel tower"),
        # Full pipeline.
        ("  The Eiffel Tower.", "eiffel tower"),
        ('   "The   Eiffel  Tower!"   ', "eiffel tower"),
        # Empty / whitespace-only inputs.
        ("", ""),
        ("   ", ""),
        ("...", ""),
    ],
)
def test_normalize_em_golden(text: str, expected: str) -> None:
    assert normalize_em(text) == expected


def test_only_first_leading_article_stripped() -> None:
    # If the text is literally "the the cat", we strip the first "the" only.
    assert normalize_em("the the cat") == "the cat"


def test_is_fail_basic() -> None:
    assert is_fail("Paris.", "Paris") is False
    assert is_fail("paris", "  The Paris  ") is False
    assert is_fail("London", "Paris") is True
    assert is_fail("", "Paris") is True


def test_normalize_is_idempotent() -> None:
    # Normalizing twice should be a no-op.
    examples = ["The Eiffel Tower.", "  PARIS!  ", "an apple", "theory"]
    for ex in examples:
        once = normalize_em(ex)
        twice = normalize_em(once)
        assert once == twice
