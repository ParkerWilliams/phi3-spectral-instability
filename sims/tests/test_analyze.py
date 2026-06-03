"""Run-comparison helpers for SC-003/SC-004: average a metric across run
summaries and compare groups (e.g. low vs high bot_map_awareness / bot_accuracy)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import harness
from idledoom_sim.analyze import compare_groups, get_metric, group_by, mean_metric


def _summary(awareness: float, coverage: float, accuracy: float) -> dict[str, Any]:
    return {
        "bot_config": {"bot_map_awareness": awareness, "bot_accuracy": accuracy},
        "stats": {"map_coverage": coverage, "accuracy": accuracy, "reached_exit": False},
    }


def test_get_metric_dotted_path() -> None:
    s = _summary(0.3, 0.5, 0.7)
    assert get_metric(s, "stats.map_coverage") == 0.5
    assert get_metric(s, "bot_config.bot_map_awareness") == 0.3
    assert get_metric(s, "stats.missing") is None
    assert get_metric(s, "stats.reached_exit") is None  # bool excluded from metrics


def test_mean_metric_ignores_missing() -> None:
    rows: list[dict[str, Any]] = [
        _summary(0.1, 0.2, 0.5),
        _summary(0.1, 0.4, 0.5),
        {"stats": {}},
    ]
    assert round(mean_metric(rows, "stats.map_coverage"), 4) == 0.3  # (0.2+0.4)/2
    assert mean_metric([], "stats.map_coverage") == 0.0


def test_group_by_config_key() -> None:
    rows = [_summary(0.1, 0.2, 0.5), _summary(0.9, 0.8, 0.5), _summary(0.1, 0.3, 0.5)]
    groups = group_by(rows, "bot_config.bot_map_awareness")
    assert sorted(groups) == [0.1, 0.9]
    assert len(groups[0.1]) == 2


def test_compare_groups_reports_improvement() -> None:
    low = [_summary(0.1, 0.2, 0.5), _summary(0.1, 0.3, 0.5)]   # mean coverage 0.25
    high = [_summary(0.9, 0.7, 0.5), _summary(0.9, 0.9, 0.5)]  # mean coverage 0.80
    r = compare_groups(low, high, "stats.map_coverage")
    assert round(r["low_mean"], 4) == 0.25
    assert round(r["high_mean"], 4) == 0.8
    assert round(r["delta"], 4) == 0.55
    assert r["improved"] is True


def test_compare_groups_no_improvement() -> None:
    low = [_summary(0.1, 0.6, 0.5)]
    high = [_summary(0.9, 0.4, 0.5)]
    assert compare_groups(low, high, "stats.map_coverage")["improved"] is False


def test_compare_subcommand_groups_and_averages(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for i, (aw, cov) in enumerate([(0.1, 0.2), (0.9, 0.8)]):
        (tmp_path / f"r{i}.summary.json").write_text(json.dumps(_summary(aw, cov, 0.5)))
    paths = [str(p) for p in sorted(tmp_path.glob("*.summary.json"))]
    rc = harness.main(
        ["compare", "--metric", "stats.map_coverage",
         "--by", "bot_config.bot_map_awareness", *paths]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "mean=0.2000" in out  # the 0.1-awareness run
    assert "mean=0.8000" in out  # the 0.9-awareness run
