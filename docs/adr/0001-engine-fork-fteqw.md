# ADR-0001: Use FTEQW as the engine fork

**Status:** Accepted
**Date:** 2026-05-23
**Deciders:** Parker, Taber

## Context

The project requires a Quake 1 engine fork that we can extend with custom
gameplay logic, expose tunable bot parameters, and embed (or coordinate with)
a host application providing the right-hand upgrade UI. The engine must
support an open-source license compatible with our intended distribution and
be actively maintained enough that build issues are tractable.

Key requirements:
- Scriptable gameplay (so most bot and progression logic can live outside
  engine C)
- Ability to expose runtime-tunable parameters readable from gameplay code
  and writable from outside the engine
- Reasonably current codebase that builds on Linux, macOS, Windows
- Open source license compatible with FrikBot-derived QuakeC and our host app
- Active enough community that bug reports get reasonable attention

## Decision

Use **FTEQW** as the engine fork. Vendor it as a git submodule under
`engine/` pinned to a specific commit. Bump the pin deliberately, with a
documented reason.

## Alternatives considered

- **QuakeSpasm** — clean, stable, well-loved by the mapping community. Easy
  to read C codebase. Rejected because most of our extension work is in
  gameplay logic, and QuakeSpasm has less scripting surface than FTEQW.
  Would force more changes in C than we want.

- **Ironwail** — performance-tuned QuakeSpasm fork. Beautiful but optimized
  for "play original Quake well" rather than "platform for extension."
  Rejected for similar reasons to QuakeSpasm plus narrower modding surface.

- **DarkPlaces** — what Xonotic/Nexuiz used. Capable but idiosyncratic and
  heavier than we need. Maintenance has slowed. Rejected as overkill and
  higher long-term risk.

- **vkQuake** — Vulkan-focused. Visually nice but our project doesn't need
  modern rendering, and the Vulkan dependency complicates the host app
  coordination story. Rejected as off-target.

- **FTEQW (chosen)** — most feature-rich modern fork. Supports CSQC
  (client-side QuakeC), modern shaders, extensive cvar/cmd surface for
  external coordination, dedicated server mode for headless sims. Active
  development. License (GPLv2) compatible with our plans.

## Consequences

**Easier:**
- Most gameplay and bot logic lives in QuakeC/CSQC, no engine C edits
  required for typical features
- Headless dedicated server mode supports our sim harness without separate
  build configuration
- Cvar surface is sufficient to expose bot stats without engine patches

**Harder:**
- FTEQW codebase is larger and less idiomatic than QuakeSpasm; engine-level
  patches (if needed) require more orientation time
- FTEQW's flexibility means more knobs to misconfigure; we'll need to lock
  down our engine config carefully
- Documentation is scattered; expect to read forum posts and source

**Risks and escape hatches:**
- If FTEQW maintenance stalls, we can switch to QuakeSpasm with moderate
  effort, because most of our work is in QuakeC which is portable. Our
  engine-C patches (if any) would need re-porting.
- We commit to GPLv2 for our QuakeC code by virtue of linking against
  FTEQW's GPLv2 codebase. Confirm full implications before public release.

## References

- FTEQW project: https://www.fteqw.org/
- Source: https://sourceforge.net/p/fteqw/code/
- License: GPLv2 (see engine/LICENSE after submodule init)
- Original engine comparison discussion: [link to notes / chat log when available]
