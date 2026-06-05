"""Batch robustness: 50 seeds all succeed and >=95% need no reseed (SC-006)."""

from __future__ import annotations

from idledoom_mapgen.generate import attempts_for, generate
from idledoom_mapgen.verify import verify

BATCH_SEEDS = list(range(1, 51))


def test_all_seeds_generate_and_verify() -> None:
    for seed in BATCH_SEEDS:
        model = generate(seed)
        assert verify(model) == [], f"seed {seed} produced an invalid model"


def test_first_attempt_success_rate() -> None:
    attempts = [attempts_for(seed) for seed in BATCH_SEEDS]
    first_try = sum(1 for a in attempts if a == 1)
    rate = first_try / len(BATCH_SEEDS)
    assert rate >= 0.95, f"first-attempt success rate {rate:.2%} < 95% (attempts={attempts})"
