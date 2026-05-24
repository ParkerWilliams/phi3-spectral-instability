# SETUP

Fresh-clone-to-running instructions. If this document is wrong or incomplete,
that's a bug — fix it as part of whatever you were doing.

## Prerequisites

### All platforms

- **Git** with submodule support
- **Rust** (stable, via rustup) — for the Tauri host app
- **Node.js 20+** and a package manager — for the frontend
- **Just** task runner — `cargo install just` or via your package manager
- **A C toolchain** — for building FTEQW
- **Python 3.11+** — for the sim harness and helper scripts

### Linux (Ubuntu 24.04 reference)

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  libwebkit2gtk-4.1-dev \
  libssl-dev \
  libgtk-3-dev \
  libayatana-appindicator3-dev \
  librsvg2-dev \
  libsdl2-dev \
  libgl1-mesa-dev \
  libasound2-dev \
  pkg-config
```

### macOS

```bash
xcode-select --install
brew install just node
# Rust via rustup.rs
```

### Windows

- Visual Studio Build Tools (C++ workload)
- WebView2 (usually preinstalled on modern Windows)
- Rust, Node, Just via their installers

## First-time setup

```bash
# Clone with submodules
git clone --recurse-submodules <repo-url>
cd <repo>

# If you forgot --recurse-submodules:
git submodule update --init --recursive

# Install frontend deps
cd host/ui && npm install && cd ../..

# Build everything (first build takes a while: ~5-10 min)
just build

# Verify it runs
just run
```

If `just run` opens a window with the engine on the left and a placeholder
upgrade panel on the right, you're set up.

## Current state: engine + bot slice

The host app (`just run`) does not exist yet. What builds today is the FTEQW
engine and a `progs.dat` (rerelease GPLv2 QuakeC + FrikBot), which you launch
directly. **All of this compiles C — build on your local machine, never on the
1 GB droplet (it will OOM).**

```bash
# Pull the FTEQW engine submodule (shallow keeps the clone light)
git submodule update --init --depth 1 engine

just build-fteqcc     # -> engine/engine/qclib/fteqcc.bin
just build-engine     # -> engine/engine/fteqw-gl*   (GL client)
just build-quakec     # -> quakec/progs.dat
```

The engine source nests one level down: the submodule root is `engine/`, the
FTEQW C tree is `engine/engine/` (so `make` runs in `engine/engine`).

### Running it (needs Quake game data)

`progs.dat` is gamecode only — to watch the bot you need a Quake game-data dir
(maps/models/sounds). We will vendor LibreQuake (GPLv2) as `assets/libre-quake/`
in a later slice; for now point FTEQW at a libre/owned data dir you have
locally. **Do not** use id's original `pak0.pak`/`pak1.pak` (not
redistributable — see `docs/licenses.md`).

```bash
mkdir -p <quakedir>/idledoom
cp quakec/progs.dat <quakedir>/idledoom/
engine/engine/fteqw-gl* -basedir <quakedir> -game idledoom +map dm3
# in the console:  impulse 100   (add a bot)
```

FrikBot ships waypoints for `dm1`–`dm6`; `dm3` is a good first smoke test.
The integration is not yet compile-verified — see `quakec/INTEGRATION.md` for
the known open issues to resolve at first build.

## Common issues

### `engine/` is empty

You cloned without submodules. Run:

```bash
git submodule update --init --recursive
```

### Tauri build fails on Linux with webkit errors

You're missing system deps. See the Linux prerequisites above. Note that
`libwebkit2gtk-4.1-dev` is required for Tauri v2; older guides may reference
`4.0`.

### FTEQW build fails

Check `engine/README.md` (the upstream FTEQW readme) for engine-specific
build requirements. Our build wraps theirs but doesn't replace it.

### `just` is not found

Install it: `cargo install just`, or `brew install just`, or
`apt install just` on recent Ubuntu.

### LibreQuake assets not loading

Confirm `assets/libre-quake/` is populated (it's a submodule). The engine
expects `pak0.pak` and friends at a specific path; see
`scripts/link-assets.sh`.

## Droplet-specific setup

For the shared dev droplet:

```bash
# As the dev user (not root)
git clone --recurse-submodules <repo-url>
cd <repo>

# Headless sim harness only — no game runtime on the droplet
just build-sim

# Start (or attach to) the shared tmux session
tmux new -s dev   # or: tmux attach -t dev
```

The droplet does not need the full host app build, frontend deps, or
graphics libraries. A `just build-sim` target installs only what's needed
for headless sim runs and Claude Code editing.

> ⚠️ **Never compile on the droplet (1 GB RAM, no swap).** `just build-engine`,
> `just build-fteqcc`, `just build-quakec`, and the engine-compiling part of
> `just build-sim` all run `make` over C and will OOM here. Edit, run git, and
> do lightweight scripting on the droplet; build and run on your local machines.
> Any Python on the droplet must go through a `uv`-managed venv (`uv run`).

## Verifying your setup

```bash
just check        # fmt, lint, typecheck — should be clean
just test         # unit tests — should pass
just build        # full build — should succeed
just sim --smoke  # 10-second sim — should produce telemetry
```

If all four pass, you're good.

## When to update this document

- You hit a setup issue not listed above
- You add a new dependency
- A platform's instructions need to change
- A new contributor reports confusion

Treat `SETUP.md` as the canonical truth. If it lies, fix it.
