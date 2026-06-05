# Procedural Map Generation — Design

**Date:** 2026-06-05 · **Branch:** `feat/procedural-maps` · **Status:** design approved
(brainstorm) → spec for review

Prospective Spec Kit feature (assign `specs/NNN-procedural-maps/` via
`/speckit-specify` when formalizing). Builds on `docs/design.md` §3/§6 (procedural
maps as the shipping content direction; automatic navigation is its precondition)
and the auto-navigation work (committed exploration + Dijkstra patrol).

## Goal & drivers

Generate **Quake-engine-style** levels (BSP, for FTEQW) from **original/libre**
content, so the agent has an endless supply of maps to play. The two co-equal
drivers (per brainstorm) actually converge on the same requirement:

1. **Endless, navigable content** — a fresh, playable map every run so the idle loop
   never runs dry.
2. **Showcase auto-nav on unseen maps** — the agent's navigation competence shining
   on levels no human waypointed (the design's stated reason for automatic nav).

Both demand **navigability guaranteed by construction** + enough **structural
variety** to feel novel. A third driver — **"the AI builds the world too"** as a
hook — is satisfied *later* by layering an LLM theming pass on top of a deterministic
algorithmic skeleton, so playability never rides on ML.

## Constraints (and how they shape the design)

| Constraint | Consequence |
|---|---|
| FTEQW plays Quake **BSP** | Generate `.map` brush text, compile with **ericw-tools** (`qbsp`/`vis`/`light`, GPL) — the modern standard; has `misc_external_map` (prefab composition) + `func_detail`. |
| **Original/libre only** (pillar IV) | LibreQuake textures + our own/libre monster & item classnames. Rules **out** OBSIDIAN's content (id-derived) and GAN training on copyrighted levels. |
| Agent must **auto-navigate** the result | Connectivity/traversability must be **guaranteed**, not hoped for — favours algorithmic PCG over GANs (which can't promise playability). |
| Droplet can't run the engine / heavy ML | Generation must be **lightweight** (algorithmic Python), runnable headless; the engine run stays local/CI. |
| Low-poly PS1 aesthetic (pillar III) | Blocky, grid-aligned geometry is on-aesthetic, not a compromise. |

## Approach: phased hybrid (chosen)

All phases emit `.map` → ericw-tools → FTEQW and are connectivity-guaranteed.

- **Phase 1 — pipeline + graph rooms (this spec).** A connectivity-graph of box
  rooms joined by corridors; prove the whole `seed → .map → .bsp → agent plays it`
  loop and the navigability guarantee, reusing the verification we already trust.
- **Phase 2 — prefab kit.** Hand-author a library of libre low-poly room/junction/
  arena pieces; assemble them on the connectivity graph (`misc_external_map`) for
  authored-quality geometry + combinatorial variety.
- **Phase 3 — grammar + LLM theming.** A mission/space grammar for intentional
  structure (arenas, lock-and-key gating, secret routes); an **optional LLM pass**
  themes/names/objectives the algorithmic skeleton — the "AI builds the world" hook,
  with playability still owned by the skeleton.

Novelty compounds across phases; each is its own spec → plan → implement cycle.

---

## Phase 1 — detailed design

### 1. End-to-end pipeline

```
seed ─▶ mapgen (Python) ─▶ <name>.map  (brushes + entities + LibreQuake textures)
                                │
                        ericw-tools:  qbsp ▶ vis ▶ light
                                │
                          <name>.bsp ─▶ FTEQW  (sim headless / watch)
                                │
                  agent auto-nav explores + fights ─▶ nav/combat telemetry
                                │
        verify: waypoints climb, shots_fired > 0, kills ≥ 1   (existing checks)
```

Success here satisfies **both** top drivers at once: the agent does on a never-seen
generated map what it now does on `lq_e1m1` (covers it, fights).

### 2. Generator + navigability guarantee

**Algorithm (seeded, deterministic):**
1. **Place rooms.** Drop *K* axis-aligned box rooms (sizes from a range) onto a
   coarse grid, no overlap.
2. **Connect them.** Graph over room centres → **minimum spanning tree** (every room
   reachable) **+ a few extra edges** (loops, so it's not a dead-end tree). Each edge
   → an L-shaped **corridor**, ≥ player width.
3. **Mark open cells.** Rasterise rooms + corridors onto the grid as "open".
4. **Seal it.** Any grid cell bordering open space that isn't open becomes a **solid
   wall**; lay a **floor slab** + **ceiling slab** over the open footprint. Merge
   contiguous solids into big brushes (low brush count). Openings land exactly where
   rooms/corridors meet — **no leaks** (which `qbsp` requires).

```
 ███████████████     █ = solid wall   . = open / walkable
 █...██....█...███
 █...██....█...███    MST guarantees the spawn reaches every room;
 █...█@....█...███    the loop edge adds an alternate route.
 █...███.███...███    @ = info_player_start
 █.....█...█.....█
 ███████████████
```

**Navigability — guaranteed by construction:** one flat floor (all open cells share
a z), corridors ≥ player width, ceilings ≥ player height, graph connected via the
MST. The agent can physically walk everywhere. **Asserted:** flood-fill the open
cells from the spawn — it must equal the entire open set, else **reject and re-seed**.
(The sim telemetry confirms it empirically, same as `lq_e1m1`.)

**Knobs** (which double as the future difficulty/progression axis): seed, room count,
room sizes, corridor width, loopiness, monster/item density.

### 3. Content placement (invariants that can't break)

- **Spawn** — one `info_player_start`, floor-centred in a chosen room, headroom
  clear, **no monster in the spawn room** (agent wakes up safe).
- **Monsters** — a handful in *other* rooms (so the agent must traverse to fight,
  exercising nav **and** combat), floor-placed, spaced, using our existing libre
  monster classnames; all reachable by construction.
- **Items** — a few health/ammo/weapon pickups, floor-placed in rooms.
- **Lights** — one `light` per room near the ceiling, so `vis`/`light` actually
  illuminate it (else pitch black for the watch view; nav wouldn't care, you would).
- **worldspawn** — map name + LibreQuake WAD reference.
- **Exit** — deferred to Phase 1.5 (chaining endless maps). Phase 1 the agent just
  explores + fights; the sim time-limit / watch loop already handle termination.

Enforced at generation: every entity in an open cell, on the floor, headroom OK, none
overlapping, spawn room clear.

### 4. Components & where they live

- **`mapgen`** — new **Python** package (fits the `sims/` harness, `uv`,
  droplet-friendly; the Rust host stays untouched). Pure functions: `generate(seed,
  params) → MapModel`; `emit_map(MapModel) → .map text`; `verify(MapModel)` (static
  asserts). Small, focused modules: layout (graph + grid), geometry (brush emission),
  entities (placement), io (.map writer).
- **Compile** — invoke vendored **ericw-tools** (`qbsp`/`vis`/`light`) → `.bsp` into
  the game maps dir.
- **Integration** — the sim/watch loads it via `+map <gen_name>`; a generated map is
  identified by its seed (`gen_<seed>`).

### 5. Verification (two tiers)

- **Static (Python, runs on the droplet — no engine):** flood-fill reachability ==
  full open set; spawn clear; all monsters reachable; no entity overlaps;
  sealed/well-formed `.map`. → `pytest`, fast, on **every** seed.
- **Dynamic (engine, local/CI):** run the sim on `gen_<seed>` → the **telemetry we
  already trust** (waypoints climb, `shots_fired > 0`, `kills ≥ 1`) proves the agent
  navigated + fought a never-seen generated map. Mirrors the feature-002 nav checks.

### 6. Success criteria

- SC-1: `generate(seed)` produces a `.map` that `qbsp/vis/light` compile **without a
  leak** for ≥ 95% of random seeds (rejected seeds re-rolled).
- SC-2: every generated map passes the **static** navigability asserts (100%).
- SC-3: on a sample of generated seeds the sim shows the agent **covers the map and
  reaches combat** (`shots_fired > 0`, `kills ≥ 1`) within the run time-limit —
  auto-nav proven on unseen maps.
- SC-4: same seed → byte-identical `.map` (determinism).

### 7. Dependencies / to resolve in planning

- **Vendor ericw-tools** (`qbsp/vis/light`) like we did `fteqcc`; confirm the
  tiny-map compile runs on the **droplet** (if so, the whole gen→compile→static-verify
  loop is headless/CI; only the engine run is local).
- **Texture WAD** — supply LibreQuake textures to `qbsp` (`-wadpath`/embed); confirm
  the exact wall/floor/ceiling texture names from the LibreQuake set.
- **Monster/item classnames** — enumerate the libre classnames our `progs.dat`
  actually supports (e.g. `monster_army`, `item_health`, `weapon_*`).
- **ADR** — record the generation-mechanism decision (algorithmic `.map` + ericw-tools
  vs engine-side) under `docs/adr/`, per the "engine discipline" convention.
- **Licensing** — generated maps derive from LibreQuake textures; note in
  `docs/licenses.md` if shipped.

---

## Phases 2–3 (sketch)

- **Phase 2 — prefab kit.** Author libre low-poly `.map` chunks (rooms, halls,
  junctions, arenas, stairs) with tagged connection sockets; the layout graph snaps
  them via `misc_external_map`. Variety = kit size × combinations; geometry quality
  jumps. Adds verticality (stairs/lifts) → richer nav (ties to nav competence).
- **Phase 3 — grammar + LLM theming.** A mission grammar generates intentional
  structure (objective, locks/keys, arenas, secrets) realised onto the space; an
  **optional LLM pass** assigns theme, room names, set-dressing, and an objective
  blurb from the graph — the "AI builds the world" hook. The skeleton remains
  deterministic and navigable; the LLM only flavours it.

## Open questions

- Feature number under Spec Kit (`specs/003` vs `004` — "feature 003" is informally
  the motion-competence work in code comments; pick a non-colliding number when
  running `/speckit-specify`).
- Difficulty/progression mapping: which knobs scale with player progression, and how
  generated maps slot into the content gates in `docs/progression.md`.
- Endless chaining (Phase 1.5): exit → load the next seed vs the host app driving map
  rotation.

## Risks

- **Leaks** — the #1 failure of generated Quake maps; mitigated by the
  seal-by-construction grid emission + a compile-time leak check (reject/re-seed).
- **ericw-tools on the droplet** — if compilation can't run headless there, the gen
  loop is local-only (acceptable; degrades CI automation, not correctness).
- **Sameyness** — Phase 1 box rooms will look plain; that's expected and is exactly
  what Phases 2–3 address. Phase 1's bar is *navigable + endless + verified*, not
  *pretty*.
