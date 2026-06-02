# Sim harness — headless run → telemetry (feature 001)

Runs the FrikBot agent headless on a map and writes schema-valid telemetry
(per-run `*.summary.json` + per-event `*.events.jsonl`). See
`specs/001-headless-sim-telemetry/` for the spec, and `docs/telemetry.md` for the
output schema.

## Two hard rules

1. **Build locally or in CI — never on the droplet.** The ~1 GB dev droplet has
   no swap and OOMs compiling the FTEQW engine. It may *run* sims once `fteqw-sv`
   + `progs.dat` exist; it must not build them. (Python tooling via `uv` is fine
   on the droplet.)
2. **Python is always `uv` — never raw `python`/`pip`.** Every command below uses
   `uv run`, which manages the venv from `pyproject.toml`.

## One-time build (local/CI)

```bash
just build-sim     # fteqcc -> quakec/progs.dat, fteqw-sv (sv-rel), then `uv sync`
```

Then provide map data: LibreQuake release paks in `id1/` (gitignored runtime
data) — see `docs/licenses.md` and, for agent navigation, `docs/waypointing.md`.
`make sv-rel` writes `engine/engine/release/fteqw-sv`; the launcher finds it there
(or set `$IDLEDOOM_FTEQW_SV`).

## Run

```bash
just sim                              # run configs/current.toml
uv run harness.py run --config configs/current.toml --time-limit 20 \
                      --bot.bot_accuracy 0.9     # CLI overrides (clamped)
just sim-smoke                        # fast chain-health CI gate (exit 0 = healthy)
```

Output: `results/<batch_id>/<run_id>.summary.json` + `.events.jsonl` (the
`results/` tree is gitignored). Inspect with `jq`, or:

```bash
grep -o '"outcome": "[a-z]*"\|"shots_fired": [0-9]*' results/*/*.summary.json
```

## Lint / type / test

```bash
cd sims
uv run ruff check .
uv run mypy .
uv run pytest        # schema, reconciliation, clamp, outcome, parse, smoke
```

## Layout

- `idledoom_sim/` — package: `config` (TOML+CLI→clamped `bot_config`+hash),
  `botstats` (cvar catalogue/clamping), `launcher` (drives `fteqw-sv`),
  `telemetry` (parse `@EVT` → events → aggregate stats), `outcome`,
  `writer` (paths, summary/events write + schema validation)
- `configs/` — `current.toml` (run), `smoke.toml` (CI)
- `schema/` — canonical copies of the JSON Schemas (mirror `contracts/`)
- `tests/`, `harness.py` (the `run` / `smoke` CLI)
