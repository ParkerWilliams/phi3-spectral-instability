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

- **License:** GPLv2 (game data and code)
- **Source:** https://github.com/MissLavender-LQ/LibreQuake
- **Vendoring:** git submodule under `assets/libre-quake/`
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
| (none yet) | | | | | |

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

- Original Quake shareware `pak0.pak` — id Software copyright, free to
  play but not redistribute
- Quake registered `pak1.pak` — id Software copyright, definitely not
  redistributable
- Most commercial Quake mods — case-by-case, usually no

## Release checklist

Before any public release:

- [ ] Every file in `assets/` is listed here or in upstream submodule credits
- [ ] License audit on all language dependencies
- [ ] `CREDITS` file generated and reviewed
- [ ] Top-level `LICENSE` reflects the chosen project license
- [ ] No id Software original assets present anywhere in the repo or build
