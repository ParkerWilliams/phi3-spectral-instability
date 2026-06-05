"""Static-verification tests: generated models satisfy every invariant."""

from __future__ import annotations

import pytest

from idledoom_mapgen.entities import MONSTER_CLASSES, SPAWN_CLASS
from idledoom_mapgen.generate import generate
from idledoom_mapgen.model import Cell, MapModel
from idledoom_mapgen.verify import _emitted_wall_cells, _flood_fill, verify

SEEDS = [1, 2, 7, 13, 42, 99, 256, 1001, 31337, 65535]


def _entity_cell(model: MapModel, origin: tuple[int, int, int]) -> Cell:
    c = model.params.cell
    return (origin[0] // c, origin[1] // c)


@pytest.mark.parametrize("seed", SEEDS)
def test_generated_model_is_valid(seed: int) -> None:
    model = generate(seed)
    assert verify(model) == []


@pytest.mark.parametrize("seed", SEEDS)
def test_reachability(seed: int) -> None:
    model = generate(seed)
    spawns = [e for e in model.entities if e.classname == SPAWN_CLASS]
    assert len(spawns) == 1
    spawn_cell = _entity_cell(model, spawns[0].origin)
    reached = _flood_fill(model.grid, spawn_cell)
    assert reached == set(model.grid.open_cells)


@pytest.mark.parametrize("seed", SEEDS)
def test_spawn_room_monster_free(seed: int) -> None:
    model = generate(seed)
    spawn = next(e for e in model.entities if e.classname == SPAWN_CLASS)
    spawn_cell = _entity_cell(model, spawn.origin)
    spawn_room = next(r for r in model.rooms if r.contains(spawn_cell))
    for ent in model.entities:
        if ent.classname in MONSTER_CLASSES:
            assert not spawn_room.contains(_entity_cell(model, ent.origin))


@pytest.mark.parametrize("seed", SEEDS)
def test_no_entity_overlaps(seed: int) -> None:
    model = generate(seed)
    cells = [_entity_cell(model, e.origin) for e in model.entities]
    assert len(cells) == len(set(cells))
    # And none inside a wall.
    for cell in cells:
        assert model.grid.is_open(cell)


@pytest.mark.parametrize("seed", SEEDS)
def test_sealed(seed: int) -> None:
    model = generate(seed)
    wall_cells = _emitted_wall_cells(model)
    grid = model.grid
    for cx, cy in grid.open_cells:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (cx + dx, cy + dy)
            if not grid.is_open(nb):
                assert grid.in_bounds(nb), f"open cell {(cx, cy)} touches grid border"
                assert nb in wall_cells, f"open cell {(cx, cy)} borders unsealed {nb}"


def test_at_least_one_monster_and_item() -> None:
    # Aggregate across seeds: the .map contract requires >=1 monster and item.
    saw_monster = False
    saw_item = False
    for seed in SEEDS:
        model = generate(seed)
        for ent in model.entities:
            if ent.classname in MONSTER_CLASSES:
                saw_monster = True
            if ent.classname.startswith(("item_", "weapon_")):
                saw_item = True
    assert saw_monster
    assert saw_item
