# Data Model: Phi-3 Attention-Geometry v1

**Branch**: `001-phi3-attention-geometry-v1`
**Date**: 2026-05-18

This document defines the entities, fields, relationships, and validation rules for the
v1 study. It is the contract between the dataset/extraction stages and the analysis stages.

---

## Entity: `DocQAEvent`

A single observation in the study: one (document, question, gold-answer) triple presented to
Phi-3-mini-128k-instruct with evidence at a controlled distance from the answer site.

**Fields**:

| Field | Type | Description |
|---|---|---|
| `event_id` | `str (64 hex chars)` | `SHA256(prompt_template_sha ‖ doc_bytes ‖ q_bytes ‖ gold_bytes)`. Primary key. |
| `document` | `str` | Synthetic Wikidata-templated document; evidence at controlled position. |
| `question` | `str` | Question targeting the evidence; one of ~10 Wikidata templates. |
| `gold_answer` | `str` | Canonical Wikidata-templated gold answer (no preposition, no article). |
| `question_template_id` | `str` | One of ~10 enumerated template ids. CEM stratification axis. |
| `evidence_position_token_idx` | `int` | Token index of the END of the evidence span in the prompt. |
| `evidence_distance_tokens` | `int` | Tokens from end-of-evidence to first generated answer token. |
| `bin_id` | `enum {B1, B2, B3, B4, B5, B6}` | Evidence-distance bin assignment. |
| `distractor_density` | `float ∈ [0, 1]` | Fraction of bin-width-minus-evidence-span filled with distractors. |
| `distractor_density_coarsening` | `enum {low, med, high}` | CEM stratification axis. |
| `gold_answer_length_tokens` | `int` | Number of tokens in the gold answer. |
| `gold_answer_length_coarsening` | `enum {1, 2-3, 4+}` | CEM stratification axis. |
| `cem_stratum_id` | `str` | `f"{question_template_id}|{distractor_density_coarsening}|{gold_answer_length_coarsening}"`. |
| `adversariality_policy` | `enum {none, lexical, sibling_entity, self_contradiction}` | Recorded per bin; non-`none` only for B1 and possibly B2. |
| `model_generation` | `str` | Phi-3's output after `<\|assistant\|>` up to first stop token. |
| `model_generation_normalized` | `str` | After NFKC→lowercase→strip-articles→collapse-whitespace pipeline. |
| `gold_answer_normalized` | `str` | Same normalization applied to gold. |
| `is_fail` | `bool` | `model_generation_normalized != gold_answer_normalized`. The label. |
| `per_event_seed` | `int` | `int(sha1("event:" + event_id).hexdigest()[:8], 16)`. |

**Validation rules**:
- `event_id` MUST be exactly 64 hex chars (SHA256 output).
- `evidence_distance_tokens` MUST fall within the inclusive-exclusive interval of its `bin_id`.
- `bin_id` MUST be one of the 6 enumerated values; `B6` is conditionally headline per FR-017.
- `cem_stratum_id` MUST be derivable from the three coarsening fields.
- `model_generation_normalized` and `gold_answer_normalized` MUST be the output of applying the
  6-step normalization pipeline (NFKC → lowercase → strip-leading-whitespace-and-punctuation →
  strip-leading-articles → collapse-internal-whitespace → strip-trailing-punctuation-and-
  whitespace).
- `is_fail` MUST be the strict string-equality result of comparing the two normalized strings.

**Relationships**:
- 1-to-1 with `AtomicUnitFeatureBlock` (one per event, indexed by `event_id`).
- 1-to-1 with `PairwiseHeadDistanceBlock` (one per event).
- N-to-1 with `EvidenceDistanceBin` (each event belongs to one bin).
- N-to-1 with `CEMStratum` (each event belongs to one stratum within its bin).

---

## Entity: `AtomicUnit`

A single (token, layer, head) location where one `QKᵀV` computation occurs during Phi-3's
forward pass on a `DocQAEvent`.

**Fields**:

| Field | Type | Description |
|---|---|---|
| `event_id` | `str` | Foreign key to `DocQAEvent`. |
| `token_idx` | `int ∈ [0, T)` | Position in the full prompt+generation sequence. |
| `layer_idx` | `int ∈ [0, 32)` | Phi-3 layer index. |
| `head_idx` | `int ∈ [0, 32)` | Head index within the layer. |
| `relative_token_position` | `int` | `token_idx - t_answer_commit`, ranging over `[-256, 0]` within the lookback window. |
| `features` | `np.ndarray[float32] shape (7,)` | The 7 atomic-unit feature scalars in canonical order. |

**Validation rules**:
- The composite key `(event_id, token_idx, layer_idx, head_idx)` is unique.
- `features` axis order MUST be `[stable_rank_qkt, grassmannian_qkt, spectral_entropy_qkt,
  stable_rank_avwo, grassmannian_avwo, spectral_entropy_avwo, forman_ricci_attention_graph]`
  (research.md §12).
- `forman_ricci_attention_graph` MAY be NaN when the node was isolated after top-`k_attn`
  truncation (research.md §10); other features MUST NOT be NaN.
- Stable rank, Grassmannian, and spectral entropy MUST have been computed in float64; the
  stored float32 is a downcast at the cache boundary.

**Relationships**:
- N-to-1 with `DocQAEvent`.
- The set of atomic units for one event populates the dense `F` tensor for that event.

---

## Entity: `HeadGraph`

A 32-node graph at fixed `(event_id, token_idx, layer_idx)` representing pairwise head-head
geometric distance at that location.

**Fields**:

| Field | Type | Description |
|---|---|---|
| `event_id` | `str` | Foreign key. |
| `token_idx` | `int` | Position in sequence. |
| `layer_idx` | `int ∈ [0, 32)` | Layer index. |
| `edge_type` | `enum {qkt_grassmannian, avwo_grassmannian}` | Which subspace defines edge weights. |
| `edges` | `np.ndarray[float32] shape (496,)` | Pairwise Grassmannian distances for the 32-choose-2 head pairs in canonical (i<j) lex order. |

**Validation rules**:
- The composite key `(event_id, token_idx, layer_idx, edge_type)` is unique.
- `edges` has exactly 496 entries.
- Edge order: `(i, j)` for `0 ≤ i < j ≤ 31` in lexicographic order (i.e., `(0,1), (0,2), …,
  (0,31), (1,2), …, (30,31)`).
- Both `qkt_grassmannian` and `avwo_grassmannian` head-graphs exist independently per
  `(event_id, token_idx, layer_idx)`; they are analyzed separately (FR-006).

**Relationships**:
- N-to-1 with `DocQAEvent`.
- Aggregates of `HeadGraph` form one point of a `SpineCurve`.

---

## Entity: `SpineCurve`

A 32-point function over the depth axis at fixed `(event_id, token_idx)`. Each point is a
head-graph aggregate at that depth.

**Fields**:

| Field | Type | Description |
|---|---|---|
| `event_id` | `str` | Foreign key. |
| `token_idx` | `int` | Position. |
| `edge_type` | `enum {qkt_grassmannian, avwo_grassmannian}` | Which head-graph underlies the aggregates. |
| `points` | `np.ndarray[float32] shape (32, 4)` | At each layer: `[mean_grassmannian, spectral_gap, mean_forman_ricci, modularity]`. |

**Validation rules**:
- The composite key `(event_id, token_idx, edge_type)` is unique.
- `points` shape is exactly `(32, 4)`.
- Aggregate order at each layer: `[mean_grassmannian, spectral_gap, mean_forman_ricci,
  modularity]`. (Mean Forman-Ricci aggregates over the 32 atomic units at that depth; if any
  of those is NaN, the mean uses NaN-aware averaging with the count of valid entries recorded
  separately.)

**Relationships**:
- N-to-1 with `DocQAEvent`.
- Input substrate for `FPCAResult` and `FunctionalLogisticResult`.

---

## Entity: `LongLine`

A time series at fixed `(event_id, layer_idx, head_idx)` over the lookback window.

**Fields**:

| Field | Type | Description |
|---|---|---|
| `event_id` | `str` | Foreign key. |
| `layer_idx` | `int ∈ [0, 32)` | Layer index. |
| `head_idx` | `int ∈ [0, 32)` | Head index. |
| `relative_token_positions` | `np.ndarray[int] shape (J=256,)` | `[-255, -254, …, 0]`. |
| `feature_series` | `np.ndarray[float32] shape (256, 7)` | Per-atomic-unit features over the lookback. |

**Validation rules**:
- The composite key `(event_id, layer_idx, head_idx)` is unique.
- `feature_series` shape is exactly `(256, 7)`; feature axis matches `AtomicUnit.features` order.
- Time axis is aligned to `t_answer_commit` at position `-0` (the last index).

**Relationships**:
- N-to-1 with `DocQAEvent`.
- Input substrate for the two-stage FDA → CUSUM/EWMA pipeline.

---

## Entity: `EvidenceDistanceBin`

One of 6 stratification bins on the evidence-distance axis.

| Field | Type | Description |
|---|---|---|
| `bin_id` | `enum {B1, B2, B3, B4, B5, B6}` | Identifier. |
| `min_distance_tokens` | `int` (inclusive) | Bin lower bound. |
| `max_distance_tokens` | `int` (exclusive) | Bin upper bound. |
| `is_headline` | `bool` | Whether the bin is included in the headline AUROC table (B6 may be set false post-pilot per FR-017). |

Enumerated values:

| `bin_id` | `min_distance_tokens` | `max_distance_tokens` | `is_headline` (default) |
|---|---|---|---|
| B1 | 128 | 256 | True |
| B2 | 256 | 512 | True |
| B3 | 512 | 1024 | True |
| B4 | 1024 | 2048 | True |
| B5 | 2048 | 3072 | True |
| B6 | 3072 | 4096 | True (revisable post-pilot) |

**Validation**: `max_distance_tokens > min_distance_tokens`. Bins are disjoint and contiguous.

---

## Entity: `CEMStratum`

A coarsening cell within an `EvidenceDistanceBin`. Defines the unit of fail/control balancing.

| Field | Type | Description |
|---|---|---|
| `bin_id` | `enum` | Parent bin. |
| `question_template_id` | `str` | One of ~10. |
| `distractor_density_coarsening` | `enum {low, med, high}` | |
| `gold_answer_length_coarsening` | `enum {1, 2-3, 4+}` | |
| `n_fail_pool` | `int` | Events in this cell labeled as failures (raw pool). |
| `n_ctrl_pool` | `int` | Events in this cell labeled as controls (raw pool). |
| `n_matched_pairs` | `int` | `min(n_fail_pool, n_ctrl_pool)` after CEM. |

**Validation**: Each event's `cem_stratum_id` MUST match exactly one stratum. Cells with
`n_matched_pairs == 0` are dropped (FR-003).

---

## Entity: `PerRegimeCompositeFit`

A logistic regression model fit independently within one `EvidenceDistanceBin`.

| Field | Type | Description |
|---|---|---|
| `bin_id` | `enum` | Bin this fit applies to. |
| `feature_names` | `list[str]` | Names of the candidate features used in the fit (atomic features + head-graph aggregates + spine FPC scores). |
| `coefficients` | `np.ndarray[float64] shape (n_features,)` | Fitted L2-regularized logistic coefficients. |
| `intercept` | `float64` | Fitted intercept. |
| `auroc` | `float` | AUROC on a held-out split within the bin. |
| `auroc_ci_lower` | `float` | 95% CI lower bound. |
| `auroc_ci_upper` | `float` | 95% CI upper bound. |
| `n_events_train` | `int` | Number of events used for fitting (≤ 800 per bin pre-split). |
| `n_events_held_out` | `int` | Number of events used for AUROC. |

**Validation**:
- `bin_id` MUST be a single bin; cross-bin pooling is forbidden by FR-010 (use
  `PooledNegativeControl` for SC-003 instead).
- `auroc_ci_lower ≤ auroc ≤ auroc_ci_upper`.
- For SC-001 headline pass: in ≥4 of 6 bins, `auroc > 0.80` and `auroc_ci_lower > 0.50`.

---

## Entity: `FunctionalLogisticResult`

A functional logistic regression on 32-point spine curves within one bin.

| Field | Type | Description |
|---|---|---|
| `bin_id` | `enum` | Bin this fit applies to. |
| `edge_type` | `enum {qkt_grassmannian, avwo_grassmannian}` | Which head-graph underlies the spines. |
| `n_fpcs` | `int` | Number of FPCs retained (≥95% variance). |
| `fpc_variance_explained` | `np.ndarray[float] shape (n_fpcs,)` | Per-FPC variance share. |
| `beta_function` | `np.ndarray[float64] shape (32,)` | β(ℓ) coefficient function. |
| `beta_ci_lower` | `np.ndarray[float64] shape (32,)` | 95% CI lower band per layer. |
| `beta_ci_upper` | `np.ndarray[float64] shape (32,)` | 95% CI upper band per layer. |
| `discriminative_depth_intervals` | `list[tuple[int, int]]` | Inclusive `(start_ℓ, end_ℓ)` layer ranges where `beta_ci_lower > 0` or `beta_ci_upper < 0`. |

**Validation**:
- `bin_id` MUST be a single bin (FR-010 applies to functional regression too).
- `beta_function`, `beta_ci_lower`, `beta_ci_upper` all have length 32 (one per layer).
- For SC-002 headline pass: in ≥4 of 6 bins, `discriminative_depth_intervals` is non-empty.

---

## Entity: `PooledNegativeControl`

A logistic regression fit on events pooled across all 6 bins. Exists only for SC-003.

| Field | Type | Description |
|---|---|---|
| `feature_names` | `list[str]` | Same features as `PerRegimeCompositeFit`. |
| `coefficients` | `np.ndarray[float64]` | Fitted coefficients. |
| `auroc` | `float` | Pooled AUROC. |
| `auroc_ci_lower`, `auroc_ci_upper` | `float` | 95% CI bounds. |

**Validation**: This entity is constructed by `analysis/pooled_negative_control.py` only;
attempting to construct it from `analysis/composite.py` is a programming error and MUST raise.
For SC-003 pass: `auroc < 0.75` OR `auroc_ci_lower < 0.55` (substantial CI overlap with 0.50).

---

## Entity: `DatasetManifest`

JSONL file at `dataset/manifest.jsonl`. One line per `DocQAEvent`. Committed to git.

| Field | Type | Description |
|---|---|---|
| `event_id` | `str` | Primary key. |
| `bin_id` | `enum` | |
| `cem_stratum_id` | `str` | |
| `is_fail` | `bool` | |
| `per_event_seed` | `int` | |
| (all other `DocQAEvent` fields except `document`, `question`, `gold_answer`) | various | The full text fields are stored separately in `dataset/events.jsonl` to keep the manifest scannable. |

A separate **`manifest_header.json`** records study-wide pins:

| Field | Type | Description |
|---|---|---|
| `manifest_sha256` | `str` | Self-SHA computed at write time. |
| `code_commit_sha` | `str` | Git commit of analysis code at manifest write time. |
| `model_revision_sha` | `str` | HuggingFace revision SHA for `microsoft/Phi-3-mini-128k-instruct`. |
| `prompt_template_sha256` | `str` | Prompt template SHA256. |
| `generation_config_sha256` | `str` | Generation config SHA256. |
| `k_grass` | `int` | 8. |
| `k_attn` | `int` | Pilot-pinned. |
| `lookback_window_length` | `int` | 256. |
| `feature_layout` | `list[str]` | `FEATURE_NAMES` (research.md §12). |
| `forman_ricci_convention` | `str` | "NaN + median impute + indicator" (research.md §10). |
| `adversariality_policy_per_bin` | `dict[str, str]` | Per-bin policy from research.md §11. |

---

## Cross-entity invariants

1. Every `DocQAEvent` has exactly 1 `AtomicUnitFeatureBlock` (256 tokens × 32 layers × 32 heads
   atomic units) and exactly 1 `PairwiseHeadDistanceBlock`.
2. The total count of `DocQAEvent` records with `is_fail == True` per `bin_id` equals 400 for
   each headline bin (FR-001).
3. Within each bin, the joint distribution of `(question_template_id,
   distractor_density_coarsening, gold_answer_length_coarsening)` over the 400 fail events
   exactly matches the joint distribution over the 400 control events (FR-003, CEM property).
4. `event_id` uniquely identifies a `DocQAEvent` and is reproducible from the four content fields
   `(prompt_template_sha, document_bytes, question_bytes, gold_answer_bytes)` (FR-011).
5. A `PerRegimeCompositeFit` for `bin_id=X` MUST NOT have been fit on events with any other
   `bin_id` (FR-010); enforced at the function-API level by accepting only the bin-filtered
   feature matrix as input.
