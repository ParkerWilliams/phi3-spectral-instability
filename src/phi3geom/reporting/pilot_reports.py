"""Pilot report writers (FR-014, T045).

Produces four artifact files under ``reports/pilot/``:

- ``per_bin_auroc.json`` — per-bin AUROC + 95% CI from the spectral-only
  composite logistic (US1 baseline).
- ``cem_yield.json`` — per-bin CEM match yield + compromised-bin flag
  (FR-015).
- ``runtime.json`` — end-to-end wall time + estimated GPU-hours.
- ``handcheck_sample.jsonl`` — 50 random matched events with full text +
  model output for SC-007 human verification.
"""

from __future__ import annotations

import dataclasses
import json
import random
from pathlib import Path

from phi3geom.analysis.types import PerRegimeCompositeFit
from phi3geom.dataset.types import BinId, CEMStratum, DocQAEvent

REPORTS_PILOT_DIR = Path("reports/pilot")


def write_per_bin_auroc(
    fits: dict[BinId, PerRegimeCompositeFit],
    *,
    out_dir: Path = REPORTS_PILOT_DIR,
) -> Path:
    """Write ``per_bin_auroc.json``.

    Schema: ``{bin_id: {auroc, auroc_ci_lower, auroc_ci_upper,
    n_events_train, n_events_held_out}}``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, dict[str, float]] = {}
    for bin_id, fit in fits.items():
        payload[bin_id] = {
            "auroc": fit.auroc,
            "auroc_ci_lower": fit.auroc_ci_lower,
            "auroc_ci_upper": fit.auroc_ci_upper,
            "n_events_train": fit.n_events_train,
            "n_events_held_out": fit.n_events_held_out,
        }
    path = out_dir / "per_bin_auroc.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return path


def write_cem_yield(
    strata_by_bin: dict[BinId, list[CEMStratum]],
    *,
    out_dir: Path = REPORTS_PILOT_DIR,
) -> Path:
    """Write ``cem_yield.json`` (FR-015).

    Schema: ``{bin_id: {n_strata, n_strata_with_matches, total_fail_pool,
    total_ctrl_pool, total_matched_pairs, yield_pct, is_compromised}}``.

    ``is_compromised`` is True when ``yield_pct < 50%``; the writeup should
    escalate-to-3x and re-check, per the matching-with-escalation logic
    that lives in US3 (T057).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, dict[str, object]] = {}
    for bin_id, strata in strata_by_bin.items():
        n_strata = len(strata)
        n_with = sum(1 for s in strata if s.n_matched_pairs > 0)
        n_fail = sum(s.n_fail_pool for s in strata)
        n_ctrl = sum(s.n_ctrl_pool for s in strata)
        n_matched = sum(s.n_matched_pairs for s in strata)
        max_possible = min(n_fail, n_ctrl)
        yield_pct = (
            100.0 * n_matched / max_possible if max_possible > 0 else 0.0
        )
        payload[bin_id] = {
            "n_strata": n_strata,
            "n_strata_with_matches": n_with,
            "total_fail_pool": n_fail,
            "total_ctrl_pool": n_ctrl,
            "total_matched_pairs": n_matched,
            "yield_pct": yield_pct,
            "is_compromised": yield_pct < 50.0,
        }
    path = out_dir / "cem_yield.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return path


def write_runtime(
    *,
    wall_time_sec: float,
    gpu_hours_estimate: float,
    n_events: int,
    out_dir: Path = REPORTS_PILOT_DIR,
) -> Path:
    """Write ``runtime.json``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "wall_time_sec": wall_time_sec,
        "wall_time_hours": wall_time_sec / 3600.0,
        "gpu_hours_estimate": gpu_hours_estimate,
        "n_events": n_events,
        "seconds_per_event": wall_time_sec / max(n_events, 1),
    }
    path = out_dir / "runtime.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return path


def write_handcheck_sample(
    matched_events: list[DocQAEvent],
    *,
    sample_size: int = 50,
    random_seed: int = 0xC0DE,
    out_dir: Path = REPORTS_PILOT_DIR,
) -> Path:
    """Write ``handcheck_sample.jsonl`` — 50 random matched events for
    SC-007 manual verification. Each line carries the full text + the
    automated is_fail decision; a human marks correctness in a separate
    column at writeup time.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(random_seed)
    sample = matched_events if len(matched_events) <= sample_size else rng.sample(
        matched_events, k=sample_size
    )
    path = out_dir / "handcheck_sample.jsonl"
    with path.open("w") as f:
        for event in sample:
            rec = {
                "event_id": event.event_id,
                "bin_id": event.bin_id,
                "question": event.question,
                "gold_answer": event.gold_answer,
                "model_generation": event.model_generation,
                "is_fail_automated": event.is_fail,
                "human_judgment": None,  # filled by hand
            }
            f.write(json.dumps(rec) + "\n")
    return path


def write_pilot_summary(
    *,
    fits: dict[BinId, PerRegimeCompositeFit],
    strata_by_bin: dict[BinId, list[CEMStratum]],
    wall_time_sec: float,
    gpu_hours_estimate: float,
    n_events: int,
    matched_events: list[DocQAEvent],
    out_dir: Path = REPORTS_PILOT_DIR,
) -> dict[str, Path]:
    """Convenience: write all 4 reports in one call."""
    return {
        "per_bin_auroc": write_per_bin_auroc(fits, out_dir=out_dir),
        "cem_yield": write_cem_yield(strata_by_bin, out_dir=out_dir),
        "runtime": write_runtime(
            wall_time_sec=wall_time_sec,
            gpu_hours_estimate=gpu_hours_estimate,
            n_events=n_events,
            out_dir=out_dir,
        ),
        "handcheck_sample": write_handcheck_sample(matched_events, out_dir=out_dir),
    }


# Quiet unused-import warning (kept for type-friendliness in some callers).
_ = dataclasses
