#!/usr/bin/env bash
# Setup script for a fresh DigitalOcean L40S (or similar) GPU droplet.
#
# Run with (one paste):
#   curl -fsSL https://raw.githubusercontent.com/ParkerWilliams/phi3-spectral-instability/main/scripts/setup_do_droplet.sh -o /tmp/setup.sh && source /tmp/setup.sh
#
# What it does (inside a subshell so set -e doesn't pollute your shell):
#   1. nvidia-smi sanity check
#   2. clone the repo if missing, switch to main
#   3. apt install python3.11-venv (DO Ubuntu ships 3.8 default; we need 3.11+)
#   4. create venv with python3.11 explicitly
#   5. pip install -e ".[dev]" (pulls CUDA torch from PyPI)
#   6. pre-download Phi-3-mini-128k-instruct
#   7. run CPU test suite
#   8. run GPU integration test
#
# After the subshell finishes successfully, the venv is sourced in YOUR shell
# and you're cd'd into the repo, ready to set GITHUB_TOKEN and launch.

(
  set -euo pipefail

  echo "===================================================================="
  echo "=== 1. GPU sanity check"
  echo "===================================================================="
  nvidia-smi | head -3

  echo
  echo "===================================================================="
  echo "=== 2. Repo (clone if missing, switch to main, pull latest)"
  echo "===================================================================="
  cd ~
  [ -d phi3-spectral-instability ] \
    || git clone https://github.com/ParkerWilliams/phi3-spectral-instability.git
  cd phi3-spectral-instability
  git checkout main
  git pull

  echo
  echo "===================================================================="
  echo "=== 3. python3.11-venv (DO Ubuntu ships 3.8 default but 3.11 binary"
  echo "===    is there; we just need the venv tooling for it)"
  echo "===================================================================="
  apt-get update -qq
  apt-get install -y python3.11-venv python3.11-dev

  echo
  echo "===================================================================="
  echo "=== 4. Fresh venv (explicit python3.11; NOT 'python3 -m venv')"
  echo "===================================================================="
  rm -rf .venv
  python3.11 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --quiet --upgrade pip

  echo
  echo "===================================================================="
  echo "=== 5. pip install -e '.[dev]' (~5-10 min; pulls CUDA torch)"
  echo "===================================================================="
  pip install -e ".[dev]"

  echo
  echo "===================================================================="
  echo "=== 6. Pre-download Phi-3-mini-128k-instruct (~7.6 GB)"
  echo "===================================================================="
  huggingface-cli download microsoft/Phi-3-mini-128k-instruct

  echo
  echo "===================================================================="
  echo "=== 7. CPU test suite (expect 288 passed, ~1 min)"
  echo "===================================================================="
  python -m pytest tests/unit tests/contract -q

  echo
  echo "===================================================================="
  echo "=== 8. GPU integration test (expect 2 passed, ~25 min)"
  echo "===================================================================="
  PHI3_RUN_GPU_TESTS=1 python -m pytest tests/integration/test_pilot_pipeline.py -s
)

# After the subshell — these affect the user's shell since we're sourced.
cd ~/phi3-spectral-instability
# shellcheck disable=SC1091
source .venv/bin/activate

echo
echo "===================================================================="
echo "=== SETUP COMPLETE"
echo "===================================================================="
echo "  venv:    $VIRTUAL_ENV"
echo "  cwd:     $(pwd)"
echo "  branch:  $(git branch --show-current)"
echo
echo "Next: export your GITHUB_TOKEN, then launch the pilot."
echo "(Paste your launch block.)"
