"""Evidence-distance computation and bin assignment (Spec FR-001).

The regime stratification axis: tokens from end-of-evidence to first
generated answer token. Six bins (B1..B6) cover [128, 4096) at
logarithmic spacing.
"""

from __future__ import annotations

from phi3geom.dataset.types import BIN_RANGES, BinId


class EvidenceDistanceOutOfRangeError(ValueError):
    """Distance falls outside the [128, 4096) range covered by B1..B6."""


def compute_evidence_distance(
    evidence_end_token_idx: int,
    answer_commit_token_idx: int,
) -> int:
    """Return the integer token distance between the end of the evidence span
    and the first generated answer token.

    Args:
        evidence_end_token_idx: Token index (in the full prompt+generation
            sequence) of the LAST token of the answer-bearing evidence span.
        answer_commit_token_idx: Token index of the FIRST generated answer
            token (immediately after the ``Answer:`` prompt suffix).

    Returns:
        ``answer_commit_token_idx - evidence_end_token_idx``, always
        positive in well-formed events (question is positioned AFTER
        document/evidence per spec section "Stress-tests flagged for the
        spec" #4).

    Raises:
        ValueError: If the computed distance is non-positive (malformed
            event: evidence appears at or after the answer commit point).
    """
    distance = answer_commit_token_idx - evidence_end_token_idx
    if distance <= 0:
        raise ValueError(
            f"Evidence-distance must be positive (got {distance}; "
            f"evidence_end={evidence_end_token_idx}, "
            f"answer_commit={answer_commit_token_idx}). "
            "Evidence should appear before the answer commit point."
        )
    return distance


def assign_bin(distance_tokens: int) -> BinId:
    """Map an evidence-distance to one of the 6 bins B1..B6.

    Bin boundaries are half-open ``[lower, upper)``:

    | Bin | Range (tokens)  |
    |-----|-----------------|
    | B1  | [128, 256)      |
    | B2  | [256, 512)      |
    | B3  | [512, 1024)     |
    | B4  | [1024, 2048)    |
    | B5  | [2048, 3072)    |
    | B6  | [3072, 4096)    |

    Args:
        distance_tokens: Token distance from ``compute_evidence_distance``.

    Returns:
        The bin id.

    Raises:
        EvidenceDistanceOutOfRangeError: If ``distance_tokens < 128`` or
            ``distance_tokens >= 4096``. Such events are out of v1 scope
            and MUST NOT be silently bucketed.
    """
    if distance_tokens < 128 or distance_tokens >= 4096:
        raise EvidenceDistanceOutOfRangeError(
            f"distance_tokens={distance_tokens} is outside the v1 range "
            "[128, 4096). Such events are out of scope per spec FR-018."
        )
    for bin_id, (lower, upper) in BIN_RANGES.items():
        if lower <= distance_tokens < upper:
            return bin_id
    # Should be unreachable given the range check above.
    raise AssertionError(f"unreachable: distance={distance_tokens}")


def diagnostic_bin(distance_tokens: int) -> str:
    """Tolerant post-hoc diagnostic label for the distance slice.

    Unlike ``assign_bin`` (which raises outside [128, 4096) because that is
    the v1 *generation* scope), this never raises: it adds catch-all buckets
    ``"B0"`` (below B1's floor) and ``"B7"`` (at/above B6's ceiling) so the
    distance-diagnostic report can bin every event. Constitution v2.0.0:
    bins are a diagnostic, not a gate.
    """
    if distance_tokens < 128:
        return "B0"
    if distance_tokens >= 4096:
        return "B7"
    for bin_id, (lower, upper) in BIN_RANGES.items():
        if lower <= distance_tokens < upper:
            return bin_id
    raise AssertionError(f"unreachable: distance={distance_tokens}")
