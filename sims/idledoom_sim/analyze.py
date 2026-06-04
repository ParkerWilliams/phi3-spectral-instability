"""Compare metrics across run summaries.

SC-003 (nav competence → coverage) and SC-004 (accuracy → accuracy) both reduce
to: average a numeric metric across "low" vs "high" run groups and check it
improved. These helpers make that robust + testable instead of ad-hoc grep/jq.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

Summary = dict[str, Any]


def load_summaries(paths: list[Path]) -> list[Summary]:
    """Load summary JSON files (e.g. ``results/*/*.summary.json``)."""
    out: list[Summary] = []
    for p in paths:
        data: Summary = json.loads(p.read_text())
        out.append(data)
    return out


def get_metric(summary: Summary, dotted: str) -> float | None:
    """Read a numeric value at a dotted path (e.g. ``stats.map_coverage``).

    Returns ``None`` if the path is missing or the value is non-numeric. Booleans
    are excluded (they aren't meaningful to average).
    """
    cur: Any = summary
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    if isinstance(cur, bool) or not isinstance(cur, (int, float)):
        return None
    return float(cur)


def mean_metric(summaries: list[Summary], dotted: str) -> float:
    """Mean of a metric across summaries; missing values are ignored; 0.0 if none."""
    vals = [v for v in (get_metric(s, dotted) for s in summaries) if v is not None]
    return sum(vals) / len(vals) if vals else 0.0


def group_by(summaries: list[Summary], dotted: str) -> dict[Any, list[Summary]]:
    """Group summaries by the value at ``dotted`` (e.g. a ``bot_config`` setting)."""
    groups: dict[Any, list[Summary]] = {}
    for s in summaries:
        groups.setdefault(get_metric(s, dotted), []).append(s)
    return groups


def compare_groups(
    low: list[Summary], high: list[Summary], metric: str
) -> dict[str, Any]:
    """Compare a metric's mean between two groups (e.g. low vs high setting).

    Returns ``{low_mean, high_mean, delta, improved}`` where ``improved`` is True
    iff the high group's mean strictly exceeds the low group's.
    """
    low_mean = mean_metric(low, metric)
    high_mean = mean_metric(high, metric)
    return {
        "low_mean": low_mean,
        "high_mean": high_mean,
        "delta": high_mean - low_mean,
        "improved": high_mean > low_mean,
    }
