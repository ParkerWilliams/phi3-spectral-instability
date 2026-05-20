#!/usr/bin/env bash
# Replicate cache/ and dataset/ to the S3 hot tier (FR-013 storage contract).
#
# Idempotent: rsync skips unchanged files. Logs to reports/full/replication.log.
#
# Required environment:
#   PHI3_S3_HOT_TIER  — destination bucket URI (e.g., s3://my-bucket/phi3geom/)
#   AWS credentials   — configured via ~/.aws/ or environment.

set -euo pipefail

if [ -z "${PHI3_S3_HOT_TIER:-}" ]; then
  echo "[replicate-s3] ERROR: PHI3_S3_HOT_TIER not set." >&2
  exit 1
fi

mkdir -p reports/full
LOG="reports/full/replication.log"

ts() { date -u +'%Y-%m-%dT%H:%M:%SZ'; }

{
  echo "[$(ts)] === Replication start to $PHI3_S3_HOT_TIER ==="

  echo "[$(ts)] Syncing dataset/ ..."
  aws s3 sync dataset/ "${PHI3_S3_HOT_TIER}dataset/" --exclude "*.tmp"

  echo "[$(ts)] Syncing cache/ ..."
  aws s3 sync cache/ "${PHI3_S3_HOT_TIER}cache/" --exclude "*.tmp"

  echo "[$(ts)] Syncing reports/ ..."
  aws s3 sync reports/ "${PHI3_S3_HOT_TIER}reports/" --exclude "*.tmp"

  echo "[$(ts)] === Replication complete ==="
} | tee -a "$LOG"
