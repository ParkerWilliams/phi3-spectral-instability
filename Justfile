# Task runner. Run `just` with no args to list available commands.
# All commands assume you're at the repo root.

# Default: show available recipes
default:
    @just --list

# === Primary dev loop ===

# Build everything and launch the host app + engine
run: build
    @echo "Launching host app..."
    cd host && cargo run --release

# Same as run, but wipe save state first (test progression from zero)
run-fresh: build
    @echo "Wiping save state..."
    rm -f data/save.sqlite
    cd host && cargo run --release

# Watch the agent play in a GL window (LOCAL ONLY — needs a display; the droplet
# can't run this, and the GL client needs audio dev libs the server build doesn't:
# e.g. libopus-dev libvorbis-dev libxxf86dga-dev libxcb*-dev — install if the build
# fails on missing headers). Lightweight observation path (no Tauri host yet):
# a listen server that autostarts the named agent on a combat-reliable map, with
# the agent's good behaviors on (sim_mode) but auto-quit suppressed (sim_watch) so
# the window survives death/timeout. First-person bot-cam: ride the agent with
# `impulse 103` (bound to O below, or type it in the ~ console).
#
# NOTE maxplayers 2: DynamicWaypoint needs max_clients >= 2 (bot_way.qc). The human
# host is client 1, the agent client 2. If the agent just loiters, confirm this took
# effect (FTE cvar name; adjust if your build differs).
watch: build-engine build-quakec
    @echo "Launching watch session (first-person bot-cam — press O / 'impulse 103')..."
    @BIN=$(ls engine/engine/release/fteqw-gl* engine/engine/fteqw-gl* 2>/dev/null | head -1); \
     if [ -z "$BIN" ]; then echo "ERROR: no fteqw-gl binary — did build-engine succeed? (audio dev libs)"; exit 1; fi; \
     echo "Using client: $BIN"; \
     "$BIN" -basedir "$(pwd)" -game quakec \
       +set deathmatch 0 +set coop 0 +set skill 1 +set sv_cheats 1 \
       +set maxplayers 2 +set sim_mode 1 +set sim_watch 1 +set sim_time_limit 0 \
       +set sim_nav_regen 1 \
       +bind o "impulse 103" \
       +map lq_e1m2
    @echo "NOTE: press O once the level loads — that rides the agent (first person)"
    @echo "      AND turns your host into a non-solid cam so it stops blocking the agent."

# Build all components
build: build-engine build-quakec build-host

# Build only what the headless sim needs: dedicated server + gamecode + harness env.
# (No GL client, no frontend.) Compiles C — LOCAL/CI only, never on the droplet.
build-sim: build-engine-sv build-quakec
    cd sims && uv sync

# === Component builds ===

# NOTE: building the engine and fteqcc compiles C — do this LOCALLY, never on
# the shared 1GB droplet (it will OOM). The FTEQW submodule nests its source one
# level down, so paths are engine/engine/... (submodule root is engine/).

build-engine:
    @echo "Building FTEQW GL client (LOCAL ONLY — do not run on the droplet)..."
    make -C engine/engine gl-rel -j$(nproc 2>/dev/null || sysctl -n hw.ncpu)
    @echo "Built client -> engine/engine/fteqw-gl*  (exact suffix is target-dependent)"

# Dedicated server (headless) — the binary the sim harness launches (ADR-0001, R1).
# LOCAL/CI only; the droplet may run the resulting binary but never builds it.
build-engine-sv:
    @echo "Building FTEQW dedicated server (LOCAL ONLY — do not run on the droplet)..."
    make -C engine/engine sv-rel -j$(nproc 2>/dev/null || sysctl -n hw.ncpu)
    @echo "Built dedicated server -> engine/engine/fteqw-sv*  (exact suffix is target-dependent)"

# fteqcc ships inside the FTEQW tree (engine/engine/qclib). build-quakec needs it.
build-fteqcc:
    @echo "Building fteqcc QuakeC compiler (LOCAL ONLY)..."
    make -C engine/engine/qclib
    @echo "Built compiler -> engine/engine/qclib/fteqcc.bin"

build-quakec: build-fteqcc
    @echo "Compiling QuakeC (rerelease base + FrikBot) -> progs.dat..."
    cd quakec && ../engine/engine/qclib/fteqcc.bin
    @echo "Built gamecode -> quakec/progs.dat"

build-host:
    @echo "Building Tauri host app..."
    cd host/ui && npm install && npm run build
    cd host && cargo build --release

# === Sim harness ===

# Run the current tuning sim config
sim:
    cd sims && uv run harness.py run --config configs/current.toml

# Quick smoke test that the sim pipeline works end-to-end (fast CI gate).
# Needs the `smoke` subcommand + configs/smoke.toml (feature 001 US4).
sim-smoke:
    cd sims && uv run harness.py smoke --config configs/smoke.toml

# Run an overnight batch (nightly tuning matrix).
# DEFERRED: multi-run aggregation is out of scope for feature 001 (FR-014 / R10).
# The single-run primitive (`just sim`) is the foundation a batch runner will use.
sim-batch:
    @echo "sim-batch is deferred — see specs/001-headless-sim-telemetry (FR-014, R10)."

# === Quality gates ===

# Run all checks (CI runs this)
check: check-rust check-quakec check-frontend check-python

check-rust:
    cd host && cargo fmt --check
    cd host && cargo clippy -- -D warnings

check-quakec:
    @echo "QuakeC lint: TODO"

check-frontend:
    cd host/ui && npm run lint
    cd host/ui && npm run typecheck

check-python:
    cd sims && uv run ruff check .
    cd sims && uv run mypy .

# Run all tests
test:
    cd host && cargo test
    cd sims && uv run pytest

# === Maintenance ===

# Clean all build artifacts
clean:
    cd engine && make clean || true
    cd host && cargo clean
    rm -rf host/ui/dist host/ui/node_modules
    rm -rf sims/results/_tmp

# Update submodules to their pinned revisions
sync-deps:
    git submodule update --init --recursive

# Format everything
fmt:
    cd host && cargo fmt
    cd host/ui && npm run fmt
    cd sims && uv run ruff format .
