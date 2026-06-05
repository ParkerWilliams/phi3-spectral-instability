"""GenParams: the generation knobs, with clamping and seed-derived RNG.

``GenParams`` is the frozen set of tunables (data-model.md "GenParams"). All
fields are clamped to sane ranges via :meth:`GenParams.clamped`; the only
entropy source for the whole generator is ``random.Random(seed)`` (research R7).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, fields, replace
from typing import Any

# Bounds used by clamping. Kept conservative so a clamped GenParams always
# produces a layout that can fit on its grid with a 1-cell wall margin.
_MIN_GRID = 8
_MAX_GRID = 256
_MIN_CELL = 16
_MAX_CELL = 256
_MIN_ROOM = 2
_MIN_CEILING = 96


@dataclass(frozen=True)
class GenParams:
    """Immutable generation parameters. Use :meth:`from_seed` to build one."""

    seed: int
    grid_w: int = 24
    grid_h: int = 24
    cell: int = 64
    room_count: int = 8
    room_min: int = 3
    room_max: int = 7
    corridor_w: int = 2
    loopiness: float = 0.2
    ceiling: int = 192
    monster_density: float = 0.5
    item_density: float = 0.4

    def clamped(self) -> GenParams:
        """Return a copy with every field forced into a sane, mutually
        consistent range (data-model.md "Validation").
        """
        grid_w = _clamp_int(self.grid_w, _MIN_GRID, _MAX_GRID)
        grid_h = _clamp_int(self.grid_h, _MIN_GRID, _MAX_GRID)
        cell = _clamp_int(self.cell, _MIN_CELL, _MAX_CELL)
        ceiling = max(int(self.ceiling), _MIN_CEILING)

        # Rooms must fit on the grid leaving a 1-cell wall margin on every side,
        # so the largest a room may be is (grid - 2) cells in either axis.
        max_fit = max(_MIN_ROOM, min(grid_w, grid_h) - 2)
        room_min = _clamp_int(self.room_min, _MIN_ROOM, max_fit)
        room_max = _clamp_int(self.room_max, room_min, max_fit)

        # Corridors must be wide enough for the player (>= 2 cells) and must
        # also fit inside the playable area.
        corridor_w = _clamp_int(self.corridor_w, 2, max_fit)

        room_count = _clamp_int(self.room_count, 1, _max_rooms(grid_w, grid_h, room_min))

        loopiness = _clamp_float(self.loopiness, 0.0, 4.0)
        monster_density = _clamp_float(self.monster_density, 0.0, 1.0)
        item_density = _clamp_float(self.item_density, 0.0, 1.0)

        return replace(
            self,
            grid_w=grid_w,
            grid_h=grid_h,
            cell=cell,
            room_count=room_count,
            room_min=room_min,
            room_max=room_max,
            corridor_w=corridor_w,
            loopiness=loopiness,
            ceiling=ceiling,
            monster_density=monster_density,
            item_density=item_density,
        )

    def rng(self) -> random.Random:
        """The single seeded entropy source threaded through generation."""
        return random.Random(self.seed)

    @classmethod
    def from_seed(cls, seed: int, overrides: dict[str, str] | None = None) -> GenParams:
        """Build clamped params for ``seed``, applying string ``overrides``
        (CLI ``--params k=v``). Unknown keys raise ``KeyError``; unparsable
        values raise ``ValueError``.
        """
        params = cls(seed=seed)
        if overrides:
            kwargs: dict[str, Any] = {}
            field_types = {f.name: f.type for f in fields(cls)}
            for key, raw in overrides.items():
                if key not in field_types or key == "seed":
                    raise KeyError(f"unknown GenParams override: {key!r}")
                kwargs[key] = _coerce(field_types[key], raw)
            params = replace(params, **kwargs)
        return params.clamped()


def _coerce(field_type: object, raw: str) -> int | float:
    """Coerce a CLI string to the int/float a GenParams field expects."""
    # Dataclass field types come through as strings under ``from __future__
    # import annotations``; match on the textual type name.
    name = field_type if isinstance(field_type, str) else getattr(field_type, "__name__", "")
    if name == "int":
        return int(raw)
    if name == "float":
        return float(raw)
    raise ValueError(f"cannot coerce {raw!r} to {name}")


def _clamp_int(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(value)))


def _clamp_float(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _max_rooms(grid_w: int, grid_h: int, room_min: int) -> int:
    """An upper bound on how many ``room_min``-sized rooms could pack a grid.

    Generous (ignores the corridor/margin slack) — placement gives up early if
    it cannot actually fit this many; this just keeps ``room_count`` finite.
    """
    per = room_min + 1  # rough footprint incl. a separating cell
    return max(1, (grid_w // per) * (grid_h // per))
