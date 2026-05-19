"""SHA-derived deterministic seeds (Constitution Principle I).

Every random number in the study is keyed by a content-derived integer. The
derivation rule is fixed: take SHA1 of a namespaced prefix string + the
content key, then read the first 8 hex chars as an integer. This gives
seeds in ``[0, 2**32)`` that fit comfortably in numpy / sklearn / torch
random_state parameters.

The namespace prefixes are stable identifiers — changing them invalidates
prior results and is a breaking change requiring a constitution bump.
"""

from __future__ import annotations

import hashlib

_PREFIX_LEN = 8  # First 8 hex chars of the SHA1 digest → 32-bit seed


def _derive(prefix: str, key: str) -> int:
    """Return ``int(sha1(prefix + key).hexdigest()[:8], 16)``."""
    digest = hashlib.sha1(f"{prefix}{key}".encode("utf-8")).hexdigest()
    return int(digest[:_PREFIX_LEN], 16)


def seed_for_event(event_id: str) -> int:
    """Per-event seed: drives the event's dataset-generation randomness.

    Args:
        event_id: 64-hex SHA256 of the event's text content.

    Returns:
        Non-negative integer < 2**32, deterministic for ``event_id``.
    """
    return _derive("event:", event_id)


def seed_for_match(bin_id: str) -> int:
    """Per-bin CEM-matching seed: drives the within-cell subsampling."""
    return _derive("match:", bin_id)


def seed_for_split(version: str = "v1") -> int:
    """Train/held-out split seed. Defaults to the v1 study version."""
    return _derive("split:", version)


def seed_for_analysis(step_name: str) -> int:
    """Per-analysis-step seed (bootstrap CI, FPCA random init, etc.).

    Args:
        step_name: A stable identifier like ``"per_regime_composite:B3"`` or
            ``"functional_logistic:B2:avwo_grassmannian"``.
    """
    return _derive("analysis:", step_name)
