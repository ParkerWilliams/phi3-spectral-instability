"""generate(): the pure, deterministic generation entry point.

``generate(seed, params)`` builds params -> layout -> geometry -> entities ->
:class:`MapModel`, runs :func:`verify`, and on failure **rejects** the model and
retries with a derived seed (``seed + 1`` ...), up to ``MAX_ATTEMPTS`` tries.
For a given ``(seed, params)`` the output is identical every time (research R7).
"""

from __future__ import annotations

from dataclasses import replace

from idledoom_mapgen.entities import place_entities
from idledoom_mapgen.geometry import build_brushes
from idledoom_mapgen.layout import layout
from idledoom_mapgen.model import MapModel
from idledoom_mapgen.params import GenParams
from idledoom_mapgen.verify import verify

MAX_ATTEMPTS = 20


class GenerationError(RuntimeError):
    """Raised when no valid level is found within ``MAX_ATTEMPTS`` tries."""


def generate(seed: int, params: GenParams | None = None) -> MapModel:
    """Generate a verified :class:`MapModel` for ``seed``.

    ``params`` defaults to clamped catalogue defaults for ``seed``. On a
    verification failure the seed is derived forward (``seed + attempt``) and the
    build is retried; after ``MAX_ATTEMPTS`` exhausted, ``GenerationError`` is
    raised. The returned model always passes :func:`verify`.
    """
    base = params.clamped() if params is not None else GenParams.from_seed(seed)

    last_problems: list[str] = []
    for attempt in range(MAX_ATTEMPTS):
        derived_seed = seed + attempt
        attempt_params = replace(base, seed=derived_seed)
        model = _build_once(attempt_params)
        problems = verify(model)
        if not problems:
            return model
        last_problems = problems

    raise GenerationError(
        f"no valid level for seed={seed} after {MAX_ATTEMPTS} attempts; "
        f"last problems: {last_problems}"
    )


def attempts_for(seed: int, params: GenParams | None = None) -> int:
    """How many attempts ``generate(seed, params)`` needs (1 == first try).

    A test/diagnostic helper that mirrors :func:`generate` exactly so batch
    tests can measure the first-attempt success rate without re-implementing the
    retry loop.
    """
    base = params.clamped() if params is not None else GenParams.from_seed(seed)
    for attempt in range(MAX_ATTEMPTS):
        attempt_params = replace(base, seed=seed + attempt)
        if not verify(_build_once(attempt_params)):
            return attempt + 1
    raise GenerationError(f"no valid level for seed={seed} after {MAX_ATTEMPTS} attempts")


def _build_once(params: GenParams) -> MapModel:
    """One generation pass for fully-resolved ``params`` (single rng)."""
    rng = params.rng()
    rooms, edges, grid = layout(params, rng)
    brushes = build_brushes(grid, params)
    entities = place_entities(rooms, grid, params, rng)
    return MapModel(
        params=params,
        rooms=rooms,
        edges=edges,
        grid=grid,
        brushes=brushes,
        entities=entities,
    )
