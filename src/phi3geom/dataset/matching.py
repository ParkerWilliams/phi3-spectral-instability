"""Coarsened Exact Matching for balanced fail/control sampling (FR-003).

CEM partitions the event pool into cells defined by three coarsenings
(question template id, distractor density coarsening, gold-answer-length
coarsening) within each evidence-distance bin, then takes
``min(n_fail, n_ctrl)`` per cell, drops cells with ``min == 0``, and
randomly subsamples each retained cell to the target count.

This module implements the core CEM algorithm. The oversample-escalation
logic (1.5× → 3×, with compromised-bin flagging at <30%) lives in
``matching.py``'s extended API added by T057 during US3.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Iterable

from phi3geom.dataset.types import (
    BinId,
    CEMStratum,
    DocQAEvent,
)


class MatchingFailedError(RuntimeError):
    """Raised when fewer than the requested matched pairs can be produced."""

    def __init__(self, bin_id: BinId, requested: int, achieved: int) -> None:
        super().__init__(
            f"Bin {bin_id}: requested {requested} matched pairs, "
            f"could only produce {achieved}."
        )
        self.bin_id = bin_id
        self.requested = requested
        self.achieved = achieved


def _stratum_key(event: DocQAEvent) -> str:
    return event.cem_stratum_id


def partition_by_stratum(
    events: Iterable[DocQAEvent],
) -> dict[str, dict[bool, list[DocQAEvent]]]:
    """Partition events by ``cem_stratum_id`` and then by ``is_fail`` label.

    Returns:
        ``{stratum_id: {True: [fail_events], False: [ctrl_events]}}``.
    """
    cells: dict[str, dict[bool, list[DocQAEvent]]] = defaultdict(
        lambda: {True: [], False: []}
    )
    for event in events:
        cells[_stratum_key(event)][event.is_fail].append(event)
    return cells


def cem_match(
    events: Iterable[DocQAEvent],
    *,
    bin_id: BinId,
    target_per_class: int,
    rng: random.Random,
) -> tuple[list[DocQAEvent], list[CEMStratum]]:
    """Apply CEM matching to produce a balanced ``target_per_class``/class
    output from the input event pool.

    Args:
        events: All events for one bin (caller pre-filters by ``bin_id``).
        bin_id: The bin label; recorded in ``CEMStratum`` outputs.
        target_per_class: Desired number of fail (and control) events.
        rng: Caller-provided RNG, seeded via
            ``reproducibility.seeds.seed_for_match(bin_id)``.

    Returns:
        ``(matched_events, strata)`` where ``matched_events`` is the
        balanced output (interleaved fail+ctrl) and ``strata`` records the
        pool / matched counts per cell for the writeup.

    Raises:
        MatchingFailedError: If the total achievable matched pairs across
            non-empty cells is less than ``target_per_class``. Callers that
            implement oversample-escalation (T057) catch this and retry.
    """
    cells = partition_by_stratum(events)

    strata: list[CEMStratum] = []
    matched_pairs: dict[str, int] = {}

    # First pass: compute per-cell achievable pair count.
    for stratum_id, by_label in cells.items():
        n_fail = len(by_label[True])
        n_ctrl = len(by_label[False])
        pairs = min(n_fail, n_ctrl)
        matched_pairs[stratum_id] = pairs

        template_id, density_coarsen, length_coarsen = stratum_id.split("|", maxsplit=2)
        strata.append(
            CEMStratum(
                bin_id=bin_id,
                question_template_id=template_id,
                distractor_density_coarsening=density_coarsen,  # type: ignore[arg-type]
                gold_answer_length_coarsening=length_coarsen,  # type: ignore[arg-type]
                n_fail_pool=n_fail,
                n_ctrl_pool=n_ctrl,
                n_matched_pairs=pairs,
            )
        )

    total_pairs = sum(matched_pairs.values())
    if total_pairs < target_per_class:
        raise MatchingFailedError(
            bin_id=bin_id, requested=target_per_class, achieved=total_pairs
        )

    # Second pass: proportional allocation across non-empty cells, then random
    # subsample to hit exactly ``target_per_class`` pairs.
    sortable = sorted(
        ((sid, p) for sid, p in matched_pairs.items() if p > 0),
        key=lambda kv: (-kv[1], kv[0]),  # stable order: largest cells first
    )

    remaining = target_per_class
    allocation: dict[str, int] = {}
    # Naive proportional: floor(target * p / total). Then distribute remainder
    # to the largest-cell rows in deterministic order.
    for stratum_id, p in sortable:
        share = (target_per_class * p) // total_pairs
        allocation[stratum_id] = min(share, p)
    deficit = target_per_class - sum(allocation.values())
    # Hand out the deficit by walking sortable order (largest first) and
    # bumping the cell's allocation until it hits the cell cap.
    i = 0
    while deficit > 0 and i < len(sortable) * 100:  # bounded retries
        stratum_id, p = sortable[i % len(sortable)]
        if allocation[stratum_id] < p:
            allocation[stratum_id] += 1
            deficit -= 1
        i += 1
    if deficit > 0:
        raise MatchingFailedError(
            bin_id=bin_id,
            requested=target_per_class,
            achieved=target_per_class - deficit,
        )

    # Third pass: randomly subsample each cell.
    matched: list[DocQAEvent] = []
    for stratum_id, n_take in allocation.items():
        if n_take <= 0:
            continue
        by_label = cells[stratum_id]
        fail_sample = rng.sample(by_label[True], k=n_take)
        ctrl_sample = rng.sample(by_label[False], k=n_take)
        matched.extend(fail_sample)
        matched.extend(ctrl_sample)

    remaining = remaining  # silence linter; remaining is computed earlier for inspection
    return matched, strata
