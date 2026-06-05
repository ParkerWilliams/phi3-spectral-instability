# Feature Specification: Procedural Map Generation

**Feature Branch**: `feat/procedural-maps`

**Created**: 2026-06-05

**Status**: Draft

**Input**: Brainstormed design (`docs/superpowers/specs/2026-06-05-procedural-maps-design.md`):
generate varied, playable, agent-navigable levels from original/libre content so the
agent always has fresh maps to play — the precondition for the automatic-navigation
work (`docs/design.md` §3/§6).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A fresh, playable level every run (Priority: P1)

The player starts (or the idle loop advances) and the agent is dropped into a level
it has never played before — fully traversable and populated with enemies to fight
and items to grab. Over many runs the content never repeats itself into staleness.

**Why this priority**: "Endless content" is half the point of the feature and the
core of the idle fantasy — the player keeps watching because there is always
something new. Without this there is nothing to generate.

**Independent Test**: Generate a level from a fresh seed, load it, and confirm the
agent can start, move through it, and reach enemies/items — delivering a complete
"new map to watch" on its own.

**Acceptance Scenarios**:

1. **Given** a previously unused seed, **When** a level is generated and loaded,
   **Then** the agent spawns safely and the level contains reachable enemies and items.
2. **Given** repeated runs, **When** each uses a new seed, **Then** each produces a
   structurally different level (no forced repeats).

---

### User Story 2 - The agent navigates levels no human designed (Priority: P1)

The agent plays a generated level using only its **automatic** navigation — there is
no hand-authored nav data for that level — and still covers the map and reaches
combat, the way it does on the hand-made test level.

**Why this priority**: This is the design's stated reason automatic navigation
exists, and it is what makes procedural maps viable at all. It also showcases the
agent's competence on the unknown — a marquee moment for the watcher.

**Independent Test**: Run the agent on a never-before-seen generated level and
confirm via the existing telemetry that it explores the level and engages enemies,
with no per-map navigation authoring.

**Acceptance Scenarios**:

1. **Given** a generated level with no hand-authored navigation data, **When** the
   agent plays it for the run's duration, **Then** it covers the level and engages
   enemies (it does not stall, soft-lock, or fail to find combat).
2. **Given** any generated level presented to the agent, **Then** every area is
   reachable from the spawn (no agent can be trapped or blocked from content).

---

### User Story 3 - Reproducible and automatically verified levels (Priority: P2)

A level is identified by its seed (and parameters); the same seed always yields the
same level, and every level is automatically checked playable **before** the agent is
asked to play it.

**Why this priority**: Reproducibility makes levels testable, shareable, and
debuggable; pre-use verification guarantees the player never watches the agent get
stuck in a broken level. Both protect the experience, but the feature delivers value
(US1/US2) before these are perfected.

**Independent Test**: Generate the same seed twice and confirm identical levels; feed
a batch of seeds through verification and confirm invalid ones are rejected and
regenerated rather than presented.

**Acceptance Scenarios**:

1. **Given** a seed, **When** the level is generated twice, **Then** the two levels
   are identical.
2. **Given** a generated level that is not fully traversable or otherwise invalid,
   **When** verification runs, **Then** the level is rejected and a replacement is
   generated, and the invalid one is never presented to the agent.

---

### User Story 4 - Variety and richness grow over time (Priority: P3)

Generated levels become progressively more interesting — better-looking geometry,
then intentional structure (objectives, gated areas, secret routes), and optionally
AI-authored theming/naming — without ever sacrificing the navigability guarantee.

**Why this priority**: Depth and "wow" matter for retention and the "the AI builds
the world too" hook, but they layer on top of a working, navigable, endless baseline
(US1–US3). They are explicitly later phases.

**Independent Test**: With richer generation enabled, confirm levels show the added
variety/structure while still passing the same traversability verification.

**Acceptance Scenarios**:

1. **Given** richer generation enabled, **When** a level is generated, **Then** it
   exhibits the added variety/structure **and** still passes traversability
   verification.

---

### Edge Cases

- A seed yields an invalid level (unsealed, disconnected, unreachable content) →
  detected by verification and regenerated; never presented to the agent.
- Degenerate parameters (too few/many rooms, impossible sizes) → clamped to sane
  ranges so generation always returns a valid level.
- Generation/verification must be fast enough not to stall the run between levels.
- The spawn area must be safe (the agent is not killed before it can act).
- Every enemy and item must be reachable, not just present.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST generate a complete, playable level from a seed value.
- **FR-002**: Every generated level MUST be fully traversable — every area, enemy,
  and item is reachable from the spawn (no unreachable or trapping regions).
- **FR-003**: Each generated level MUST include a safe spawn, enemies to fight, and
  items to collect, placed so the agent must move through the level to engage them.
- **FR-004**: Generation MUST use only original/libre content (no third-party
  copyrighted assets), consistent with the project's licensing pillar.
- **FR-005**: The same seed (and parameters) MUST always produce an identical level.
- **FR-006**: The system MUST verify each level is valid and fully traversable
  **before** it is used, and regenerate any level that fails — an invalid level is
  never presented to the agent.
- **FR-007**: The agent MUST be able to play a generated level using only its
  automatic navigation, with no hand-authored navigation data for that level.
- **FR-008**: Generation MUST expose parameters controlling level size, connectivity,
  and population, so variety can scale (and later map to difficulty/progression).
- **FR-009**: Generated levels MUST load in the game engine and be observable in the
  watch view (lit, navigable, populated).
- **FR-010**: The system SHOULD support, in later phases, richer geometry (authored
  building blocks), intentional structure (objectives, gating, secret routes), and
  optional AI-driven theming/naming — each without weakening FR-002.

### Key Entities

- **Generated Level**: a self-contained, playable map — geometry plus spawn, enemies,
  items, and lighting — uniquely identified by its seed and parameters.
- **Generation Parameters**: the knobs that shape a level (size, room count,
  connectivity/loopiness, population density, difficulty); also the future
  progression axis.
- **Level Rotation**: the ongoing supply of generated levels the agent plays through,
  enabling endless content.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A fresh, playable level is available for every run, indefinitely — the
  idle loop never runs out of content, with no required repeats.
- **SC-002**: 100% of levels presented to the agent are fully traversable; zero
  soft-locks caused by unreachable or trapping geometry.
- **SC-003**: On a sample of generated levels, the agent — with no hand-authored
  navigation data — covers the level and engages enemies within the run's time limit,
  at a rate comparable to its performance on the hand-made test level.
- **SC-004**: The same seed reproduces an identical level 100% of the time.
- **SC-005**: Generated levels load and are visibly playable in the watch view (lit,
  navigable, populated) for every level presented.
- **SC-006**: ≥95% of random seeds yield a valid level on first generation (the
  remainder auto-regenerated), so a new level is effectively always ready when needed.

## Assumptions

- The agent's existing automatic navigation (committed exploration + graph routing)
  is the consumer; generated levels must satisfy what it needs to traverse — primarily
  full connectivity and engine-walkable space.
- Levels are produced in the project's engine's native map format and load without
  per-map authoring.
- Building blocks are original/libre (LibreQuake textures + the project's libre
  monsters/items).
- Phase 1 targets simple, reliably-navigable levels; geometric and structural richness
  (authored kits, grammar, AI theming) are explicitly later phases (US4).
- Playability verification reuses the existing headless simulation + telemetry harness
  to confirm the agent can actually navigate and fight a level.
- "Endless" for Phase 1 means a new level per seed; in-session chaining of one level
  to the next is a follow-up.
