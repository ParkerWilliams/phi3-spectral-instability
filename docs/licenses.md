# Asset Licenses and Attribution

Every asset shipped with the project must be listed here with its license
and source. If a license is unclear, the asset doesn't ship.

## Bases

### Engine: FTEQW

- **License:** GPLv2 (root `LICENSE` in the repo)
- **Source:** https://www.fteqw.org/ — official GitHub mirror
  https://github.com/fte-team/fteqw
- **Vendoring:** git submodule under `engine/`, pinned to commit
  `3584377302cda4bd1b6950b126d147451895a1da`. fteqcc (the QuakeC compiler)
  builds from `engine/engine/qclib` in the same tree.
- **Implications:** Our QuakeC code that links against FTEQW is effectively
  GPLv2. Confirm with a lawyer before commercial release.

### Game data: LibreQuake

- **License:** ⚠️ **UNRESOLVED — not cleared for release.** The repo describes
  "art under the BSD license" but ships **no `LICENSE` file** (GitHub reports
  `NOASSERTION`); code is typically GPLv2. The earlier "GPLv2 (game data and
  code)" claim was **not substantiated**. Confirm the exact code/art split with
  upstream before any release (CLAUDE.md: "if a license is unclear, the asset
  doesn't ship").
- **Source:** https://github.com/lavenderdotpet/LibreQuake (formerly
  `MissLavender-LQ/LibreQuake`, now redirects). Release **v0.09-beta**.
- **Vendoring (as-built, feature 001):** prebuilt release paks (`mod.zip` →
  `lq1/pak0.pak` + `pak1.pak`) placed in `id1/` as **runtime data (gitignored)**.
  The git repo holds only `.map`/`.wad` sources that need a map compiler, so a
  plain source submodule isn't directly runnable — the originally planned
  `assets/libre-quake/` submodule is deferred pending the license call above.
- **Attribution:** see upstream `CREDITS` / `AUTHORS`. Mirror into our
  `CREDITS` file before release.

### Game logic base: Quake rerelease QuakeC

- **License:** GPLv2 (`quakec/COPYING.txt`, vendored from upstream)
- **Source:** https://github.com/id-Software/quake-rerelease-qc — the `quakec/`
  (id1 base campaign) tree only
- **Vendoring:** copied into `quakec/` with our FrikBot modifications, pinned to
  commit `7bcbd29c9934e8523974263de50b3ae90b5d2605`
- **Attribution:** id Software copyright headers preserved in each `.qc`

### Bot baseline: FrikBot X v0.10.2

- **License:** **Public Domain** ✅ (confirmed — stated in `src/install.txt` and
  the header of every `frikbot/*.qc`). One condition: the notice must be
  reproduced in its entirety, so do not strip the file headers. GPLv2-compatible.
- **Source:** FrikBot X v0.10.2 (`fbxc.zip`), by Ryan "FrikaC" Smith — archived
  at https://github.com/Jason2Brownlee/QuakeBotArchive (`bin/fbxc.zip`)
- **Vendoring:** QuakeC source under `quakec/frikbot/` (+ `quakec/waypoints/`)
  with our modifications; integrated into the rerelease base above
- **Attribution:** original author notice preserved verbatim in source headers

## Maps

| File | Map | Author | License | Source | Notes |
|------|-----|--------|---------|--------|-------|
| lq_e1m1.bsp | lq_e1m1 | LibreQuake team | ⚠️ see "Game data: LibreQuake" above (unresolved BSD-art / GPL split) | https://github.com/lavenderdotpet/LibreQuake — v0.09-beta `mod.zip` | Confirmed live 2026-06-02 (feature 001 US1): loads with our `progs.dat`, agent autostarts, telemetry emits, schema-valid `timeout` summary written. First SP level (has `info_player_start`; launcher runs `deathmatch 0`). **No `trigger_secret` → `secrets_total=0`** — choose a secret-bearing map for US2 secret tests. Paks are runtime data in `id1/` (gitignored), not committed. |

Format: when a map is added, append a row with full provenance. Don't ship
a map whose license you cannot cite here.

## Custom assets

| File | Type | Author | License | Notes |
|------|------|--------|---------|-------|
| (none yet) | | | | |

For assets we create ourselves, decide on a project-wide license (likely
CC-BY-SA 4.0 to match the libre spirit) and apply it uniformly.

## Third-party libraries

Tracked via standard tooling (`cargo.lock`, `package-lock.json`,
`requirements.txt`). License audit before each release using a tool like
`cargo-deny` or `license-checker`. Add license-incompatible deps to a
"do not use" list here as we discover them.

## License-incompatible (do not ship)

This is an original/libre game. We do not ship id Software's assets, original
maps, monsters, or the "Quake" trademark; keep names/art original or libre.
(Building on id's GPLv2 *code* — FTEQW, the rerelease QuakeC — is fine; their
*content* and brand are not.)

- Original Quake shareware `pak0.pak` — id Software copyright, free to
  play but not redistribute
- Quake registered `pak1.pak` — id Software copyright, definitely not
  redistributable
- Most commercial Quake mods — case-by-case, usually no

## Procedurally generated maps (feature 004)

Generated `.map`/`.bsp` levels (the `mapgen/` generator) are **derived works of
LibreQuake textures** (libre) plus our libre monster/item content — no id assets. The
exact LibreQuake wall/floor/ceiling texture names are pinned when the compile pipeline
is wired locally (T016) and listed here at that point. The generator code itself is our
original GPLv2 work. Generated levels are runtime output (gitignored, like other build
artifacts); if any are ever curated and shipped, log them here.

## Release checklist

Before any public release:

- [ ] Every file in `assets/` is listed here or in upstream submodule credits
- [ ] License audit on all language dependencies
- [ ] `CREDITS` file generated and reviewed
- [ ] Top-level `LICENSE` reflects the chosen project license
- [ ] No id Software original assets present anywhere in the repo or build
