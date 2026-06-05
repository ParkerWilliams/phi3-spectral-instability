"""Static verification of a :class:`MapModel` (data-model.md "Invariants").

``verify(model)`` returns a list of human-readable problem strings; an empty
list means the model is valid and may be emitted. A non-empty list means the
caller must reject + reseed (the model is never written).
"""

from __future__ import annotations

from collections import deque

from idledoom_mapgen.entities import (
    ITEM_CLASSES,
    MONSTER_CLASSES,
    SPAWN_CLASS,
)
from idledoom_mapgen.model import Cell, Grid, MapEntity, MapModel, Room

_NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))
_ITEM_PREFIXES = ("item_", "weapon_")


def verify(model: MapModel) -> list[str]:
    """Run every static invariant; empty result == valid."""
    problems: list[str] = []
    problems.extend(_check_spawn_safe(model))
    problems.extend(_check_reachability(model))
    problems.extend(_check_content_reachable(model))
    problems.extend(_check_no_overlap(model))
    problems.extend(_check_sealed(model))
    return problems


# --- individual checks -----------------------------------------------------


def _check_reachability(model: MapModel) -> list[str]:
    """Flood-fill open from the spawn cell must equal the full open set."""
    spawn = _spawn_cell(model)
    if spawn is None:
        return ["reachability: no info_player_start to flood-fill from"]

    open_set = set(model.grid.open_cells)
    if spawn not in open_set:
        return ["reachability: spawn cell is not open"]

    reached = _flood_fill(model.grid, spawn)
    if reached != open_set:
        missing = len(open_set - reached)
        return [f"reachability: {missing} open cell(s) unreachable from spawn"]
    return []


def _check_spawn_safe(model: MapModel) -> list[str]:
    """Exactly one spawn; its room is monster-free."""
    spawns = [e for e in model.entities if e.classname == SPAWN_CLASS]
    if len(spawns) != 1:
        return [f"spawn_safe: expected exactly 1 {SPAWN_CLASS}, found {len(spawns)}"]

    spawn_cell = _entity_cell(model, spawns[0])
    spawn_room = _room_of_cell(model.rooms, spawn_cell)
    if spawn_room is None:
        return ["spawn_safe: spawn is not inside any room"]

    problems: list[str] = []
    for ent in model.entities:
        if ent.classname in MONSTER_CLASSES:
            if spawn_room.contains(_entity_cell(model, ent)):
                problems.append("spawn_safe: a monster shares the spawn room")
                break
    return problems


def _check_content_reachable(model: MapModel) -> list[str]:
    """Every monster/item sits in a reachable open cell."""
    spawn = _spawn_cell(model)
    if spawn is None:
        return ["content_reachable: no spawn to measure reachability from"]
    reached = _flood_fill(model.grid, spawn)

    problems: list[str] = []
    for ent in model.entities:
        if _is_content(ent):
            cell = _entity_cell(model, ent)
            if cell not in reached:
                problems.append(f"content_reachable: {ent.classname} at {cell} is unreachable")
    return problems


def _check_no_overlap(model: MapModel) -> list[str]:
    """No two entities share a cell; none sits in a wall (non-open) cell."""
    problems: list[str] = []
    seen: dict[Cell, str] = {}
    for ent in model.entities:
        cell = _entity_cell(model, ent)
        if not model.grid.is_open(cell):
            problems.append(f"no_overlap: {ent.classname} at {cell} is inside a wall cell")
        if cell in seen:
            problems.append(
                f"no_overlap: {ent.classname} and {seen[cell]} share cell {cell}"
            )
        else:
            seen[cell] = ent.classname
    return problems


def _check_sealed(model: MapModel) -> list[str]:
    """Every open cell whose 4-neighbor is non-open must have that neighbor in
    the emitted wall-cell set (the hull is closed).
    """
    grid = model.grid
    wall_cells = _emitted_wall_cells(model)
    problems: list[str] = []
    for cx, cy in grid.open_cells:
        for dx, dy in _NEIGHBORS:
            nb = (cx + dx, cy + dy)
            if not grid.is_open(nb):
                if not grid.in_bounds(nb):
                    problems.append(f"sealed: open cell {(cx, cy)} touches the grid border")
                    break
                if nb not in wall_cells:
                    problems.append(
                        f"sealed: open cell {(cx, cy)} borders unsealed cell {nb}"
                    )
                    break
    return problems


# --- helpers ---------------------------------------------------------------


def _flood_fill(grid: Grid, start: Cell) -> set[Cell]:
    if not grid.is_open(start):
        return set()
    seen: set[Cell] = {start}
    queue: deque[Cell] = deque([start])
    while queue:
        cx, cy = queue.popleft()
        for dx, dy in _NEIGHBORS:
            nb = (cx + dx, cy + dy)
            if nb not in seen and grid.is_open(nb):
                seen.add(nb)
                queue.append(nb)
    return seen


def _emitted_wall_cells(model: MapModel) -> set[Cell]:
    """Reconstruct the wall-cell set the geometry pass emits: solid cells that
    are 4-adjacent to an open cell.
    """
    grid = model.grid
    cells: set[Cell] = set()
    for x in range(grid.w):
        for y in range(grid.h):
            if grid.open[x][y]:
                continue
            for dx, dy in _NEIGHBORS:
                if grid.is_open((x + dx, y + dy)):
                    cells.add((x, y))
                    break
    return cells


def _spawn_cell(model: MapModel) -> Cell | None:
    for ent in model.entities:
        if ent.classname == SPAWN_CLASS:
            return _entity_cell(model, ent)
    return None


def _entity_cell(model: MapModel, ent: MapEntity) -> Cell:
    """World origin -> grid cell (inverse of entities._world_origin)."""
    c = model.params.cell
    return (ent.origin[0] // c, ent.origin[1] // c)


def _room_of_cell(rooms: list[Room], cell: Cell) -> Room | None:
    for room in rooms:
        if room.contains(cell):
            return room
    return None


def _is_content(ent: MapEntity) -> bool:
    return ent.classname in MONSTER_CLASSES or ent.classname in ITEM_CLASSES or any(
        ent.classname.startswith(p) for p in _ITEM_PREFIXES
    )
