# [working title TBD]

An idle game where you watch an AI get progressively better at a low-poly,
PS1-era FPS.

Built on the [FTEQW](https://www.fteqw.org/) engine with
[LibreQuake](https://github.com/MissLavender-LQ/LibreQuake) assets. Open source
and libre throughout — a low-poly, PS1-era FPS built from original/libre
content, using no id Software assets or trademarks.

## Concept

Two-panel interface. On the left, the engine runs and an AI agent plays our
low-poly PS1-era FPS. On the right, a config/upgrade menu where you spend currency
the agent earns — and tune how it behaves — to make it faster, smarter, more
accurate, and capable of new behaviors: rocket-jumping, weapon mastery, finding
secrets, taking risks. Progress unlocks harder maps and more advanced movement
and combat tech.

The fantasy: watching your friend get progressively better at a low-poly,
PS1-era FPS, on a several-hour-to-several-week arc.

## Status

Early development. Not yet playable. See `docs/design.md` for the design
direction and `docs/adr/` for architectural decisions.

## Building from source

See [`SETUP.md`](./SETUP.md).

```bash
git clone --recurse-submodules <repo-url>
cd <repo>
just run
```

## Project structure

- `engine/` — FTEQW (submodule)
- `quakec/` — game logic in QuakeC
- `host/` — Tauri app providing the dual-viewport UI
- `assets/` — LibreQuake base + curated maps
- `sims/` — headless simulation harness for bot tuning
- `docs/` — design doc, ADRs, schemas

## Contributing

Currently a two-person project; we'll open up contribution if and when it
makes sense. If you're curious, the design doc and ADRs are the best entry
point.

## License

GPLv2, forced by the FTEQW engine base (also GPLv2). A top-level `LICENSE`
will be added before first release. See `docs/licenses.md` for per-asset
attribution as we build it out.
