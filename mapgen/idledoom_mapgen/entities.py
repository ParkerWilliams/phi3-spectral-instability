"""Entities: spawn / monsters / items / lights placement (research R5).

``place_entities`` enforces the data-model.md invariants up front:

* exactly **one** ``info_player_start``, floor-centered in a chosen room, with
  that room kept **monster-free**;
* monsters cycle ``monster_army`` / ``monster_dog`` / ``monster_knight`` in the
  *other* rooms, expected count per room ``monster_density``;
* items cycle ``item_health`` / ``item_shells`` / ``weapon_supershotgun`` per
  room, expected count ``item_density``;
* one ``light`` per room near the ceiling (``extras={"light": 200}``);
* no two entities occupy the same cell (tracked via an occupied set).
"""

from __future__ import annotations

import random

from idledoom_mapgen.model import Cell, Grid, MapEntity, Room, Vec3
from idledoom_mapgen.params import GenParams

SPAWN_CLASS = "info_player_start"
MONSTER_CLASSES = ("monster_army", "monster_dog", "monster_knight")
ITEM_CLASSES = ("item_health", "item_shells", "weapon_supershotgun")
LIGHT_CLASS = "light"

# Origin offset above the floor. Must clear the player CLIP-HULL floor seam: the
# standing hull bottom is -24, so in hull 1/2 the floor inflates up to z=24 and an
# origin sitting exactly at +24 lands on the seam -> qbsp can't seed the hull fill
# ("WARNING 19: no entities in empty space"), and the agent would fall through floors.
# +40 puts the fill-seed entities clearly inside the collision-hull empty space; they
# (and monsters/items, which droptofloor) settle onto the floor in-game.
_STAND_OFFSET = 40
_LIGHT_BRIGHTNESS = 200


def place_entities(
    rooms: list[Room],
    grid: Grid,
    params: GenParams,
    rng: random.Random,
) -> list[MapEntity]:
    """Populate the level; deterministic for a given ``rng`` state."""
    entities: list[MapEntity] = []
    occupied: set[Cell] = set()

    if not rooms:
        return entities

    spawn_room = rng.choice(rooms)
    spawn_cell = spawn_room.center
    # If the center somehow is not open (shouldn't happen — rooms are solid
    # rectangles), fall back to the first open cell of the room.
    if not grid.is_open(spawn_cell):
        spawn_cell = _first_open_cell(spawn_room, grid) or spawn_cell
    entities.append(MapEntity(SPAWN_CLASS, _world_origin(spawn_cell, params, _STAND_OFFSET)))
    occupied.add(spawn_cell)

    monster_cycle = 0
    item_cycle = 0
    for room in rooms:
        # Light: one per room, near the ceiling, at the room center cell.
        light_cell = _free_cell_in_room(room, grid, occupied, rng) or room.center
        entities.append(
            MapEntity(
                LIGHT_CLASS,
                _world_origin(light_cell, params, params.ceiling - 16),
                extras={"light": _LIGHT_BRIGHTNESS},
            )
        )
        occupied.add(light_cell)

        is_spawn_room = room.id == spawn_room.id

        # Monsters — never in the spawn room.
        if not is_spawn_room:
            for _ in range(_expected_count(params.monster_density, rng)):
                cell = _free_cell_in_room(room, grid, occupied, rng)
                if cell is None:
                    break
                cls = MONSTER_CLASSES[monster_cycle % len(MONSTER_CLASSES)]
                monster_cycle += 1
                entities.append(MapEntity(cls, _world_origin(cell, params, _STAND_OFFSET)))
                occupied.add(cell)

        # Items — any room, including spawn (items there are harmless).
        for _ in range(_expected_count(params.item_density, rng)):
            cell = _free_cell_in_room(room, grid, occupied, rng)
            if cell is None:
                break
            cls = ITEM_CLASSES[item_cycle % len(ITEM_CLASSES)]
            item_cycle += 1
            entities.append(MapEntity(cls, _world_origin(cell, params, _STAND_OFFSET)))
            occupied.add(cell)

    return entities


def _expected_count(density: float, rng: random.Random) -> int:
    """Turn an expected count (e.g. 0.5/room) into a concrete integer.

    The whole part is guaranteed; the fractional part is a Bernoulli draw, so
    the long-run mean equals ``density``.
    """
    whole = int(density)
    frac = density - whole
    extra = 1 if rng.random() < frac else 0
    return whole + extra


def _free_cell_in_room(
    room: Room,
    grid: Grid,
    occupied: set[Cell],
    rng: random.Random,
) -> Cell | None:
    """A random open, unoccupied cell inside ``room`` (deterministic order)."""
    candidates = [c for c in room.cells() if grid.is_open(c) and c not in occupied]
    if not candidates:
        return None
    candidates.sort()
    return rng.choice(candidates)


def _first_open_cell(room: Room, grid: Grid) -> Cell | None:
    for cell in room.cells():
        if grid.is_open(cell):
            return cell
    return None


def _world_origin(cell: Cell, params: GenParams, z: int) -> Vec3:
    """Cell -> world origin at the cell center on the XY plane, height ``z``."""
    cx, cy = cell
    c = params.cell
    return (cx * c + c // 2, cy * c + c // 2, z)
