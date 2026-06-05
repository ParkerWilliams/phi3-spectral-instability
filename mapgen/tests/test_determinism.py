"""Determinism: same (seed, params) -> identical MapModel and .map text."""

from __future__ import annotations

import pytest

from idledoom_mapgen.generate import generate
from idledoom_mapgen.mapfile import emit_map
from idledoom_mapgen.params import GenParams

SEEDS = [0, 1, 5, 42, 12345, 99999]


@pytest.mark.parametrize("seed", SEEDS)
def test_model_is_deterministic(seed: int) -> None:
    a = generate(seed)
    b = generate(seed)
    assert a == b


@pytest.mark.parametrize("seed", SEEDS)
def test_map_text_is_byte_identical(seed: int) -> None:
    a = emit_map(generate(seed))
    b = emit_map(generate(seed))
    assert a == b


def test_overrides_are_deterministic() -> None:
    params = GenParams.from_seed(7, {"room_count": "12", "loopiness": "0.35"})
    a = generate(7, params)
    b = generate(7, params)
    assert a == b
    assert emit_map(a) == emit_map(b)


def test_different_seeds_differ() -> None:
    # Sanity: the generator actually varies across seeds (not a constant).
    texts = {emit_map(generate(s)) for s in SEEDS}
    assert len(texts) == len(SEEDS)
