"""CEM oversample escalation logic (FR-015, T057).

Wraps ``cem_match`` with retry-at-3× behavior:

- Attempt at 1.5× target_per_class oversample.
- If yield <50%, escalate to 3× oversample.
- If yield <30% at 3×, flag the bin as compromised in the report and
  return the best-effort match.
- If yield <10% at 3×, raise ``CEMYieldEscalationError`` — the researcher
  must investigate before continuing.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from phi3geom.dataset.matching import MatchingFailedError, cem_match
from phi3geom.dataset.types import BinId, CEMStratum, DocQAEvent

OVERSAMPLE_1_5X = 1.5
OVERSAMPLE_3X = 3.0
YIELD_OK_THRESHOLD_PCT = 50.0
YIELD_COMPROMISED_THRESHOLD_PCT = 30.0
YIELD_ESCALATE_TO_USER_PCT = 10.0


class CEMYieldEscalationError(RuntimeError):
    """Yield is so low even 3× oversampling can't recover; user intervention required."""


@dataclass
class MatchResult:
    bin_id: BinId
    matched_events: list[DocQAEvent]
    strata: list[CEMStratum]
    yield_pct: float
    oversample_factor: float
    is_compromised: bool


def _yield_pct(strata: list[CEMStratum]) -> float:
    """Total matched_pairs / max-possible-pairs across strata, in %."""
    total_pairs = sum(s.n_matched_pairs for s in strata)
    max_possible = min(
        sum(s.n_fail_pool for s in strata),
        sum(s.n_ctrl_pool for s in strata),
    )
    if max_possible <= 0:
        return 0.0
    return 100.0 * total_pairs / max_possible


def cem_match_with_escalation(
    *,
    event_generator,  # callable: int → list[DocQAEvent]
    bin_id: BinId,
    target_per_class: int,
    rng: random.Random,
) -> MatchResult:
    """Run CEM matching with 1.5× → 3× escalation.

    Args:
        event_generator: Callable that takes a target sample count and
            returns a fresh pool of candidate events for this bin.
            Should be a partial of ``_generate_candidate_events`` bound to
            ``bin_id``.
        bin_id: Bin label.
        target_per_class: Desired matched pairs.
        rng: Seeded RNG.

    Returns:
        ``MatchResult``.

    Raises:
        CEMYieldEscalationError: 3× oversampling yields <10%; needs human
            inspection.
    """
    # First attempt at 1.5× oversample.
    pool_1_5 = event_generator(int(target_per_class * 2 * OVERSAMPLE_1_5X))
    try:
        matched, strata = cem_match(
            pool_1_5,
            bin_id=bin_id,
            target_per_class=target_per_class,
            rng=rng,
        )
        pct = _yield_pct(strata)
        if pct >= YIELD_OK_THRESHOLD_PCT:
            return MatchResult(
                bin_id=bin_id,
                matched_events=matched,
                strata=strata,
                yield_pct=pct,
                oversample_factor=OVERSAMPLE_1_5X,
                is_compromised=False,
            )
    except MatchingFailedError:
        pass

    # Escalate to 3× oversample.
    pool_3 = event_generator(int(target_per_class * 2 * OVERSAMPLE_3X))
    try:
        matched, strata = cem_match(
            pool_3,
            bin_id=bin_id,
            target_per_class=target_per_class,
            rng=rng,
        )
    except MatchingFailedError as exc:
        raise CEMYieldEscalationError(
            f"Bin {bin_id}: 3× oversample failed to produce {target_per_class} "
            f"matched pairs ({exc.achieved} achievable). User intervention required."
        ) from exc

    pct = _yield_pct(strata)
    if pct < YIELD_ESCALATE_TO_USER_PCT:
        raise CEMYieldEscalationError(
            f"Bin {bin_id}: yield {pct:.1f}% at 3× oversample (<{YIELD_ESCALATE_TO_USER_PCT}%). "
            "User intervention required."
        )
    is_compromised = pct < YIELD_COMPROMISED_THRESHOLD_PCT
    return MatchResult(
        bin_id=bin_id,
        matched_events=matched,
        strata=strata,
        yield_pct=pct,
        oversample_factor=OVERSAMPLE_3X,
        is_compromised=is_compromised,
    )
