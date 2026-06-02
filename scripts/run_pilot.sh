#!/usr/bin/env bash
# Pilot driver: ~600-event end-to-end pipeline.
#
# All extra args pass through to `run-pilot` (pilot_main). See:
#   python -m phi3geom.scripts.pilot_main --help
#
# Common usage:
#   bash scripts/run_pilot.sh                                            # default pilot
#   bash scripts/run_pilot.sh --with-ricci                               # US2 Ricci path
#   bash scripts/run_pilot.sh --experiment-branch experiment/foo         # resilient mode

set -euo pipefail

echo "[run-pilot] Step 1/3: HuggingFace auth check..."
check-hf-auth

echo "[run-pilot] Step 2/3: Pin model revision (idempotent)..."
if [ ! -f dataset/pinned_revision.json ]; then
  pin-model-revision
else
  echo "[run-pilot] Existing pin found at dataset/pinned_revision.json; skipping."
fi

echo "[run-pilot] Step 3/3: Run pilot (long step; ~72 GPU-hours budget)..."
run-pilot "$@"
