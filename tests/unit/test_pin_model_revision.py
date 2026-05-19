"""Tests for ``phi3geom.scripts.pin_model_revision``."""

from __future__ import annotations

from pathlib import Path

import pytest

from phi3geom.scripts.pin_model_revision import read_pin, write_pin


def test_write_then_read_round_trip(tmp_path: Path) -> None:
    pin_path = tmp_path / "pinned_revision.json"
    sha = "0123456789abcdef" * 2 + "01234567"  # 40 hex
    written = write_pin(sha, model_id="org/model", pin_path=pin_path)
    assert written == pin_path
    data = read_pin(pin_path)
    assert data["model_id"] == "org/model"
    assert data["model_revision_sha"] == sha
    assert "pinned_at_utc" in data


def test_existing_pin_refuses_without_force(tmp_path: Path) -> None:
    pin_path = tmp_path / "pinned_revision.json"
    sha_a = "a" * 40
    write_pin(sha_a, pin_path=pin_path)
    with pytest.raises(FileExistsError, match="--force-repin"):
        write_pin("b" * 40, pin_path=pin_path)


def test_force_repin_overwrites(tmp_path: Path) -> None:
    pin_path = tmp_path / "pinned_revision.json"
    write_pin("a" * 40, pin_path=pin_path)
    write_pin("b" * 40, pin_path=pin_path, force=True)
    data = read_pin(pin_path)
    assert data["model_revision_sha"] == "b" * 40


def test_pin_parent_directory_created(tmp_path: Path) -> None:
    pin_path = tmp_path / "nested" / "dir" / "pin.json"
    write_pin("c" * 40, pin_path=pin_path)
    assert pin_path.exists()
