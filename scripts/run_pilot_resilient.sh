#!/usr/bin/env bash
# Resilient pilot wrapper: PAT auth-verify -> git identity -> pilot w/ checkpoints.
#
# Required env:
#   GITHUB_TOKEN     fine-grained GitHub PAT with `contents: read+write` on this repo.
# Required args (at least):
#   --experiment-branch <name>
# Optional pass-through args: any pilot_main flag.
#
# Example (paste on a fresh pod):
#   export GITHUB_TOKEN=ghp_...
#   bash scripts/run_pilot_resilient.sh \
#       --experiment-branch experiment/pilot/$(date -u +%Y-%m-%d)
#
# If the pod dies, spin up a new one and run the SAME command — restore-from-branch
# pulls the prior cache off the experiment branch and resume-from-cache skips the
# events that are already done.

set -euo pipefail

# --- 0. Auto-source the project venv if not already active ---
# Without this, a nohup'd subprocess can fail to find the entry-point scripts
# (check-hf-auth, pin-model-revision, run-pilot) even when the parent shell
# had the venv activated, because PATH propagation through nohup + bash
# subprocess chains can be flaky depending on environment.
if [ -z "${VIRTUAL_ENV:-}" ]; then
  _RPR_HERE="$(cd "$(dirname "$0")/.." && pwd)"
  if [ -f "$_RPR_HERE/.venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$_RPR_HERE/.venv/bin/activate"
    echo "[resilient] sourced venv at $_RPR_HERE/.venv"
  fi
fi

# --- 1. Required env ---
if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "[resilient] ERROR: GITHUB_TOKEN env var not set." >&2
  echo "  Export a fine-grained GitHub PAT (contents: read+write) before running:" >&2
  echo "    export GITHUB_TOKEN=ghp_..." >&2
  exit 1
fi

# --- 2. Required arg ---
if ! printf '%s\n' "$@" | grep -q -- '--experiment-branch'; then
  echo "[resilient] ERROR: --experiment-branch <name> is required for resilient mode." >&2
  echo "  Without it, use scripts/run_pilot.sh (no checkpoint, no resume)." >&2
  echo "  Example:" >&2
  echo "    bash scripts/run_pilot_resilient.sh --experiment-branch experiment/pilot/$(date -u +%Y-%m-%d)" >&2
  exit 1
fi

# --- 3. origin must be HTTPS (PAT auth doesn't work over SSH URLs) ---
REMOTE_URL=$(git remote get-url origin)
case "$REMOTE_URL" in
  https://*) ;;
  *)
    echo "[resilient] ERROR: origin URL must be HTTPS for PAT auth. Got: $REMOTE_URL" >&2
    echo "  Fix: git remote set-url origin https://github.com/<owner>/<repo>.git" >&2
    exit 1
    ;;
esac

# --- 4. Verify the PAT works against this remote (seconds, not minutes) ---
AUTHED_URL=$(printf '%s' "$REMOTE_URL" \
    | sed "s|https://|https://x-access-token:${GITHUB_TOKEN}@|")
echo "[resilient] Verifying GitHub PAT against $REMOTE_URL ..."
if ! git ls-remote --heads "$AUTHED_URL" >/dev/null 2>&1; then
  echo "[resilient] ERROR: ls-remote with the provided PAT failed." >&2
  echo "  Check the token has 'contents: read+write' scope on this repo." >&2
  exit 1
fi
echo "[resilient] Auth OK."

# --- 5. Local git identity (fresh pods often have neither) ---
git config user.email >/dev/null 2>&1 || git config user.email "pilot@runpod.local"
git config user.name  >/dev/null 2>&1 || git config user.name  "Pilot Runner"

# --- 5b. HF_HUB_ENABLE_HF_TRANSFER fallback ---
# RunPod's PyTorch template sets HF_HUB_ENABLE_HF_TRANSFER=1; if the
# `hf_transfer` package isn't installed (older pods predating its addition to
# deps), HF downloads fail loudly. Silently unset rather than fail.
if [ -n "${HF_HUB_ENABLE_HF_TRANSFER:-}" ]; then
  if ! python -c "import hf_transfer" >/dev/null 2>&1; then
    echo "[resilient] HF_HUB_ENABLE_HF_TRANSFER=1 set but hf_transfer not installed; unsetting."
    unset HF_HUB_ENABLE_HF_TRANSFER
  fi
fi

# --- 6. Hand off. pilot_main does restore + periodic + final checkpoint. ---
exec bash scripts/run_pilot.sh "$@"
