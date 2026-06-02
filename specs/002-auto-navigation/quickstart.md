# Quickstart: Automatic Agent Navigation

Goal: the agent navigates an **un-waypointed** map on its own, reaches combat, and
navigation competence visibly changes how much of the level it covers — all
verified through feature 001's headless sim. Build locally/CI, never on the droplet.

## 0. Build

```bash
just build-quakec        # progs.dat with the nav changes
just build-sim           # (if needed) fteqw-sv + harness env
# LibreQuake map data in id1/ (docs/licenses.md); NO maps/<map>.way needed
```

## 1. Navigate + reach combat (US1 — P1)

```bash
cd sims
# pick a map with reachable enemies and NO .way file:
uv run harness.py run --config configs/current.toml --time-limit 60
grep -o '"shots_fired": [0-9]*\|"kills": [0-9]*\|"map_coverage": [0-9.]*' results/*/*.summary.json | tail
```

**Expected:** `shots_fired > 0`, `kills ≥ 1`, `map_coverage` well above the
spawn-only baseline — with no waypoint file authored. A `maps/<map>.way` is written
on first run and reused next time (force fresh gen with `--bot`-style
`sim_nav_regen 1` via the launcher).

## 2. Never-seen map, zero setup (US2 — P2)

```bash
uv run harness.py run --config configs/current.toml --map <some_other_lq_map> --time-limit 60
```

**Expected:** navigates + reaches combat with zero map-specific steps.

## 3. Competence is a visible axis (US3 — P2)

```bash
for a in 0.1 0.9; do for i in 1 2 3; do
  uv run harness.py run --config configs/current.toml --time-limit 60 --bot.bot_map_awareness $a >/dev/null
done; done
grep -o '"bot_map_awareness": [0-9.]*\|"map_coverage": [0-9.]*\|"time_to_exit_sec": [0-9.null]*' results/*/*.summary.json
```

**Expected:** higher `bot_map_awareness` → higher average `map_coverage` and/or
lower `time_to_exit_sec` (SC-003).

## 4. No softlocks (US4 — P3)

```bash
uv run harness.py run --config configs/current.toml --time-limit 30   # repeat across maps
echo $?     # always 0/terminal; the agent never wedges for the whole run
```

**Expected:** 100% of runs reach a terminal outcome within the limit (SC-004).

## 5. Unblocks feature-001 SC-004

With the agent now fighting, re-run the feature-001 accuracy comparison
(`--bot.bot_accuracy 0.1` vs `0.9`): higher accuracy → higher `stats.accuracy`.

## 6. Tests

```bash
cd sims && uv run pytest      # + new coverage-reconcile / nav-competence assertions
```
