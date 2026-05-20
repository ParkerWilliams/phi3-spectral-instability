#!/usr/bin/env bash
# SC-005 cross-machine reproducibility check.
#
# Run this on a SECOND machine after a full-study completes on the first.
# Targets ≥99% event_id agreement under the same code commit SHA + manifest.

set -euo pipefail

regenerate-dataset "$@"
