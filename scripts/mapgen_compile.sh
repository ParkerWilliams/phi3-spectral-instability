#!/usr/bin/env bash
# Compile a procedurally generated level: gen_<seed>.map -> gen_<seed>.bsp (feature 004).
#
# LOCAL ONLY. Needs the vendored prebuilt ericw-tools (tools/ericw-tools/bin/) and a
# LibreQuake texture .wad. The droplet cannot run this (no engine, ericw-tools not vendored
# there); generation + static verification run on the droplet via `just mapgen-verify`.
#
# Usage: scripts/mapgen_compile.sh <seed> [out_map_dir]
set -euo pipefail

SEED="${1:?usage: mapgen_compile.sh <seed> [out_map_dir]}"
MAPS_DIR="${2:-quakec/maps}"          # where the engine/sim looks for +map gen_<seed>
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/tools/ericw-tools/bin"
WAD="${LIBREQUAKE_WAD:-$ROOT/assets/wads/librequake.wad}"   # override via env if needed
MAP="gen_${SEED}.map"
BSP="gen_${SEED}.bsp"

for t in qbsp vis light; do
  [ -x "$TOOLS/$t" ] || { echo "ERROR: missing $TOOLS/$t — vendor prebuilt ericw-tools (see tools/ericw-tools/README.md)"; exit 1; }
done
[ -f "$WAD" ] || { echo "ERROR: LibreQuake wad not found at $WAD (set LIBREQUAKE_WAD)"; exit 1; }

# 1) generate (re-generates deterministically; safe to re-run)
( cd "$ROOT/mapgen" && uv run python -m idledoom_mapgen.cli --seed "$SEED" --out "$ROOT/$MAP" )

# 2) compile
"$TOOLS/qbsp" -wadpath "$(dirname "$WAD")" "$ROOT/$MAP"
# qbsp writes a .pts on a leak -> hard failure
if [ -f "$ROOT/gen_${SEED}.pts" ]; then
  echo "ERROR: LEAK in gen_${SEED} (qbsp produced a .pts). The seed should have been rejected upstream — file a bug."
  exit 2
fi
"$TOOLS/vis"   "$ROOT/$BSP"
"$TOOLS/light" "$ROOT/$BSP"

# 3) place where the engine/sim load it
mkdir -p "$ROOT/$MAPS_DIR"
mv -f "$ROOT/$BSP" "$ROOT/$MAPS_DIR/$BSP"
echo "Compiled -> $MAPS_DIR/$BSP   (play it: just watch gen_${SEED})"
