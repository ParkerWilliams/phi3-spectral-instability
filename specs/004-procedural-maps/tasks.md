---

description: "Task list for Procedural Map Generation (Phase 1)"
---

# Tasks: Procedural Map Generation

**Input**: Design documents from `/specs/004-procedural-maps/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/mapgen.md

**Tests**: Included — verification (static asserts + dynamic sim) is a core requirement
(FR-006, SC-002/003/006), so test tasks are first-class here.

**Organization**: grouped by user story. US1 (generate a valid level) and US2 (the agent
plays it) are both **P1** and together form the watchable MVP.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no incomplete-task deps)
- **[Story]**: US1 / US2 / US3 / US4
- Exact file paths included

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: stand up the generator package + the compile toolchain.

- [X] T001 Scaffold the `mapgen/` uv package (`pyproject.toml`, `idledoom_mapgen/__init__.py`, `tests/`) mirroring `sims/` layout
- [X] T002 [P] Configure ruff + mypy for `mapgen/` matching `sims/` config (in `mapgen/pyproject.toml`)
- [ ] T003 Vendor **prebuilt** ericw-tools (`qbsp`/`vis`/`light`, latest 2.x) into `tools/ericw-tools/` with a `tools/ericw-tools/README.md` fetch note — download per-OS binaries, **never build on the droplet** (constitution)
- [X] T004 [P] Add Justfile targets `mapgen`, `mapgen-compile`, `mapgen-verify` (wire to the CLI/scripts created later)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the shared data structures every story builds on.

**⚠️ CRITICAL**: no user-story work begins until this phase is complete.

- [X] T005 Implement `GenParams` (fields + defaults + clamping) and the single seeded `random.Random(seed)` in `mapgen/idledoom_mapgen/params.py` (per data-model.md)
- [X] T006 Define the shared dataclasses `Room`, `RoomGraph`, `Grid`, `Brush`, `MapEntity`, `BrushSet`, `EntitySet`, `MapModel` in `mapgen/idledoom_mapgen/model.py` (per data-model.md)

**Checkpoint**: params + data model importable; user stories can begin.

---

## Phase 3: User Story 1 - A fresh, playable level every run (Priority: P1) 🎯 MVP

**Goal**: `mapgen --seed S` deterministically produces a **valid, navigable-by-construction**
`.map` (rooms + corridors sealed into libre geometry, populated, statically verified).

**Independent Test**: generate a seed and run the static verifier — reachability/seal/
overlap/spawn-safety all pass, and the same seed re-generates byte-identically. No engine
needed.

### Tests for User Story 1 ⚠️ (write first, ensure they FAIL)

- [X] T007 [P] [US1] Static-verification tests (reachability flood-fill == open set; sealed hull; no entity overlap; spawn room monster-free; every monster/item reachable) in `mapgen/tests/test_verify.py`
- [X] T008 [P] [US1] Determinism test (same `(seed, params)` → byte-identical `.map`) in `mapgen/tests/test_determinism.py`

### Implementation for User Story 1

- [X] T009 [US1] Implement `layout()` — non-overlapping room placement + connectivity graph (MST over centers + `loopiness` extra edges) + corridor rasterization → `Grid` — in `mapgen/idledoom_mapgen/layout.py`
- [X] T010 [US1] Implement `geometry()` — `Grid` → sealed wall brushes from solid-adjacent-to-open cells (greedy rectangle merge) + floor/ceiling slabs — in `mapgen/idledoom_mapgen/geometry.py`
- [X] T011 [US1] Implement `entities()` — place `info_player_start`, `monster_army`/`monster_dog`/`monster_knight`, `item_health`/`item_shells`/`weapon_supershotgun`, and one `light` per room, enforcing the placement invariants — in `mapgen/idledoom_mapgen/entities.py`
- [X] T012 [US1] Implement `verify()` — the static invariants from data-model.md (reachability, spawn safety, content reachable, no overlap, sealed) — in `mapgen/idledoom_mapgen/verify.py`
- [X] T013 [US1] Implement `emit_map()` — `.map` text: `worldspawn` with `"wad"`, axis-aligned box brushes (6 planes, LibreQuake texture names), then entities — in `mapgen/idledoom_mapgen/mapfile.py`
- [X] T014 [US1] Implement `cli.py` — `mapgen --seed S [--out] [--params k=v]`, the **reject-and-reseed** loop (only ever writes a static-verified `.map`), summary print — in `mapgen/idledoom_mapgen/cli.py`

**Checkpoint**: `just mapgen 1234` writes a verified `gen_1234.map`; `uv run pytest` green.

---

## Phase 4: User Story 2 - The agent navigates levels no human designed (Priority: P1)

**Goal**: a generated level compiles to `.bsp`, loads in FTEQW, and the agent — with **no
hand-authored nav data** — covers it and fights, proven by the sim telemetry.

**Independent Test**: compile one generated seed, run the agent through the feature-001
sim, and confirm `waypoints` climb, `shots_fired > 0`, `kills ≥ 1` (SC-003).

### Tests for User Story 2 ⚠️

- [ ] T018 [P] [US2] Dynamic-verification test (run the agent on a compiled generated seed; assert `waypoints` increase, `shots_fired > 0`, `kills ≥ 1`) in `sims/tests/test_generated_nav.py`

### Implementation for User Story 2

- [X] T015 [US2] Implement the compile helper — `mapgen` → `qbsp`→`vis`→`light` → `gen_S.bsp` → game `maps/` dir, with **leak detection** (a `.pts`/"leaked" result is a hard failure) — in `scripts/mapgen_compile.sh` (wired to Justfile `mapgen-compile`)
- [ ] T016 [US2] Pin the LibreQuake `.wad` + wall/floor/ceiling texture names; pass the WAD to `qbsp`; record texture provenance in `docs/licenses.md`
- [X] T017 [US2] Add `sims/configs/gen.toml` and `--map gen_S` support to the harness so the sim/watch run the agent on a generated level

**Checkpoint**: `just watch gen_1234` shows the agent explore + fight a never-seen level; the sim test passes.

---

## Phase 5: User Story 3 - Reproducible and auto-verified at scale (Priority: P2)

**Goal**: every level is reproducible and **guaranteed valid before use**, across many
seeds — invalid levels are never emitted.

**Independent Test**: run a batch of N seeds; all pass static verification, ≥95% on the
first generation (the rest auto-reseeded), and each seed reproduces identically.

- [X] T019 [P] [US3] Batch property test over N seeds (all pass static verify; ≥95% valid on first generation — SC-006) in `mapgen/tests/test_batch.py`
- [X] T020 [US3] Harden the reject-and-reseed loop in `mapgen/idledoom_mapgen/cli.py` — bounded re-rolls, clear diagnostic + non-zero exit on exhaustion; clamp degenerate `GenParams`
- [X] T021 [US3] Add `mapgen` pytest + ruff + mypy to CI (`.github/workflows/ci.yml`) and `just check`, so generation regressions are caught

**Checkpoint**: `cd mapgen && uv run pytest` green across the batch; CI runs it.

---

## Phase 6: User Story 4 - Variety and richness grow over time (Priority: P3)

**Goal**: record the richer-generation trajectory and the difficulty/progression mapping.
The actual richer geometry (prefab kit), intentional structure (grammar), and AI theming are
the design's **Phase 2/3** — a future feature (005+), out of scope for this build. The
in-scope sliver is param-driven variety, already delivered by `GenParams` (T005).

- [X] T022 [US4] Document the Phase 2/3 trajectory and map `GenParams` (size/count/density/loopiness) onto difficulty/progression in `docs/progression.md` and `docs/design.md` §6; defer geometry/grammar/LLM-theming to a future spec

**Checkpoint**: the variety/difficulty axis and future phases are recorded; no Phase 2/3 code in this build.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T023 [P] Write `docs/adr/0004-procedural-map-generation.md` — the mechanism decision (external `.map` + ericw-tools vs engine-side; libre constraint; droplet/local split)
- [X] T024 [P] Update `docs/design.md` §6 to link ADR-0004; confirm `docs/licenses.md` records the LibreQuake texture provenance
- [ ] T025 Confirm the ericw-tools Linux prebuilt runs headless on the droplet (resolves the open research item — decides CI-compile vs local-only)
- [ ] T026 Run `quickstart.md` end-to-end locally (gen → compile → watch → sim) and confirm SC-001…SC-006

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)**: no deps — start immediately.
- **Foundational (P2)**: depends on Setup — **blocks all user stories**.
- **US1 (P3 phase)**: depends on Foundational. The technical core.
- **US2 (P4 phase)**: depends on Foundational + **US1** (it compiles/runs US1's output).
- **US3 (P5 phase)**: depends on US1 (batch-verifies the generator). Independent of US2.
- **US4 (P6 phase)**: docs-only; depends on US1 existing (so params are real).
- **Polish (P7)**: after the desired stories are complete.

### User Story Dependencies

- **US1 (P1)**: needs only Foundational — fully testable on its own (static verify).
- **US2 (P1)**: needs US1 (its output) — then independently testable via the sim.
- **US3 (P2)**: needs US1 — independent of US2.
- **US4 (P3)**: docs; deferred richer-generation to a future feature.

### Parallel Opportunities

- Setup: T002, T004 in parallel; T003 (vendor binaries) independent.
- US1 tests T007, T008 in parallel (write first). Within US1 impl, T009→T010→T011 are
  roughly sequential (grid → geometry → entities), but T012 (verify) and T013 (emit) can be
  developed in parallel once the model + grid exist.
- US3 (T019) and US2 can proceed in parallel once US1 is done (different files).
- Polish T023, T024 in parallel.

---

## Implementation Strategy

### MVP (the watchable demo) = US1 + US2

1. Phase 1 Setup → Phase 2 Foundational.
2. Phase 3 (US1): the generator emits a static-verified level. **STOP & VALIDATE** with
   `uv run pytest` (no engine needed — fully droplet-checkable).
3. Phase 4 (US2): compile + run it; **watch the agent play a generated map** and confirm
   the sim telemetry. This is the demo that proves "endless content" **and** "auto-nav on
   unseen maps" at once.

### Incremental delivery

- US1 → US2 (MVP demo) → US3 (scale/robustness + CI) → US4 (record the trajectory) →
  Polish (ADR, docs, droplet-compile confirmation, quickstart validation).

### Notes

- `[P]` = different files, no incomplete-task deps.
- Generation + static tests run on the droplet (`uv`); compile + engine run are local.
- Commit after each task or logical group; keep `main`-equivalent green.
