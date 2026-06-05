# Implementation Plan: Procedural Map Generation

**Branch**: `feat/procedural-maps` | **Date**: 2026-06-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-procedural-maps/spec.md`; brainstormed
design `docs/superpowers/specs/2026-06-05-procedural-maps-design.md`.

## Summary

Generate varied, **navigable-by-construction**, libre Quake-engine levels the agent can
play, so the idle loop never runs dry **and** the automatic-navigation work is proven on
maps no human authored. Approach (**phased hybrid**, Phase 1 here): a seeded **Python
generator** lays out a connectivity-graph of box rooms + corridors on a grid, seals it
into brush geometry, populates it (spawn/monsters/items/lights) with **LibreQuake**
textures and the gamecode's libre monster/item classnames, and emits a `.map`. Vendored
**ericw-tools** (`qbsp`→`vis`→`light`) compile it to `.bsp`; the existing FTEQW + FrikBot
load it. Verification is two-tier: **static** Python asserts (reachability/seal/overlap —
runnable on the droplet) and **dynamic** reuse of the feature-001 sim telemetry (agent
covers + fights the generated level). No engine-C patches; generation is external.

## Technical Context

**Language/Version**: Python 3.11+ (`uv`) for the generator + static verification;
**ericw-tools 2.x** (`qbsp`/`vis`/`light`, GPLv2, **vendored prebuilt** binaries) for
compilation; FTEQW + our `progs.dat` to run; feature-001 sim harness for dynamic checks.

**Primary Dependencies**: ericw-tools (vendored prebuilt, never built on the droplet);
LibreQuake textures (a `.wad` for `qbsp`) + LibreQuake monster/item content; FTEQW +
FrikBot QuakeC (the consumer/navigator, features 002/003); feature-001 sim harness
(verification instrument).

**Storage**: generated levels as `.map` (text) → compiled `.bsp`; a level is identified by
its `(seed, params)`. No database.

**Testing**: `pytest` for static generation asserts (droplet-runnable, every seed) + the
feature-001 sim telemetry assertions for dynamic playability (local/CI).

**Target Platform**: generation + static verify = Python anywhere (incl. the droplet);
compile = ericw-tools binaries (local/CI); run = FTEQW GL/SV (local).

**Project Type**: content-generation tooling (CLI generator) + a verification harness,
feeding the game's existing engine/gamecode.

**Performance Goals**: a level generates + static-verifies in well under a second;
`qbsp`+`vis`+`light` on a small box-map in a few seconds; ≥95% of seeds valid on first
generation (SC-006).

**Constraints**: original/libre content only (constitution IV); **no engine-C patches**;
the droplet cannot compile ericw-tools or run the engine (compile/run are local/CI);
Python via `uv`.

**Scale/Scope**: Phase 1 = single-floor box-room levels (≤ ~30 rooms), one generated map
per seed; must generalize to endless seeds and (Phases 2–3) to richer geometry/structure.

## Constitution Check

*GATE: must pass before Phase 0; re-checked after Phase 1.*

| Principle | Assessment |
|---|---|
| **I. Visible Progression (NON-NEG)** | ✅ A generated level is inherently observable (a new map each run); size/complexity/difficulty params are a visible progression axis (later phase), measured via the sim. |
| **II. Behavior Config Is the Gameplay** | ✅ Maps are content, not agent-behavior config; introduces no rule engine. |
| **III. Low-Poly PS1 Authenticity** | ✅ Blocky grid geometry + LibreQuake low-res textures read as a late-'90s low-poly FPS — on-aesthetic, not a compromise. |
| **IV. Original/Libre, No id IP (NON-NEG)** | ✅ LibreQuake textures + the gamecode's libre monster/item content (exactly what `lq_e1m1` already uses); **no id assets/maps**; "Quake-engine-style", not the Quake brand; OBSIDIAN's id-derived content explicitly **excluded**; generated-map texture provenance logged in `docs/licenses.md`. |
| **V. Small, Testable, Observable** | ✅ Phased; Phase 1 verified by static `pytest` asserts + the existing sim telemetry (SC-002/003). |
| **Engine discipline (no C patches)** | ✅ Generation is **external** (Python + ericw-tools); levels load via the unmodified engine. An ADR records the mechanism (`.map` + ericw-tools vs engine-side nav-mesh/gen). |
| **Build/runtime (droplet 1 GB)** | ✅ Generation + static verify are light Python (`uv`, droplet-OK); ericw-tools is **vendored prebuilt** (never built on the droplet); compile + engine run are local/CI. |

**Result: PASS.** No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/004-procedural-maps/
├── plan.md              # This file
├── research.md          # Phase 0 — ericw-tools, .map format, textures, classnames, algo, verification
├── data-model.md        # Phase 1 — GenParams, RoomGraph, Grid, BrushSet, EntitySet, MapModel
├── quickstart.md        # Phase 1 — generate → compile → run → verify a level
├── contracts/           # Phase 1 — mapgen CLI + .map output + verification contracts
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
mapgen/                          # NEW — seeded Python generator (uv project, mirrors sims/)
├── idledoom_mapgen/
│   ├── params.py                # GenParams + seeded RNG
│   ├── layout.py                # room placement + connectivity graph (MST + loop edges) → grid
│   ├── geometry.py              # grid → sealed brush set (walls/floor/ceiling), merged rectangles
│   ├── entities.py              # spawn / monsters / items / lights placement (invariants)
│   ├── mapfile.py               # .map text emission (brushes + entities + worldspawn "wad")
│   ├── verify.py                # static asserts: reachability flood-fill, seal, overlap
│   └── cli.py                   # `mapgen --seed S [params] → gen_S.map`
├── tests/                       # pytest: static verification across many seeds (droplet)
└── pyproject.toml

tools/ericw-tools/               # NEW — vendored PREBUILT qbsp/vis/light (per-OS); never built on droplet
sims/                            # feature-001 harness — dynamic verify: run agent on gen_S, assert telemetry
scripts/                         # gen+compile helper: mapgen → qbsp→vis→light → .bsp → game maps dir
docs/
├── adr/0004-procedural-map-generation.md   # mechanism ADR (.map + ericw-tools)
├── licenses.md                  # generated-map texture provenance (LibreQuake)
└── design.md                    # §6 procedural maps (link the ADR)
Justfile                         # `just mapgen SEED`, `just mapgen-compile SEED`, `just mapgen-verify`
```

**Structure Decision**: a new Python **`mapgen/`** package mirrors the `sims/` layout
(`uv`, droplet-friendly, `pytest`-tested). ericw-tools is **vendored prebuilt** under
`tools/` (constitution: never compile on the droplet). The existing **`sims/`** harness is
the dynamic verifier — no new measurement instrument. **No engine or QuakeC changes**:
generation is fully external and loads through the unmodified engine. A mechanism **ADR**
is added under `docs/adr/`.

## Complexity Tracking

> No constitution violations — section intentionally empty.

## Phase notes

- **Phase 0 (`research.md`)** resolves: ericw-tools vendoring + invocation + the
  droplet/local split; the minimal `.map` format (brush plane syntax, `worldspawn "wad"`,
  entity keys); LibreQuake texture/WAD names; the libre monster/item classnames; the
  grid→sealed-brush emission + rectangle merging + leak-avoidance; seeded determinism; and
  how the two verification tiers map onto features 001/002.
- **Phase 1** emits `data-model.md` (the generation data structures + invariants),
  `contracts/` (the `mapgen` CLI, the `.map` output contract, the verification contract),
  and `quickstart.md` (gen → compile → run → verify).
- **Phase 2** (`/speckit-tasks`) turns this into an ordered, dependency-aware task list.
