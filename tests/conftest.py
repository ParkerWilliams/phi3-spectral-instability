"""Shared pytest fixtures across the test tree."""

from __future__ import annotations

import os
import random
from pathlib import Path

import pytest


@pytest.fixture
def seeded_rng() -> random.Random:
    """A deterministic stdlib random.Random instance for non-numpy tests."""
    return random.Random(0xC0DE_BEEF)


@pytest.fixture
def tmp_cache_root(tmp_path: Path) -> Path:
    """A per-test cache root under pytest's tmp_path."""
    root = tmp_path / "cache"
    root.mkdir()
    return root


@pytest.fixture
def repo_root() -> Path:
    """Repository root, derived from this conftest's location."""
    return Path(__file__).resolve().parent.parent


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-skip GPU-marked tests when no CUDA is available.

    Tests can opt-in to running anyway by setting ``PHI3_RUN_GPU_TESTS=1``.
    """
    if os.environ.get("PHI3_RUN_GPU_TESTS"):
        return
    skip_gpu = pytest.mark.skip(reason="GPU not available; set PHI3_RUN_GPU_TESTS=1 to override")
    for item in items:
        if "gpu" in item.keywords:
            item.add_marker(skip_gpu)
