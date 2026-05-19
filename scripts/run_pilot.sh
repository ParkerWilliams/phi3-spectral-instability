#!/usr/bin/env bash
# Pilot driver: 600-event end-to-end pipeline (US1 MVP).
#
# Steps:
#   1. Verify HuggingFace credentials.
#   2. Pin the Phi-3-mini-128k-instruct revision SHA (if not already pinned).
#   3. Run the pilot Python entrypoint.
#
# Pass --with-ricci to enable US2's Forman-Ricci feature path.

set -euo pipefail

WITH_RICCI=""
for arg in "$@"; do
  case "$arg" in
    --with-ricci) WITH_RICCI="--with-ricci" ;;
    *) ;;
  esac
done

echo "[run-pilot] Step 1/3: HuggingFace auth check..."
check-hf-auth

echo "[run-pilot] Step 2/3: Pin model revision (idempotent)..."
if [ ! -f dataset/pinned_revision.json ]; then
  pin-model-revision
else
  echo "[run-pilot] Existing pin found at dataset/pinned_revision.json; skipping."
fi

echo "[run-pilot] Step 3/3: Run pilot (this is the long step; ~72 GPU-hours target)..."
run-pilot $WITH_RICCI
