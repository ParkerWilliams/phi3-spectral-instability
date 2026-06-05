# Contracts: Procedural Map Generation (Phase 1)

The interfaces this feature exposes. Three surfaces: the **generator CLI**, the **`.map`
output**, and the **verification** contract.

## 1. `mapgen` CLI

```
mapgen --seed <int> [--out <path.map>] [--params <key=val> ...]
```

| Arg | Required | Default | Meaning |
|---|---|---|---|
| `--seed` | yes | — | the level seed (only entropy source) |
| `--out` | no | `gen_<seed>.map` | output `.map` path |
| `--params k=v` | no | (catalogue defaults) | override any `GenParams` field (clamped) |

**Behaviour**: pure function of `(seed, params)`. On success writes a **valid** `.map`
(static verification passed) and exits `0`, printing the resolved (clamped) params + a
one-line summary (`rooms`, `open_cells`, `monsters`, `items`). On an unsatisfiable request
(e.g. params that cannot fit) it re-rolls a bounded number of times, then exits non-zero
with a diagnostic. **Never writes an invalid `.map`.**

**Determinism**: same `(seed, params)` → byte-identical `.map` (SC-004).

A compile helper (Justfile / `scripts/`) chains: `mapgen --seed S` → `qbsp/vis/light` →
`gen_S.bsp` into the game `maps/` dir, then `+map gen_S` for the sim/watch.

## 2. `.map` output contract

A standard Quake `.map` that **`qbsp` compiles without a leak**:
- First entity is `worldspawn` with `"wad" "<librequake>.wad"` and all world brushes
  (walls + floor + ceiling), axis-aligned integer boxes, 6 planes each (see research R3).
- Exactly one `info_player_start` in a safe room (no co-located monster, full headroom).
- ≥1 `monster_*` and ≥1 item (`item_*`/`weapon_*`), all on the floor in reachable open
  cells, none overlapping, none in the spawn room.
- ≥1 `light` per room (so `vis`/`light` illuminate it).
- The hull is **sealed** (no void leak).

**Guarantee**: the open space is fully connected and every entity is reachable from the
spawn (the navigability contract the agent's auto-nav relies on).

## 3. Verification contract

**Static (`mapgen/tests/`, pytest, droplet-runnable, every seed):**
- `reachable(model)` — flood-fill open from spawn == full open set. **MUST** hold.
- `spawn_safe(model)` — one `info_player_start`; spawn room monster-free; headroom OK.
- `content_reachable(model)` — every monster/item in a reachable open cell.
- `no_overlap(model)` — no two entities too close; none inside a wall.
- `sealed(model)` — the emitted hull is closed (leak pre-check).
- `deterministic` — `generate(s,p) == generate(s,p)` byte-for-byte.

**Dynamic (`sims/`, feature-001 harness, local/CI, sampled seeds):**
- Compile `gen_S` and run the agent; assert the feature-002 telemetry: `waypoints`
  strictly increases over the run, `shots_fired > 0`, `kills ≥ 1` within the time limit
  (SC-003) — the agent navigates and fights a never-seen generated level.
- A `qbsp` **leak** (`.pts` produced / "leaked" in the log) is a **hard failure** for that
  seed → it must have been rejected upstream; if it reaches compile, that's a bug to fix.

**Failure policy**: any static failure ⇒ the level is rejected and regenerated from the
next derived seed; an invalid level is never compiled or presented (SC-002, SC-006).
