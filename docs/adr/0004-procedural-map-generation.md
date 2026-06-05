# ADR-0004: Procedural map generation via external `.map` + ericw-tools

**Status**: Accepted · **Date**: 2026-06-05 · **Feature**: `specs/004-procedural-maps/`

## Context

The project is heading toward procedurally generated levels (`docs/design.md` §6); this
is also the reason automatic navigation (feature 002/003) exists — the agent must handle
maps no human waypointed. We need a mechanism that produces **libre**, **navigable**,
engine-loadable levels, that fits the droplet/local split and the no-engine-C-patch
discipline.

## Decision

Generate Quake **`.map`** brush text in a seeded **Python** package (`mapgen/`) and compile
it to `.bsp` with **vendored prebuilt ericw-tools** (`qbsp`→`vis`→`light`, GPLv2). The
unmodified FTEQW + FrikBot `progs.dat` load the result. Levels are
**navigable-by-construction** (MST-connected rooms, single flat floor, sealed-hull grid
emission) with a flood-fill reachability invariant that **rejects + re-seeds** bad levels.
Verification is two-tier: static Python asserts (droplet, every seed) + the feature-001 sim
telemetry (local/CI, sampled seeds). Phased: Phase 1 box-room levels; Phase 2 prefab kit;
Phase 3 grammar + optional LLM theming.

## Alternatives considered

- **Engine-side BSP / nav-mesh generation** — rejected: needs engine-C work (violates
  engine discipline; the droplet can't build it).
- **OBSIDIAN / OBLIGE** (mature Quake procgen) — rejected: ships **id-derived content**
  (violates constitution IV) and is Lua/GUI-oriented. May inform Phase-2 prefab ideas only.
- **GAN / LLM direct geometry** — rejected for the skeleton: can't guarantee navigability
  and are heavy; LLM theming is kept as an *optional* Phase-3 layer over the deterministic
  skeleton.

## Consequences

- **+** Generation stays light, testable Python (droplet-friendly); no engine patch; reuses
  the engine + FrikBot + the feature-001 sim exactly as-is.
- **+** Navigability is guaranteed and verified with the same instrument we trust for
  `lq_e1m1`.
- **−** New external dependency (ericw-tools) is **vendored prebuilt** (never built on the
  droplet); compiling a level and running the engine remain **local/CI**, not droplet.
- **−** `.map` plane-winding correctness is only confirmable at first local `qbsp` compile
  (the droplet can verify everything except the compile).
- Generated-map texture provenance (LibreQuake) is logged in `docs/licenses.md`.
