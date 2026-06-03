# ADR-0003: Automatic navigation via QuakeC waypoint generation

**Status:** Proposed (pending feature 002 PR review — both-devs sign-off per constitution)
**Date:** 2026-06-02
**Deciders:** Parker, Taber

## Context

The agent must traverse levels on its own with **no hand-authored waypoints**
(`docs/design.md` §3): maps will eventually be **procedurally generated** (§6), so
no human can pre-place a navigation graph. Today FrikBot only ships waypoints for
id1 `dm1`–`dm6`; on LibreQuake maps the agent has no nav data, wanders near spawn,
and never reaches combat — which left feature 001's SC-004 unprovable. Navigation
competence is also a first-class progression axis. We need a way to produce usable
navigation data automatically, per map, with zero human steps.

Hard constraints:
- **Constitution: minimize engine-C patches** — every engine patch / submodule bump
  needs its own ADR and is discouraged.
- Reuse the FrikBot baseline (ADR-0001) where possible.
- Must be measurable through the feature-001 headless-sim harness.

## Decision

Generate navigation **in QuakeC**, building on FrikBot's existing systems:

- `DynamicWaypoint` (`bot_way.qc`) already creates + links waypoints as the agent
  moves (it runs in our sim because `max_clients ≥ 2`).
- Add an **exploration driver** so the agent actively seeks unvisited space
  (instead of loitering near spawn), so the graph covers the level and brings
  enemies into view.
- **Auto-save** the generated graph with `SaveWays()` → `maps/<map>.way`, which the
  engine already `exec`-loads at level start; reuse it on later runs (regen via a
  cvar).
- Expose navigation competence through the existing `bot_map_awareness` cvar and
  measure coverage via feature-001 telemetry.

**No engine-C changes.** This is pure QuakeC + cvars.

## Alternatives considered

- **BSP-derived nav-mesh (engine-C).** Sample walkable space / parse BSP
  leaves+portals in engine C to build a nav-mesh. Most robust for dense/large or
  pathologically-shaped procedural maps, and likely the long-term answer. **Rejected
  for now**: it is an engine-C patch + submodule change (heavier, its own ADR), and
  the QuakeC route reuses ~80% existing machinery. Revisit (superseding this ADR) if
  QuakeC dynamic generation can't produce usable graphs on real/generated maps.
- **Keep manual `.way` recording.** Rejected by the design — doesn't scale to
  procedural maps; already reframed as temporary scaffolding (`docs/waypointing.md`).
- **Learned / RL navigation.** Out of scope; far heavier; not libre-toolchain-simple.

## Consequences

- **Positive:** no engine patch (constitution-aligned); reuses FrikBot + ADR-0001;
  fast path to unblock feature-001 SC-004; navigation becomes a tunable
  progression axis measured by the sim.
- **Negative / risk:** dynamic-generation quality depends on the exploration driver;
  may under-cover very large/disconnected maps. Mitigations: coverage telemetry +
  the nav-competence axis; stuck-recovery prevents softlocks. If quality proves
  insufficient on procedural maps, escalate to the nav-mesh alternative (new ADR).
- **Follow-on:** feature 002 (`specs/002-auto-navigation/`) implements this;
  `docs/design.md` §3/§7 reference this ADR.
