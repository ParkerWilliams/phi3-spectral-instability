"""Pin the HuggingFace revision SHA for ``microsoft/Phi-3-mini-128k-instruct``.

Writes ``dataset/pinned_revision.json`` with the model's current main-branch
commit SHA. The dataset-generation step reads this file to populate
``manifest_header.json``'s ``model_revision_sha`` field.

Once a pin exists, this script refuses to overwrite without ``--force-repin``
(which is destructive: it invalidates any manifest that consumed the prior
pin). Per Constitution Principle I, every reported result is reproducible
back to the specific revision SHA recorded here.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_MODEL_ID = "microsoft/Phi-3-mini-128k-instruct"
DEFAULT_PIN_PATH = Path("dataset/pinned_revision.json")


def _now_iso() -> str:
    return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_revision_sha(model_id: str = DEFAULT_MODEL_ID) -> str:
    """Return the current main-branch commit SHA of ``model_id`` on HuggingFace.

    Args:
        model_id: HuggingFace repo id (e.g., ``"microsoft/Phi-3-mini-128k-instruct"``).

    Returns:
        40-hex commit SHA.

    Raises:
        RuntimeError: If HuggingFace API call fails.
    """
    try:
        from huggingface_hub import HfApi  # noqa: PLC0415 (lazy import)
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub is required to fetch the revision SHA. "
            "Install with: pip install -e '.[dev]'"
        ) from exc

    api = HfApi()
    try:
        info = api.model_info(model_id)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Failed to query HuggingFace for {model_id}: {type(exc).__name__}: {exc}"
        ) from exc

    sha = getattr(info, "sha", None)
    if not sha or not isinstance(sha, str) or len(sha) != 40:
        raise RuntimeError(
            f"HuggingFace returned an unexpected SHA for {model_id}: {sha!r}"
        )
    return sha


def write_pin(
    sha: str,
    *,
    model_id: str = DEFAULT_MODEL_ID,
    pin_path: Path = DEFAULT_PIN_PATH,
    force: bool = False,
) -> Path:
    """Write the pin to ``pin_path``.

    Args:
        sha: 40-hex SHA from ``fetch_revision_sha``.
        model_id: Repo id, recorded alongside the SHA.
        pin_path: Output file path.
        force: If True, overwrite an existing pin. Default False.

    Returns:
        ``pin_path``.

    Raises:
        FileExistsError: If a pin already exists and ``force`` is False.
    """
    if pin_path.exists() and not force:
        raise FileExistsError(
            f"Pin already exists at {pin_path}. Use --force-repin to overwrite "
            "(this invalidates any manifest that consumed the prior pin)."
        )
    pin_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "model_id": model_id,
        "model_revision_sha": sha,
        "pinned_at_utc": _now_iso(),
    }
    pin_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return pin_path


def read_pin(pin_path: Path = DEFAULT_PIN_PATH) -> dict[str, str]:
    """Read a pin file. Returns the dict with model_id, model_revision_sha,
    pinned_at_utc.
    """
    return json.loads(pin_path.read_text())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--pin-path", type=Path, default=DEFAULT_PIN_PATH)
    parser.add_argument(
        "--force-repin",
        action="store_true",
        help="Overwrite an existing pin (DESTRUCTIVE; invalidates prior manifests).",
    )
    args = parser.parse_args(argv)

    try:
        sha = fetch_revision_sha(args.model_id)
    except RuntimeError as exc:
        print(f"[pin-model-revision] ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        path = write_pin(sha, model_id=args.model_id, pin_path=args.pin_path, force=args.force_repin)
    except FileExistsError as exc:
        print(f"[pin-model-revision] ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"[pin-model-revision] Pinned {args.model_id} → {sha}")
    print(f"[pin-model-revision] Written to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
