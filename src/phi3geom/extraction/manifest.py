"""Capture manifest — the metric→raw-material mapping (SP-0 primary deliverable).

Maps every program-catalog §5 metric
(docs/superpowers/specs/2026-06-17-v2-correctness-geometry-program-design.md) to a
``CaptureBundle`` field (data-model.md / contracts/capture-manifest.md). The
completeness check is the SC-001 gate: every catalog metric MUST resolve to a known
bundle field before any full run, else the run is blocked. Pure data + a check —
import-safe without torch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

CAPTURE_VERSION = "2.0.0"

# CaptureBundle fields (data-model.md) PLUS ``qkv_per_head`` — the per-head Q/K/V
# the capture-manifest.md requires for DLA / v1-magnitude-norms / retrieval-head
# metrics. (This reconciles a data-model.md omission: its CaptureBundle table did
# not list the per-head operators those offline metrics consume.)
BUNDLE_FIELDS: frozenset[str] = frozenset(
    {
        "hidden_answer_pos",
        "hidden_window",
        "attn_rows_answer_pos",
        "attn_full_subset",
        "token_cloud_spectra",
        "qkv_per_head",
        "samples",
        "answer_logits",
        "evidence_spans",
        "model_descriptor_ref",
    }
)

# program design §5 catalog -> bundle field (contracts/capture-manifest.md).
METRIC_TO_FIELD: dict[str, str] = {
    # 5.0 baselines / ceiling
    "confidence_logit_stats": "answer_logits",
    "semantic_entropy": "samples",
    "linear_probe": "hidden_answer_pos",
    # 5.1 residual-stream trajectory (diff-geo)
    "trajectory_curvature": "hidden_answer_pos",
    "logit_lens_convergence": "hidden_answer_pos",
    "local_intrinsic_dimension": "hidden_window",
    "per_token_dynamics": "hidden_window",
    # 5.2 realized routing (functional analysis)
    "attention_to_evidence": "attn_rows_answer_pos",
    "routing_entropy": "attn_rows_answer_pos",
    "direct_logit_attribution": "qkv_per_head",
    "retrieval_head_signature": "attn_rows_answer_pos",
    "attention_rollout": "attn_full_subset",
    "markov_operator_spectra": "attn_full_subset",
    # 5.3 random matrix theory
    "mp_deviation_spikes": "token_cloud_spectra",
    "eigenvalue_spacing": "token_cloud_spectra",
    "effective_rank": "token_cloud_spectra",
    # 5.4 attention-graph geometry
    "ollivier_ricci": "attn_full_subset",
    "cheeger_laplacian": "attn_full_subset",
    # 5.5 v1 object, repaired
    "v1_magnitude_norms": "qkv_per_head",
    "v1_dynamics": "qkv_per_head",
}

# The full §5 catalog (everything the first big run must be able to feed).
PROGRAM_CATALOG_METRICS: frozenset[str] = frozenset(METRIC_TO_FIELD)

# The subset the US1 MVP capture already feeds (no per-head ops / full T×T yet).
US1_METRIC_SUBSET: frozenset[str] = frozenset(
    {
        "confidence_logit_stats",
        "semantic_entropy",
        "linear_probe",
        "trajectory_curvature",
        "logit_lens_convergence",
        "mp_deviation_spikes",
        "eigenvalue_spacing",
        "effective_rank",
    }
)


@dataclass(frozen=True)
class CompletenessResult:
    """Outcome of the SC-001 completeness gate."""

    complete: bool
    missing_metrics: tuple[str, ...]  # catalog metrics with no mapping
    unknown_fields: tuple[str, ...]  # mappings pointing at a non-bundle field


def check_completeness(
    catalog: Iterable[str] = PROGRAM_CATALOG_METRICS,
    *,
    metric_to_field: dict[str, str] = METRIC_TO_FIELD,
    bundle_fields: frozenset[str] = BUNDLE_FIELDS,
) -> CompletenessResult:
    """Assert every ``catalog`` metric maps to a known bundle field.

    Returns a ``CompletenessResult``; ``complete`` is True iff no catalog metric
    is unmapped and no mapping points at a field absent from ``bundle_fields``.
    """
    catalog = set(catalog)
    missing = tuple(sorted(m for m in catalog if m not in metric_to_field))
    unknown = tuple(
        sorted(
            {
                metric_to_field[m]
                for m in catalog
                if m in metric_to_field and metric_to_field[m] not in bundle_fields
            }
        )
    )
    return CompletenessResult(
        complete=(not missing and not unknown),
        missing_metrics=missing,
        unknown_fields=unknown,
    )
