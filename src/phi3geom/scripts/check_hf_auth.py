"""Verify the local HuggingFace credentials before running any pipeline that
needs them. Called by ``check-hf-auth`` (declared in ``pyproject.toml``)
and by ``scripts/run_pilot.sh`` at startup.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Print authenticated user identity, or actionable failure message.

    Returns:
        Process exit code: 0 on success OR no-token (public model, downloads
        still work but may be rate-limited); 1 only on a present-but-invalid
        token or a missing huggingface_hub install.
    """
    try:
        from huggingface_hub import get_token, whoami  # noqa: PLC0415 (lazy import)
    except ImportError:
        print(
            "[check-hf-auth] huggingface_hub not installed. "
            "Run: pip install -e '.[dev]'",
            file=sys.stderr,
        )
        return 1

    token = get_token()
    if not token:
        # microsoft/Phi-3-mini-128k-instruct is public — it downloads without
        # a token, just rate-limited. Warn but DO NOT block the pipeline.
        print(
            "[check-hf-auth] No HF token found. microsoft/Phi-3-mini-128k-instruct "
            "is public, so it will still download — but possibly rate-limited.\n"
            "For faster/unthrottled downloads, run `huggingface-cli login` or set "
            "HF_TOKEN before the run.",
            file=sys.stderr,
        )
        return 0

    # A token IS present — verify it's valid (a broken token is a real error).
    try:
        info = whoami(token=token)
    except Exception as exc:  # noqa: BLE001  (we want any auth failure)
        print(
            "[check-hf-auth] An HF token is set but authentication failed:\n"
            f"  {type(exc).__name__}: {exc}\n\n"
            "The token may be expired or invalid. Re-run `huggingface-cli login`.",
            file=sys.stderr,
        )
        return 1

    name = info.get("name", "<unknown>") if isinstance(info, dict) else str(info)
    print(f"[check-hf-auth] Authenticated as: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
