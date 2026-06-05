# Quickstart: Procedural Map Generation (Phase 1)

Generate a libre, navigable level from a seed, compile it, and watch the agent play it.

> **Where things run:** generation + static verification are light Python (`uv`) and run
> **anywhere, including the droplet**. Compiling (`qbsp/vis/light`) and running the engine
> are **local** (the droplet can't run the engine, and ericw-tools is vendored, not built,
> there).

## 1. Generate a level (droplet-OK)

```bash
cd ~/idledoom
just mapgen 1234                 # mapgen --seed 1234 -> gen_1234.map  (only if it passes static verify)
# or tune it:
just mapgen 1234 room_count=12 loopiness=0.3
```

Output: `gen_1234.map` + a summary line (`rooms=12 open_cells=... monsters=... items=...`).
Re-running the same seed produces a byte-identical `.map`.

## 2. Static-verify a batch (droplet-OK, CI)

```bash
cd ~/idledoom/mapgen
uv run pytest                    # reachability, spawn safety, content reachable, no-overlap, sealed, determinism
```

Every seed in the test set must pass; a failing seed is auto-rejected by the generator, so
this is a guard against generator regressions.

## 3. Compile to BSP (local)

```bash
just mapgen-compile 1234         # gen_1234.map -> qbsp -> vis -> light -> gen_1234.bsp -> game maps dir
```

Needs the vendored ericw-tools (`tools/ericw-tools/`) and the LibreQuake `.wad`. A `qbsp`
**leak** is a hard failure for that seed (it should have been rejected in step 1; if not,
file a bug).

## 4. Watch the agent play it (local)

```bash
just watch gen_1234              # FTEQW first-person bot-cam on the generated level
```

You should see the agent spawn safely, **explore the whole level** (committed exploration +
graph routing), and **fight** the monsters — on a map no human authored.

## 5. Dynamic-verify with the sim (local/CI)

```bash
cd ~/idledoom/sims
uv run harness.py run --config configs/gen.toml --map gen_1234 --time-limit 60
grep -o '"shots_fired": [0-9]*\|"kills": [0-9]*\|"map_coverage": [0-9.]*' results/*/*.summary.json | tail
```

Expected (SC-003): `waypoints` climbed, `shots_fired > 0`, `kills ≥ 1` — the agent
navigated + fought the generated level, the same bar it clears on `lq_e1m1`.

## Success looks like

- `just mapgen <seed>` always yields a `.map` that passes static verify (≥95% on the first
  try; the rest re-rolled) — SC-006.
- The compiled level loads, is lit, and is fully traversable — SC-002/SC-005.
- The agent covers it and fights, with **no hand-authored nav data** — SC-003 / US2.
- Same seed → identical level — SC-004.
