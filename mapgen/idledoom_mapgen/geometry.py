"""Geometry: grid -> sealed brush set (research R6).

``build_brushes(grid, params)`` emits:

* one **floor slab** and one **ceiling slab** spanning the full grid bbox, and
* **wall brushes** for every solid cell that is 4-adjacent to an open cell,
  greedily merged into maximal horizontal runs per row to keep the brush count
  down.

Building walls from solid-cells-bordering-open guarantees a closed hull by
construction (no leaks), provided the open set never touches the grid border
(enforced in :mod:`idledoom_mapgen.layout`).
"""

from __future__ import annotations

from idledoom_mapgen.model import Brush, Grid
from idledoom_mapgen.params import GenParams

FLOOR_TEX = "floor0_1"
CEILING_TEX = "ceil1_1"
WALL_TEX = "wall0_1"

_SLAB_THICKNESS = 16

_NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def build_brushes(grid: Grid, params: GenParams) -> list[Brush]:
    """All world brushes for ``grid``: floor slab, ceiling slab, and walls."""
    c = params.cell
    floor_z = 0
    ceiling_z = params.ceiling

    world_w = grid.w * c
    world_h = grid.h * c

    brushes: list[Brush] = []

    # Floor slab: sits below z=0, top face at the floor plane.
    brushes.append(
        Brush(
            mins=(0, 0, -_SLAB_THICKNESS),
            maxs=(world_w, world_h, floor_z),
            tex=FLOOR_TEX,
        )
    )
    # Ceiling slab: sits above the room, bottom face at the ceiling plane.
    brushes.append(
        Brush(
            mins=(0, 0, ceiling_z),
            maxs=(world_w, world_h, ceiling_z + _SLAB_THICKNESS),
            tex=CEILING_TEX,
        )
    )

    brushes.extend(_wall_brushes(grid, params, floor_z, ceiling_z))
    return brushes


def _wall_brushes(grid: Grid, params: GenParams, floor_z: int, ceiling_z: int) -> list[Brush]:
    """Full-height wall brushes for boundary solid cells, merged per row."""
    c = params.cell
    brushes: list[Brush] = []
    for y in range(grid.h):
        x = 0
        while x < grid.w:
            if not _is_wall_cell(grid, x, y):
                x += 1
                continue
            # Greedily extend a maximal horizontal run of wall cells.
            run_start = x
            while x < grid.w and _is_wall_cell(grid, x, y):
                x += 1
            run_end = x  # exclusive
            brushes.append(
                Brush(
                    mins=(run_start * c, y * c, floor_z),
                    maxs=(run_end * c, (y + 1) * c, ceiling_z),
                    tex=WALL_TEX,
                )
            )
    return brushes


def _is_wall_cell(grid: Grid, x: int, y: int) -> bool:
    """A solid cell that is 4-adjacent to at least one open cell."""
    if grid.open[x][y]:
        return False
    for dx, dy in _NEIGHBORS:
        if grid.is_open((x + dx, y + dy)):
            return True
    return False
