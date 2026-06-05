"""Layout: room placement, connectivity graph, and grid rasterisation.

``layout(params, rng)`` ties the three steps together (data-model.md
"RoomGraph" / "Grid"):

1. :func:`place_rooms` — non-overlapping rooms, sized in ``[room_min, room_max]``,
   kept a 1-cell margin from the grid border so walls fit.
2. :func:`connect` — an MST over room centers (by euclidean distance) plus
   ``floor(loopiness * n)`` extra edges for loops.
3. :func:`rasterize` — room cells plus L-shaped corridors of width ``corridor_w``
   stamped into a :class:`Grid`.
"""

from __future__ import annotations

import math
import random

from idledoom_mapgen.model import Cell, Edge, Grid, Room
from idledoom_mapgen.params import GenParams

# How hard placement tries before giving up on the target room_count.
_PLACE_ATTEMPTS_PER_ROOM = 40


def place_rooms(params: GenParams, rng: random.Random) -> list[Room]:
    """Place up to ``params.room_count`` non-overlapping rooms.

    Rooms are square-ish (independent w/h in ``[room_min, room_max]``), kept one
    cell off every grid edge so a wall ring always fits, and separated by at
    least one solid cell so corridors have something to carve. Returns however
    many fit (always >= 1; caller/verify rejects degenerate layouts).
    """
    rooms: list[Room] = []
    placed_cells: set[Cell] = set()
    # Playable interior: [1, grid - 1) leaves the border solid for the shell.
    lo = 1
    hi_x = params.grid_w - 1
    hi_y = params.grid_h - 1

    attempts = params.room_count * _PLACE_ATTEMPTS_PER_ROOM
    for _ in range(attempts):
        if len(rooms) >= params.room_count:
            break
        w = rng.randint(params.room_min, params.room_max)
        h = rng.randint(params.room_min, params.room_max)
        if w > hi_x - lo or h > hi_y - lo:
            continue
        x = rng.randint(lo, hi_x - w)
        y = rng.randint(lo, hi_y - h)
        candidate = Room(id=len(rooms), x=x, y=y, w=w, h=h)
        if _overlaps(candidate, placed_cells):
            continue
        rooms.append(candidate)
        placed_cells.update(_padded_cells(candidate, params.grid_w, params.grid_h))
    return rooms


def connect(rooms: list[Room], params: GenParams, rng: random.Random) -> list[Edge]:
    """An MST over room centers + ``floor(loopiness * n)`` extra edges.

    The MST guarantees connectivity (data-model.md "RoomGraph" validation);
    extra edges are the shortest non-tree pairs, added for loops. Edges are
    normalised ``(min_id, max_id)`` and deduplicated.
    """
    n = len(rooms)
    if n <= 1:
        return []

    centers = [r.center for r in rooms]
    # Sorted list of all candidate edges by euclidean center distance; ties
    # broken by (a, b) for determinism.
    candidates: list[tuple[float, int, int]] = []
    for a in range(n):
        for b in range(a + 1, n):
            candidates.append((_dist(centers[a], centers[b]), a, b))
    candidates.sort()

    # Kruskal MST.
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> bool:
        ri, rj = find(i), find(j)
        if ri == rj:
            return False
        parent[ri] = rj
        return True

    edges: list[Edge] = []
    in_tree: set[Edge] = set()
    leftovers: list[Edge] = []
    for _, a, b in candidates:
        key = (a, b)
        if union(a, b):
            edges.append(key)
            in_tree.add(key)
        else:
            leftovers.append(key)

    extra = math.floor(params.loopiness * n)
    # leftovers is already in ascending-distance order (candidates were sorted).
    for key in leftovers:
        if extra <= 0:
            break
        if key in in_tree:
            continue
        edges.append(key)
        extra -= 1

    return edges


def rasterize(rooms: list[Room], edges: list[Edge], params: GenParams, rng: random.Random) -> Grid:
    """Stamp rooms and L-shaped corridors into a fresh :class:`Grid`."""
    grid = Grid.solid(params.grid_w, params.grid_h)
    for room in rooms:
        for cell in room.cells():
            grid.set_open(cell)

    for a, b in edges:
        _carve_corridor(grid, rooms[a].center, rooms[b].center, params.corridor_w, rng)
    return grid


def layout(params: GenParams, rng: random.Random) -> tuple[list[Room], list[Edge], Grid]:
    """Run placement -> connectivity -> rasterisation with one shared rng."""
    rooms = place_rooms(params, rng)
    edges = connect(rooms, params, rng)
    grid = rasterize(rooms, edges, params, rng)
    return rooms, edges, grid


# --- helpers ---------------------------------------------------------------


def _overlaps(room: Room, occupied: set[Cell]) -> bool:
    return any(cell in occupied for cell in room.cells())


def _padded_cells(room: Room, grid_w: int, grid_h: int) -> set[Cell]:
    """Room cells plus a 1-cell skirt, clipped to the grid — enforces a solid
    separator between rooms so corridors are meaningful.
    """
    cells: set[Cell] = set()
    for cx in range(room.x - 1, room.x + room.w + 1):
        for cy in range(room.y - 1, room.y + room.h + 1):
            if 0 <= cx < grid_w and 0 <= cy < grid_h:
                cells.add((cx, cy))
    return cells


def _dist(a: Cell, b: Cell) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _carve_corridor(grid: Grid, a: Cell, b: Cell, width: int, rng: random.Random) -> None:
    """Carve an L-shaped corridor of ``width`` cells between two centers.

    Randomly chooses the horizontal-first or vertical-first elbow. The corridor
    is a band ``width`` cells wide centered on the path; cells are clipped so the
    solid border ring (col/row 0 and grid-1) is never opened, preserving the
    seal.
    """
    horizontal_first = rng.random() < 0.5
    if horizontal_first:
        _carve_h(grid, a[1], a[0], b[0], width)
        _carve_v(grid, b[0], a[1], b[1], width)
    else:
        _carve_v(grid, a[0], a[1], b[1], width)
        _carve_h(grid, b[1], a[0], b[0], width)


def _carve_h(grid: Grid, y: int, x0: int, x1: int, width: int) -> None:
    """Open a horizontal band at row ``y`` from ``x0`` to ``x1`` (inclusive)."""
    lo, hi = (x0, x1) if x0 <= x1 else (x1, x0)
    for x in range(lo, hi + 1):
        _open_band(grid, x, y, width, vertical=False)


def _carve_v(grid: Grid, x: int, y0: int, y1: int, width: int) -> None:
    """Open a vertical band at col ``x`` from ``y0`` to ``y1`` (inclusive)."""
    lo, hi = (y0, y1) if y0 <= y1 else (y1, y0)
    for y in range(lo, hi + 1):
        _open_band(grid, x, y, width, vertical=True)


def _open_band(grid: Grid, x: int, y: int, width: int, vertical: bool) -> None:
    """Open a ``width``-thick band perpendicular to the corridor direction,
    centered on ``(x, y)`` and clipped to keep the border ring solid.
    """
    half = width // 2
    start = -half
    end = width - half  # exclusive; yields exactly ``width`` offsets
    for off in range(start, end):
        cx, cy = (x, y + off) if vertical else (x + off, y)
        # Never open the outer border ring — it is the seal.
        if 1 <= cx < grid.w - 1 and 1 <= cy < grid.h - 1:
            grid.set_open((cx, cy))
