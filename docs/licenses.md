# Asset Licenses and Attribution

Every asset shipped with the project must be listed here with its license
and source. If a license is unclear, the asset doesn't ship.

## Bases

### Engine: FTEQW

- **License:** GPLv2
- **Source:** https://www.fteqw.org/ — https://sourceforge.net/p/fteqw/code/
- **Vendoring:** git submodule under `engine/`
- **Implications:** Our QuakeC code that links against FTEQW is effectively
  GPLv2. Confirm with a lawyer before commercial release.

### Game data: LibreQuake

- **License:** GPLv2 (game data and code)
- **Source:** https://github.com/MissLavender-LQ/LibreQuake
- **Vendoring:** git submodule under `assets/libre-quake/`
- **Attribution:** see upstream `CREDITS` / `AUTHORS`. Mirror into our
  `CREDITS` file before release.

### Bot baseline: FrikBot

- **License:** [confirm — historically permissive but verify]
- **Source:** Quake community archives (Quake Wiki has links)
- **Vendoring:** QuakeC source in `quakec/` with our modifications
- **Attribution:** preserve original author credits in source headers

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
