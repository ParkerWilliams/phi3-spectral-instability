"""Dataclass schemas for the dataset layer.

Mirrors the entities defined in
``specs/001-phi3-attention-geometry-v1/data-model.md``. All entities are
frozen dataclasses; the manifest layer round-trips them to/from JSONL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

BinId = Literal["B1", "B2", "B3", "B4", "B5", "B6"]
DensityCoarsening = Literal["low", "med", "high"]
LengthCoarsening = Literal["1", "2-3", "4+"]
AdversarialityPolicy = Literal["none", "lexical", "sibling_entity", "self_contradiction"]

BIN_IDS: tuple[BinId, ...] = ("B1", "B2", "B3", "B4", "B5", "B6")

# Inclusive lower, exclusive upper, in tokens.
BIN_RANGES: dict[BinId, tuple[int, int]] = {
    "B1": (128, 256),
    "B2": (256, 512),
    "B3": (512, 1024),
    "B4": (1024, 2048),
    "B5": (2048, 3072),
    "B6": (3072, 4096),
}


@dataclass(frozen=True, slots=True)
class DocQAEvent:
    """One observation in the v1 study."""

    event_id: str  # 64 hex chars (SHA256)
    document: str
    question: str
    gold_answer: str
    question_template_id: str
    evidence_position_token_idx: int
    evidence_distance_tokens: int
    bin_id: BinId
    distractor_density: float  # [0.0, 1.0]
    distractor_density_coarsening: DensityCoarsening
    gold_answer_length_tokens: int
    gold_answer_length_coarsening: LengthCoarsening
    cem_stratum_id: str
    adversariality_policy: AdversarialityPolicy
    model_generation: str
    model_generation_normalized: str
    gold_answer_normalized: str
    is_fail: bool
    per_event_seed: int


@dataclass(frozen=True, slots=True)
class ManifestHeader:
    """Study-wide pins recorded in ``manifest_header.json``."""

    schema_version: str
    manifest_sha256: str  # 64 hex
    events_sha256: str  # 64 hex
    code_commit_sha: str  # 40 hex
    model_revision_sha: str  # 40 hex (HuggingFace revision)
    prompt_template_sha256: str  # 64 hex
    generation_config_sha256: str  # 64 hex
    k_grass: int
    k_attn: int
    lookback_window_length: int
    feature_layout: tuple[str, ...]
    forman_ricci_convention: str
    adversariality_policy_per_bin: dict[str, AdversarialityPolicy]
    split_seed: int
    matching_seed_per_bin: dict[str, int]
    constitution_version: str
    spec_version: str
    write_timestamp_utc: str


@dataclass(frozen=True, slots=True)
class CEMStratum:
    """A coarsening cell within a single bin."""

    bin_id: BinId
    question_template_id: str
    distractor_density_coarsening: DensityCoarsening
    gold_answer_length_coarsening: LengthCoarsening
    n_fail_pool: int
    n_ctrl_pool: int
    n_matched_pairs: int = field(default=0)

    @property
    def cem_stratum_id(self) -> str:
        return (
            f"{self.question_template_id}|"
            f"{self.distractor_density_coarsening}|"
            f"{self.gold_answer_length_coarsening}"
        )
