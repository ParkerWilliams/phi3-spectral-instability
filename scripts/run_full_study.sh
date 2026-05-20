#!/usr/bin/env bash
# Full-study driver: 4800-event collection + per-regime composite (US3).
#
# Prerequisites:
#   - Pilot (US1 + US2) complete and validated against SC-004.
#   - k_attn sweep report at reports/pilot/k_attn_sweep.json.
#   - dataset/pinned_revision.json present.

set -euo pipefail

echo "[run-full-study] Step 1/3: HF auth check..."
check-hf-auth

echo "[run-full-study] Step 2/3: Verify k_attn sweep report exists..."
if [ ! -f reports/pilot/k_attn_sweep.json ]; then
  echo "[run-full-study] ERROR: reports/pilot/k_attn_sweep.json not found. Run kattn_sweep first." >&2
  exit 1
fi

echo "[run-full-study] Step 3/3: Run full-study (~120 GPU-hours target)..."
run-full-study "$@"
