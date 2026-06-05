# Phase 1 Data Model: Procedural Map Generation

The in-memory structures the generator builds, and the invariants enforced on them. All
coordinates are Quake units; the grid is a coarse lattice (cell size `C`, e.g. 64u) mapped
to world units by `world = cell * C`.

## Generation lifecycle

```
GenParams ─▶ layout()  ─▶ RoomGraph + Grid
                              │
              geometry()  ─▶  BrushSet          (sealed walls/floor/ceiling)
              entities()  ─▶  EntitySet         (spawn/monsters/items/lights)
                              │
                       MapModel  ─▶ verify()  ─▶ (reject+reseed on fail)
                              │
                       emit_map()  ─▶ .map text
```

## Entities

### GenParams
The knobs (also the future difficulty/progression axis).

| Field | Type | Default | Notes |
|---|---|---|---|
| `seed` | int | — | required; the only entropy source |
| `grid_w`, `grid_h` | int | 24×24 | grid cells |
| `cell` | int | 64 | world units per cell |
| `room_count` | int | 8 | target number of rooms (clamped to fit) |
| `room_min`, `room_max` | int | 3, 7 | room size in cells (square-ish) |
| `corridor_w` | int | 2 | corridor width in cells (≥ player width) |
| `loopiness` | float | 0.2 | fraction of extra (non-MST) edges added |
| `ceiling` | int | 192 | room height in world units (≥ player height) |
| `monster_density` | float | 0.5 | monsters per non-spawn room (expected) |
| `item_density` | float | 0.4 | items per room (expected) |

**Validation**: all clamped to sane ranges (e.g. `room_count` to what fits the grid;
`corridor_w ≥ 2`; `ceiling ≥ 96`); clamped values are recorded.

### Room
| Field | Type | Notes |
|---|---|---|
| `id` | int | |
| `x, y, w, h` | int (cells) | non-overlapping axis-aligned rectangle on the grid |
| `center` | (int, int) | cell coords, for the graph |

### RoomGraph
| Field | Type | Notes |
|---|---|---|
| `rooms` | list[Room] | |
| `edges` | list[(room_id, room_id)] | **MST over room centers + `loopiness` extra edges** |

**Validation**: the edge set is **connected** (every room reachable) — guaranteed because
it contains a spanning tree. Each edge → an L-shaped corridor of width `corridor_w`.

### Grid
| Field | Type | Notes |
|---|---|---|
| `w, h` | int | |
| `open` | bool[w][h] | True where a room or corridor was rasterised |

**Validation (the navigability invariant, FR-002)**: flood-fill `open` from the spawn cell
**must equal** the full set of open cells. If not → reject + reseed.

### Brush (axis-aligned box)
| Field | Type | Notes |
|---|---|---|
| `mins, maxs` | vec3 (world units) | the box extent |
| `tex` | str | LibreQuake texture name (wall/floor/ceiling) |

Emitted as 6 planes (R3). Walls come from solid cells adjacent to open cells, **merged into
maximal rectangles**; plus one floor slab and one ceiling slab over the open footprint.

### MapEntity
| Field | Type | Notes |
|---|---|---|
| `classname` | str | `info_player_start` \| `monster_*` \| `item_*`/`weapon_*` \| `light` |
| `origin` | vec3 (world units) | on the floor (`z = floor + standing offset`), in an open cell |
| `extras` | dict | e.g. `light` brightness, monster angle |

### BrushSet / EntitySet / MapModel
- **BrushSet**: `list[Brush]` (walls + floor + ceiling).
- **EntitySet**: `list[MapEntity]`.
- **MapModel**: `{ params, room_graph, grid, brushes: BrushSet, entities: EntitySet }` —
  the complete, verifiable, emittable level. `emit_map(MapModel) → str`.

## Invariants enforced (verify())

These map directly to the spec's requirements/edge cases:

1. **Reachability (FR-002)** — flood-fill open from spawn == full open set.
2. **Spawn safety (edge case)** — exactly one `info_player_start`; its room contains **no
   monster**; headroom ≥ player height.
3. **Content reachable (FR-003)** — every `monster_*` and `item_*`/`weapon_*` sits in an
   open cell reachable from spawn.
4. **No overlap** — no two entities share a cell/too-close origin; no entity inside a wall.
5. **Sealed (R6, leak guard)** — every open cell is fully ringed by open-or-solid cells
   that are emitted (the hull is closed); the bounding ring is solid.
6. **Determinism (FR-005 / SC-004)** — `generate(seed, params)` is pure.

A model that fails 1–5 is **rejected and regenerated** with the next derived seed (it is
never emitted), satisfying SC-002/SC-006.
