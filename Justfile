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

# Build all components
build: build-engine build-quakec build-host

# Build only what the droplet needs (no graphics, no frontend)
build-sim: build-engine build-quakec
    cd sims && pip install -r requirements.txt

# === Component builds ===

build-engine:
    @echo "Building FTEQW engine..."
    cd engine && make -j$(nproc 2>/dev/null || sysctl -n hw.ncpu)

build-quakec:
    @echo "Compiling QuakeC..."
    cd quakec && fteqcc

build-host:
    @echo "Building Tauri host app..."
    cd host/ui && npm install && npm run build
    cd host && cargo build --release

# === Sim harness ===

# Run the current tuning sim config
sim:
    cd sims && python harness.py run --config configs/current.toml

# Quick smoke test that the sim pipeline works end-to-end
sim-smoke:
    cd sims && python harness.py run --config configs/smoke.toml --duration 10

# Run an overnight batch (nightly tuning matrix)
sim-batch:
    cd sims && python harness.py batch --config configs/nightly.toml

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
    cd sims && ruff check .
    cd sims && mypy .

# Run all tests
test:
    cd host && cargo test
    cd sims && pytest

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
    cd sims && ruff format .
