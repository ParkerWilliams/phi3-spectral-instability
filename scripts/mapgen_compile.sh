#!/usr/bin/env bash
# Compile a procedurally generated level: gen_<seed>.map -> gen_<seed>.bsp (feature 004).
#
# LOCAL ONLY (the droplet has no engine and ericw-tools isn't vendored there; generation +
# static verification run on the droplet via `just mapgen-verify`).
#
# Needs prebuilt ericw-tools. Point at them with ERICW_BIN, else the vendored
# tools/ericw-tools/bin/. A LibreQuake texture .wad (LIBREQUAKE_WAD) is OPTIONAL — without
# it the map compiles fine but is untextured (grey).
#
#   # one-time vendor:  mkdir -p tools/ericw-tools/bin && cp <ericw>/bin/* tools/ericw-tools/bin/
#   scripts/mapgen_compile.sh <seed>
set -euo pipefail

SEED="${1:?usage: mapgen_compile.sh <seed>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${ERICW_BIN:-$ROOT/tools/ericw-tools/bin}"
MAPS_DIR="${MAPS_DIR:-quakec/maps}"          # where the engine loads +map gen_<seed>
WAD="${LIBREQUAKE_WAD:-}"                      # optional
MAP="$ROOT/gen_${SEED}.map"
BSP="$ROOT/gen_${SEED}.bsp"

for t in qbsp vis light; do
  [ -x "$BIN/$t" ] || { echo "ERROR: $BIN/$t missing. Vendor ericw-tools or set ERICW_BIN:"; \
    echo "  mkdir -p tools/ericw-tools/bin && cp <ericw>/bin/* tools/ericw-tools/bin/"; exit 1; }
done
export LD_LIBRARY_PATH="$BIN:${LD_LIBRARY_PATH:-}"   # ericw ships libtbb/libembree alongside

# 1) generate (deterministic; safe to re-run)
( cd "$ROOT/mapgen" && uv run python -m idledoom_mapgen.cli --seed "$SEED" --out "$MAP" )

# 2) compile (qbsp -> vis -> light)
WADARGS=()
if [ -n "$WAD" ] && [ -f "$WAD" ]; then
  WADARGS=(-wadpath "$(dirname "$WAD")")
else
  echo "NOTE: no LibreQuake wad (set LIBREQUAKE_WAD) -> the level will be untextured (grey, but playable)."
fi
"$BIN/qbsp" "${WADARGS[@]}" "$MAP"
if [ -f "$ROOT/gen_${SEED}.pts" ]; then
  echo "ERROR: LEAK in gen_${SEED} (qbsp produced a .pts) — should have been rejected upstream; file a bug."
  exit 2
fi
"$BIN/vis"   "$BSP"
"$BIN/light" "$BSP"

# 3) place where the engine/sim load it
mkdir -p "$ROOT/$MAPS_DIR"
mv -f "$BSP" "$ROOT/$MAPS_DIR/gen_${SEED}.bsp"
echo "Compiled -> $MAPS_DIR/gen_${SEED}.bsp   (play it: just watch gen_${SEED})"
