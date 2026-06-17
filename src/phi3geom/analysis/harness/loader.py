"""Frozen-cache loader (SP-0 harness interface, T044).

The read-only view SP-1/SP-2 consume: per event, the labeled target plus a
pluggable arbitrary-width feature assembler over the stored bundle arrays — no
hard-coded feature count, no GPU, no model reload (contracts/harness-interface.md).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np


@dataclass
class HarnessDataset:
    """Read-only projection over CaptureBundles under one ``capture_version``."""

    event_dirs: list[Path]
    capture_version: str

    def __len__(self) -> int:
        return len(self.event_dirs)

    def _meta(self, d: Path) -> dict:
        return json.loads((d / "meta.json").read_bytes())

    def _label(self, d: Path) -> dict:
        return json.loads((d / "label.json").read_bytes())

    @property
    def corpus_ids(self) -> np.ndarray:
        return np.array([self._meta(d)["corpus_id"] for d in self.event_dirs])

    @property
    def model_ids(self) -> np.ndarray:
        return np.array([self._meta(d)["model_id"] for d in self.event_dirs])

    @property
    def targets(self) -> np.ndarray:
        """Headline binary target: ``is_hallucination`` (0/1)."""
        return np.array(
            [int(self._label(d)["is_hallucination"]) for d in self.event_dirs], dtype=int
        )

    @property
    def class_4way(self) -> list[str]:
        return [self._label(d)["class_4way"] for d in self.event_dirs]

    def bundle(self, d: Path) -> dict[str, np.ndarray]:
        """Load the event's stored arrays as ``{array_name: ndarray}``."""
        return {f.stem: np.load(f, allow_pickle=False) for f in sorted(d.glob("*.npy"))}

    def assemble(self, fn: Callable[[dict[str, np.ndarray]], object]) -> np.ndarray:
        """Apply a pluggable feature assembler to every event → ``(N, d)`` matrix.

        ``fn`` receives the per-event ``{array_name: ndarray}`` bundle and returns
        a feature vector (or scalar) of arbitrary, consistent width.
        """
        rows = [
            np.asarray(fn(self.bundle(d)), dtype=np.float64).ravel()
            for d in self.event_dirs
        ]
        return np.vstack(rows) if rows else np.empty((0, 0))


def load(
    cache_root: str | Path,
    capture_version: str,
    *,
    models: list[str] | None = None,
    corpora: list[str] | None = None,
) -> HarnessDataset:
    """Build a ``HarnessDataset`` over the frozen cache, optionally filtered.

    An event dir qualifies iff it has both ``meta.json`` and ``label.json``.
    Filtering is by the ``model_id``/``corpus_id`` recorded in ``meta.json`` (not
    by path, so org-slashed model ids round-trip correctly).
    """
    base = Path(cache_root) / capture_version
    dirs: list[Path] = []
    if base.exists():
        for meta_path in base.rglob("meta.json"):
            d = meta_path.parent
            if not (d / "label.json").exists():
                continue
            meta = json.loads(meta_path.read_bytes())
            if models is not None and meta.get("model_id") not in models:
                continue
            if corpora is not None and meta.get("corpus_id") not in corpora:
                continue
            dirs.append(d)
    dirs.sort()
    return HarnessDataset(event_dirs=dirs, capture_version=capture_version)
