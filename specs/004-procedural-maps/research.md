# Phase 0 Research: Procedural Map Generation

Decisions that resolve the Technical Context unknowns. Format: **Decision / Rationale /
Alternatives**.

## R1. Generation mechanism — external `.map` + ericw-tools

**Decision**: Generate Quake **`.map`** brush text in Python and compile it to `.bsp` with
**ericw-tools** (`qbsp`→`vis`→`light`). No engine-side generation; the unmodified FTEQW +
`progs.dat` load the result.

**Rationale**: `.map`→`.bsp` is the standard, well-documented Quake content pipeline;
keeps generation in light, testable Python (droplet-friendly); satisfies the **no
engine-C-patch** discipline; and lets us reuse the engine + FrikBot exactly as-is.

**Alternatives**: *Engine-side BSP/nav-mesh generation* — would need engine C work
(violates engine discipline, droplet can't build it). *OBSIDIAN/OBLIGE* — generates Quake
maps but ships **id-derived content** (violates constitution IV) and is Lua/GUI-oriented;
rejected (may serve as a reference for prefab ideas in Phase 2 only). *GANs/LLM direct
geometry* — can't guarantee navigability and are heavy; deferred to the optional Phase-3
theming layer.

**ADR**: record as `docs/adr/0004-procedural-map-generation.md`.

## R2. ericw-tools — vendor prebuilt, split droplet vs local

**Decision**: **Vendor prebuilt** ericw-tools binaries (latest 2.x; the project ships
per-OS prebuilt `qbsp`/`vis`/`light`, GPLv2) under `tools/ericw-tools/`. The compile step
runs them; it does **not** build them. Pipeline per level: `qbsp gen_S.map` → `vis
gen_S.bsp` → `light gen_S.bsp`.

**Rationale**: constitution forbids compiling heavy toolchains on the 1 GB droplet;
prebuilt binaries sidestep that. `vis` can be slow on big maps but Phase-1 box-maps are
tiny (seconds). Whether the Linux prebuilt runs headless on the droplet is confirmed during
implementation; if yes, gen→compile→static-verify is fully headless/CI, else compile is
local (generation + static verify stay on the droplet regardless).

**Alternatives**: build ericw-tools from source (rejected: droplet OOM; local-only build
adds setup). Skip `vis` (faster but leaves the map unoptimised/fullbright-ish) — keep `vis`
for correctness, revisit if compile time bites.

## R3. Minimal `.map` format

**Decision**: Emit standard Quake `.map`:
- **worldspawn** entity first, with `"classname" "worldspawn"`, `"wad"
  "<librequake>.wad"`, and all world brushes.
- **Brush** = `{ ` + one plane per face: three integer points `( x y z ) ( x y z ) ( x y z
  )` then `TEXNAME xoff yoff rot xscale yscale` + ` }`. Axis-aligned boxes only (6 faces),
  which makes plane points trivial and robust.
- **Point/solid entities** as `{ "classname" "..." "origin" "x y z" ... }`.

**Rationale**: axis-aligned integer boxes are the simplest brushes that always form valid
convex solids — no degenerate-plane risk. The classic (non-Valve-220) format is enough for
flat geometry; revisit Valve-220 only if Phase 2 needs finer texture alignment.

**Alternatives**: Valve-220 format (more texture control, more verbose) — deferred.
`misc_external_map` prefab composition — Phase 2 (prefab kit), not Phase 1.

## R4. Textures — LibreQuake WAD

**Decision**: Reference a small set of **LibreQuake** wall/floor/ceiling texture names; hand
`qbsp` the LibreQuake `.wad` via `-wadpath`/the `worldspawn "wad"` key. Exact texture names
are pinned from the LibreQuake asset set during implementation and recorded in
`docs/licenses.md`.

**Rationale**: LibreQuake is already the project's libre base (its paks live in `id1/`,
gitignored runtime data); reusing its textures keeps everything libre and on-aesthetic. The
WAD is only needed at **compile** time (local), not for generation or static verify.

**Alternatives**: ship our own textures (more authoring; defer); embed textures in the BSP
(qbsp can, but the WAD path is simpler).

## R5. Entity content — libre classnames already in `progs.dat`

**Decision**: Use the gamecode's existing classnames (LibreQuake content behind them):
- **Spawn**: `info_player_start`.
- **Monsters (Phase 1, simple)**: `monster_army`, `monster_dog`, `monster_knight`.
- **Items (Phase 1)**: `item_health`, `item_shells`, `weapon_supershotgun`.
- **Lights**: `light` (with `"light"` brightness), one per room.

**Rationale**: these are exactly the entities `lq_e1m1` uses and the agent already
fights/collects (telemetry confirmed `monster_army` kills). The **content** is LibreQuake's
libre replacement; the classnames are the FrikBot/rerelease gamecode's. No id assets.

**Alternatives**: a custom minimal monster set — unnecessary; reuse what's proven.

## R6. Grid → sealed brush emission (leak-free)

**Decision**: Rasterise rooms + corridors to "open" grid cells. Emit: a **floor slab** and
**ceiling slab** spanning the open footprint, and **wall brushes** for every solid cell
bordering an open cell — **merged into maximal rectangles** (greedy) to keep brush count
low. Place an `info_null`-free **sealed shell**: because every open cell is fully ringed by
solid cells or other open cells, the world is closed (no leak) with openings exactly at
room/corridor junctions. A `light`-lit sealed volume compiles cleanly.

**Rationale**: "the void must be sealed" is the #1 qbsp failure (leaks). Building walls from
*solid cells adjacent to open cells* guarantees a closed hull by construction. Greedy
rectangle merging avoids one-brush-per-cell blowup.

**Alternatives**: per-room hollow boxes with punched doorways (fiddly gap management,
leak-prone); CSG subtraction (qbsp `.map` is additive). Rejected for Phase 1.

**Leak guard**: after compile, treat a qbsp leak (`.pts` file / "leaked" log) as a hard
failure → reject + re-seed; also a static pre-compile assert that the open set is fully
ringed.

## R7. Determinism

**Decision**: A single seeded `random.Random(seed)` threaded through layout + population;
no other entropy. `generate(seed, params)` is pure → byte-identical `.map` (SC-004).

**Rationale**: reproducibility for testing/sharing/debugging; the sim harness already seeds.

## R8. Verification — two tiers mapped to features 001/002

**Decision**:
- **Static (Python, droplet, every seed)** — on the in-memory `MapModel` before/without
  compiling: flood-fill open cells from the spawn cell == full open set (FR-002); spawn cell
  clear of monsters; every monster/item in a reachable open cell; no entity overlaps; open
  set fully ringed (seal pre-check). → `pytest` in `mapgen/tests/`.
- **Dynamic (engine, local/CI)** — compile a sample of seeds, run each through the
  **feature-001 sim**, assert the feature-002 nav/combat telemetry: `waypoints` climbs,
  `shots_fired > 0`, `kills ≥ 1` (SC-003) — the agent navigates + fights a never-seen level.

**Rationale**: static asserts catch generation bugs instantly and cheaply on the droplet;
the dynamic tier reuses the exact instrument we already trust for nav competence, so
"playable" means the same thing it does for `lq_e1m1`.

**Alternatives**: only-dynamic (slow, needs the engine for every seed — rejected);
only-static (can't catch engine/compile issues — rejected). Two tiers it is.

## Open items carried to planning/tasks

- Confirm the Linux prebuilt ericw-tools runs headless on the droplet (decides whether
  compile is CI-able or local-only).
- Pin the exact LibreQuake WAD + texture names; log in `docs/licenses.md`.
- Decide where compiled `.bsp` lands so the sim/watch `+map gen_S` finds it (game `maps/`
  dir vs `id1/maps/`), consistent with the feature-002 `.way` path handling.
