"""Verify the local HuggingFace credentials before running any pipeline that
needs them. Called by ``check-hf-auth`` (declared in ``pyproject.toml``)
and by ``scripts/run_pilot.sh`` at startup.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Print authenticated user identity, or actionable failure message.

    Returns:
        Process exit code: 0 on success, 1 on missing/invalid token.
    """
    try:
        from huggingface_hub import whoami  # noqa: PLC0415  (lazy import)
    except ImportError:
        print(
            "[check-hf-auth] huggingface_hub not installed. "
            "Run: pip install -e '.[dev]'",
            file=sys.stderr,
        )
        return 1

    try:
        info = whoami()
    except Exception as exc:  # noqa: BLE001  (we want any auth failure)
        print(
            "[check-hf-auth] HuggingFace authentication failed:\n"
            f"  {type(exc).__name__}: {exc}\n\n"
            "To fix: run `huggingface-cli login` with a token that has read access to "
            "microsoft/Phi-3-mini-128k-instruct.",
            file=sys.stderr,
        )
        return 1

    name = info.get("name", "<unknown>") if isinstance(info, dict) else str(info)
    print(f"[check-hf-auth] Authenticated as: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
