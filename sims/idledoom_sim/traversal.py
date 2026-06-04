"""Pluggable traversal-coverage metrics over the periodic ``nav`` sample stream.

Design (feature: nav-competence metric). The QuakeC side emits a cheap, *stable*
``nav`` event every ~2s carrying the agent's position + cumulative counters
(``t, x, y, waypoints, distance``). EVERY traversal metric is then computed here
in Python from that stream — so we can add, swap, and compare metrics WITHOUT
rebuilding QuakeC (the slow-to-iterate layer barely changes). ``aggregate()``
folds the whole registry into ``stats.traversal`` in parallel; switching which one
is authoritative for a comparison is just picking the dotted key, e.g.
``compare --metric stats.traversal.visited_cells`` — no rebuild, no re-run.

Why a registry rather than one metric: nav competence is expected to be revisited
often (start cheap/coarse, improve over the project). Adding a metric = write one
``f(list[NavSample]) -> float`` and register it in ``TRAVERSAL_METRICS``; it then
appears in every summary and is immediately selectable in ``compare``.

Note on saturation (why these shapes): on a small map within the time limit the
agent fully explores at *any* competence, so end-of-run coverage saturates and
can't distinguish skill. The rate-style metrics (``*_at_15s``) capture how *fast*
it explores — which discriminates even when both runs finish fully explored.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .telemetry import ParsedEvent

CELL_SIZE = 256.0  # world units per grid cell for visited_cells
RATE_CHECKPOINT_SEC = 15.0  # "early" sim-time for rate (exploration-speed) metrics


@dataclass(frozen=True)
class NavSample:
    """One periodic nav sample: agent position + cumulative counters at time ``t``."""

    t: float
    x: float
    y: float
    waypoints: int
    distance: float
    boredom: float = 0.0  # agent restlessness at this sample (rises while wandering)


def _num(value: Any) -> float:
    return float(value) if value is not None else 0.0


def nav_samples(events: Iterable[ParsedEvent]) -> list[NavSample]:
    """Extract the ordered ``nav`` samples from an event stream."""
    out: list[NavSample] = []
    for ev in events:
        if ev.type != "nav":
            continue
        d = ev.data
        out.append(
            NavSample(
                t=_num(ev.t),
                x=_num(d.get("x")),
                y=_num(d.get("y")),
                waypoints=int(_num(d.get("waypoints"))),
                distance=_num(d.get("distance")),
                boredom=_num(d.get("boredom")),
            )
        )
    return out


# --- metric implementations: each is a pure function of the sample list --------


def extent_area(s: list[NavSample]) -> float:
    """Bounding-box area of all sampled positions (how far the agent ranges)."""
    if not s:
        return 0.0
    xs = [p.x for p in s]
    ys = [p.y for p in s]
    return round((max(xs) - min(xs)) * (max(ys) - min(ys)), 2)


def visited_cells(s: list[NavSample]) -> float:
    """Distinct ``CELL_SIZE`` grid cells the samples fall in (coarse true coverage)."""
    return float(len({(int(p.x // CELL_SIZE), int(p.y // CELL_SIZE)) for p in s}))


def _value_at(s: list[NavSample], t_max: float, attr: str) -> float:
    """Value of ``attr`` at the latest sample with ``t <= t_max`` (0 if none yet)."""
    val = 0.0
    for p in s:
        if p.t <= t_max:
            val = float(getattr(p, attr))
    return val


def waypoints_at_15s(s: list[NavSample]) -> float:
    """Exploration speed: distinct waypoints reached by the early checkpoint."""
    return _value_at(s, RATE_CHECKPOINT_SEC, "waypoints")


def distance_at_15s(s: list[NavSample]) -> float:
    """Exploration speed: ground covered by the early checkpoint."""
    return _value_at(s, RATE_CHECKPOINT_SEC, "distance")


def final_waypoints(s: list[NavSample]) -> float:
    """Total distinct waypoints reached by the last sample (end-of-run reach)."""
    return float(s[-1].waypoints) if s else 0.0


def peak_boredom(s: list[NavSample]) -> float:
    """Highest boredom reached — how restless the agent got before finding combat.
    Lower = it sought/found fights sooner (the boredom mechanic working)."""
    return max((p.boredom for p in s), default=0.0)


# Registry — add a metric by writing a function above and listing it here.
TRAVERSAL_METRICS: dict[str, Callable[[list[NavSample]], float]] = {
    "extent_area": extent_area,
    "visited_cells": visited_cells,
    "waypoints_at_15s": waypoints_at_15s,
    "distance_at_15s": distance_at_15s,
    "final_waypoints": final_waypoints,
    "peak_boredom": peak_boredom,
}


def compute_traversal(events: Iterable[ParsedEvent]) -> dict[str, float]:
    """Compute every registered traversal metric from a stream's nav samples.

    Returns ``{}`` when the stream carries no ``nav`` samples (e.g. a pre-nav-event
    run) so the absence reads as "unmeasured" rather than misleading zeros — and
    ``compare`` (which skips missing values) ignores those runs.
    """
    samples = nav_samples(events)
    if not samples:
        return {}
    return {name: fn(samples) for name, fn in TRAVERSAL_METRICS.items()}
