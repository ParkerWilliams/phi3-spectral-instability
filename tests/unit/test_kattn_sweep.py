"""Tests for ``phi3geom.scripts.kattn_sweep`` (T050)."""

from __future__ import annotations

import json
from pathlib import Path

from phi3geom.scripts.kattn_sweep import (
    DEFAULT_K_ATTN_VALUES,
    select_winner,
    write_sweep_report,
)


def test_default_k_attn_values() -> None:
    assert DEFAULT_K_ATTN_VALUES == (8, 16, 32)


def test_select_winner_by_median_gain() -> None:
    # k=16 has the highest median marginal gain
    per_k_results = {
        8:  {"B1": 0.01, "B2": 0.02, "B3": 0.01, "B4": 0.01, "B5": 0.00, "B6": -0.01},
        16: {"B1": 0.03, "B2": 0.04, "B3": 0.02, "B4": 0.03, "B5": 0.02, "B6": 0.01},
        32: {"B1": 0.02, "B2": 0.03, "B3": 0.01, "B4": 0.02, "B5": 0.01, "B6": 0.00},
    }
    assert select_winner(per_k_results) == 16


def test_select_winner_handles_none_entries() -> None:
    per_k_results = {
        8:  {"B1": 0.01, "B2": 0.02, "B3": None, "B4": None, "B5": None, "B6": None},
        16: {"B1": 0.05, "B2": 0.04, "B3": None, "B4": None, "B5": None, "B6": None},
        32: {"B1": 0.02, "B2": None, "B3": None, "B4": None, "B5": None, "B6": None},
    }
    # k=16 has highest median of available gains
    assert select_winner(per_k_results) == 16


def test_write_sweep_report_schema(tmp_path: Path) -> None:
    per_k_results = {
        8:  {"B1": 0.01, "B2": 0.02, "B3": 0.01, "B4": 0.01, "B5": 0.00, "B6": -0.01},
        16: {"B1": 0.03, "B2": 0.04, "B3": 0.02, "B4": 0.03, "B5": 0.02, "B6": 0.01},
        32: {"B1": 0.02, "B2": 0.03, "B3": 0.01, "B4": 0.02, "B5": 0.01, "B6": 0.00},
    }
    out = tmp_path / "k_attn_sweep.json"
    write_sweep_report(per_k_results=per_k_results, winner=16, out_path=out)
    payload = json.loads(out.read_text())
    assert payload["winner_k_attn"] == 16
    assert set(payload["median_marginal_gain_per_k"].keys()) == {"8", "16", "32"}
    assert set(payload["per_bin_marginal_gain"].keys()) == {"8", "16", "32"}
    for k_str in ("8", "16", "32"):
        assert set(payload["per_bin_marginal_gain"][k_str].keys()) == {
            "B1", "B2", "B3", "B4", "B5", "B6",
        }
