# Phase 0 Research: Phi-3 Attention-Geometry v1

**Branch**: `001-phi3-attention-geometry-v1`
**Date**: 2026-05-18
**Inputs**: spec.md, plan.md, constitution.md, prior-work brainstorm (`docs/superpowers/specs/2026-05-18-phi3-attention-geometry-failure-prediction-design.md`)

This document resolves every NEEDS CLARIFICATION and dependency choice the plan deferred, plus
the open-decision items from the brainstorm document that affect Phase 1 design.

---

## §1 — HuggingFace `Phi3Attention` hook surface

**Decision**: Hook on the `Phi3Attention` module's `forward` via `torch.nn.Module.register_forward_hook`,
combined with `output_attentions=True` and `output_hidden_states=True` on the `Phi3ForCausalLM`
forward call. Extract `Q`, `K`, `V`, `attention_weights` from the attention module's intermediate
state; reconstruct `QKᵀ` (before softmax) by replaying the same head-major reshape that the
HuggingFace implementation uses. `AVWO` is reconstructed as `attention_weights @ V @ W_O` per
head, where `W_O` is sliced from the projection layer's weight matrix.

**Rationale**: `Phi3Attention` does not expose `QKᵀ` directly in `transformers ≥ 4.45`. The
post-softmax `attention_weights` is exposed when `output_attentions=True`; pre-softmax `QKᵀ`
must be recomputed from cached `Q`, `K` because the kernel fuses softmax with attention scores.
Capturing `Q` and `K` via forward hook on the attention module is the minimum-intrusion path that
preserves the model weights bit-exactly and matches the DCSBM-prior-work extraction pattern.

**Alternatives considered**:
- *Monkey-patching the attention forward*: rejected — fragile across `transformers` versions and
  obscures provenance of the recomputed tensors.
- *Using `accelerate`'s tensor-parallel hook system*: rejected — overkill for single-GPU; adds a
  dependency not otherwise needed.
- *Re-running a custom forward that mirrors `Phi3Attention`'s arithmetic*: rejected — duplicates
  HuggingFace's implementation, risk of silent divergence as `transformers` updates.

**Test plan**: `tests/unit/test_hooks.py` builds a tiny 2-layer, 4-head synthetic module with
hand-computed expected `Q/K/V/A/O` and asserts the hook recovers them within `1e-12` (no
spectral computation involved at this stage; this is a pure mechanical-recovery test).

---

## §2 — HuggingFace revision SHA for `microsoft/Phi-3-mini-128k-instruct`

**Decision**: Pin the revision SHA at the start of the pilot run (`run_pilot.sh`). The pilot
driver reads the latest commit SHA via `huggingface_hub.HfApi().model_info()` once, writes it
to the dataset manifest, and freezes thereafter for all 4800 production events. Re-pinning for
v2 work requires a new spec.

**Rationale**: The brainstorm document calls out "pick at spec time; lock in constitution" as
the resolution path for the revision SHA. The constitution does not pin the SHA itself (it
correctly defers to per-feature manifests). Pinning at pilot kickoff guarantees the manifest is
authoritative and avoids a stale pin from spec-writing time decaying before implementation.

**Alternatives considered**:
- *Pin in the spec*: rejected — the spec is a public document and includes manifest-derived
  values would couple spec text to ephemeral artifact state.
- *Use `main` branch unpinned*: rejected — violates Constitution Principle I.

**Test plan**: `tests/unit/test_manifest.py` includes a test that the manifest contains a
non-empty `model_revision_sha` field and that re-reading the manifest preserves it bit-exactly.

---

## §3 — FPCA backend: `skfda` vs `FDApy`

**Decision**: `skfda`. (Brainstorm Open Decision #9.)

**Rationale**: `skfda` has wider test coverage in its 0.9+ releases, ships with a documented
functional logistic regression class (`skfda.ml.classification.LogisticRegression`), is the
backend used by published functional-logistic-regression tutorials, and integrates cleanly with
NumPy arrays of shape `(n_curves, n_grid_points)`. `FDApy` is younger, has thinner docs, and
requires curve-object wrapping that adds friction in property tests.

**Alternatives considered**:
- *`FDApy`*: rejected for the reasons above. Revisit in v2 if `skfda` performance becomes a
  bottleneck on the 4800 × 32 spine-curve fits (unlikely; 4800 curves of 32 points is small).
- *Roll our own FPCA via `scipy` eigendecomposition*: rejected — duplicates a well-tested library
  for no measurable gain.

**Test plan**: `tests/contract/test_skfda_fpca_shape.py` asserts `(n_curves, n_grid) → (n_curves,
n_fpcs)` shape contract and that variance-explained is monotone decreasing across FPCs.

---

## §4 — Forman-Ricci reference for parity testing

**Decision**: Use `GraphRicciCurvature` (package on PyPI; commit-pin to a known-good release).
For parity tests, use the **3 explicit published reference cases** from the package's test suite:
a triangle (K₃), a square (C₄), and a star (K_{1,4}). The expected Forman-Ricci values for these
graphs are well-known analytic constants. For property tests, generate 100 random graphs on 16
nodes with edge density in `[0.1, 0.8]` (representative of post-`k_attn` attention graphs) and
assert that production and reference compute the same value within `1e-10` (the tighter tolerance
is justified because Forman-Ricci is integer/rational on small graphs).

**Rationale**: The constitution requires parity testing against a "published reference
implementation" for Ricci. `GraphRicciCurvature` is the de facto reference, used in the
mechanistic-interpretability literature for this purpose. Pinning the version avoids silent
behavioral drift.

**Alternatives considered**:
- *Hand-implement Forman-Ricci*: rejected — duplicates a well-tested library. We may STILL want
  a hand-coded version for the production path if `GraphRicciCurvature` is slow on the per-
  (t,ℓ,h) loop; in that case the hand-coded version becomes the production code and
  `GraphRicciCurvature` remains the parity oracle in tests. This decision is deferred to the
  pilot's profiling step.
- *Use Ollivier-Ricci as the parity oracle*: rejected — different metric, not a valid reference.

**Test plan**: `tests/unit/test_ricci_parity.py` covers the 3 reference graphs and 100 random
graphs.

---

## §5 — `k_attn` for attention-graph sparsification

**Decision**: Default to `k_attn=16` for the pilot. The pilot evaluates `k_attn ∈ {8, 16, 32}` on
a 100-event subset (`pilot_kattn_sweep` job) and pins the winning value before the full study
collection. Winning criterion: highest median per-bin marginal AUROC gain from Forman-Ricci
features in the per-regime composite. (Brainstorm Open Decision #6.)

**Rationale**: `k_attn=16` is a sensible midpoint: low enough to focus on dominant attention
edges (the Phi-3 attention distribution is heavy-tailed; 16 captures ≥85% mass on average per
the DCSBM prior data), high enough to give Forman-Ricci a meaningful neighborhood. Cost scales
linearly with `k_attn`: `k_attn=8` is ~4× cheaper than `k_attn=32`. The 100-event sweep is
~3 GPU-hours, low cost.

**Alternatives considered**:
- *Pin `k_attn=16` and skip the sweep*: rejected — too easy a corner to cut on the only
  remaining tunable that affects Ricci's signal strength. A 3 GPU-hour sweep is cheap insurance.
- *Pin `k_attn=32`*: rejected — pre-commits to the most expensive option without evidence.

**Test plan**: `tests/unit/test_ricci_parity.py` parameterizes over `k_attn ∈ {8, 16, 32}` to
verify the sparsification logic. The sweep itself is a pilot-time experiment, not a unit test.

---

## §6 — DCSBM codebase port: what carries, what rewrites

**Decision**: Port verbatim:
- Spectral metric primitives (`stable_rank`, `top_k_grassmannian`, `spectral_entropy`) — these
  are pure matrix → scalar functions, model-agnostic, and the parity oracle for the new
  implementation under TDD.
- Event-alignment infrastructure (`lookback_index`, `paired_sample`) — adapt for log-spaced
  lookback (DCSBM used linear; we use log).
- Per-regime composite logistic fit + AUROC framework — wraps `sklearn`; no Phi-3-specific
  changes needed.
- CUSUM/EWMA primitives — used in the two-stage FDA → TS pipeline as stage-2 detectors on
  FPCA scores.

**Rewrite**:
- Per-head extraction hooks: DCSBM was 1-head toy; Phi-3 is 32 layers × 32 heads. New code.
- Crossbar pairwise Grassmannian: different slicing on the same `top_k_grassmannian` primitive.
- FDA on spine curves: new (DCSBM didn't have this).
- Two-stage FDA → TS: stage 1 reuses `skfda` FPCA; stage 2 reuses ported CUSUM/EWMA primitives.
- Failure-EM normalization: new (replaces DCSBM rule-violation detection).
- Forman-Ricci-token: new wrapper around `GraphRicciCurvature` adapted to per-(t,ℓ,h) graph
  input.
- Dataset generator: new (synthetic Wikidata-templated DocQA).

**Rationale**: The brainstorm document already mapped this. The deciding criterion is whether
the function's signature stays bit-identical (port) or whether its tensor layout changes
(rewrite).

**Alternatives considered**:
- *Rewrite everything from scratch*: rejected — discards a working test suite. The DCSBM
  reference becomes the parity oracle.
- *Vendor the DCSBM repo as a git submodule*: rejected for now — copy the primitives into
  `src/phi3geom/geometry/spectral.py` and keep the DCSBM repo as the parity-test fixture source.
  Submodule is a v2 option if upstream changes start mattering.

**Test plan**: All ported functions get an additional `tests/unit/test_*_parity.py` that
imports from the DCSBM repo (installed as a dev dependency from a pinned git ref) and asserts
`max_abs_diff ≤ 1e-7` on 100 seeded random inputs.

---

## §7 — Long-line stage-2 detector: CUSUM vs EWMA vs PELT

**Decision**: Default to **CUSUM** for v1, with EWMA reported as a sensitivity check in the
appendix. (Brainstorm Open Decision #7.)

**Rationale**: CUSUM is the detector used in the DCSBM prior work; using the same primitive
preserves the comparison story (same detector, different geometry input). EWMA's smoother
response is useful for sensitivity analysis but adds a parameter (the smoothing factor) that
expands the multiple-testing surface. PELT is too aggressive for the FPCA-score trajectory
length (J=256 with log-spaced D giving 10 trajectory points).

**Alternatives considered**:
- *EWMA as primary*: rejected — adds a hyperparameter to the headline analysis.
- *PELT*: rejected — designed for finding multiple change points in long series; our series
  are short.

**Test plan**: `tests/unit/test_changepoint.py` ports the DCSBM CUSUM tests; the EWMA sensitivity
check is implemented but only run in the writeup-time appendix workflow, not in CI.

---

## §8 — Number of spine FPCs

**Decision**: Use **95% variance explained** as the threshold for retaining FPCs per bin per
class. Sensitivity check at 90% and 99% reported in the appendix. (Brainstorm Open Decision #8.)

**Rationale**: 95% is the standard default in functional-data-analysis practice. On 32-point
curves, 95% typically retains 3–5 FPCs; 90% would retain 2–4 (less robust); 99% would retain
6–8 (more model parameters for the same data). The full-study has 400 curves per class per bin,
giving ~80 events per FPC parameter at 5 FPCs — well within the 10× rule of thumb for stable
fitting.

**Alternatives considered**:
- *Fix FPCs = 5*: rejected — different bins likely have different intrinsic dimensionality.
- *Fix FPCs = 3*: rejected — risk under-fitting in the harder long-distance bins where the
  spine curve has more depth-dependent structure.

**Test plan**: `tests/contract/test_skfda_fpca_shape.py` asserts that the variance-explained
threshold returns a sensible n_fpcs in `[2, 8]` for synthetic curves with known intrinsic
dimensionality.

---

## §9 — Storage layout (cache header schema)

**Decision**: Cache header is a 2KB block at the start of every `.npy`-shaped tensor file (or a
sidecar `.header.json` file) containing:
- `manifest_sha256`: dataset manifest SHA at write time
- `code_commit_sha`: git commit SHA at write time
- `tensor_shape`: tuple
- `tensor_dtype`: e.g., "float32"
- `feature_layout`: ordered list of feature names mapped to the last-axis indices
- `lookback_window_length`: J (= 256)
- `lookback_indices`: explicit positions (dense for F, log-spaced for D)
- `k_grass`: 8
- `k_attn`: pinned value (from pilot)
- `forman_ricci_convention`: how degenerate-graph atomic units are handled (decided at
  implementation time; recorded here for replay)
- `write_timestamp_utc`: ISO 8601
- `host`: machine identifier (informational only; not used for integrity)

**Rationale**: Constitution Principle I requires every cached artifact to declare its
provenance. A sidecar header makes the cache file independently verifiable (one can confirm a
cache file came from a known manifest+code without loading the tensor body) and supports the
"do not silently mix runs" invariant.

**Alternatives considered**:
- *Embed in the .npy file via numpy structured dtype*: rejected — couples header to tensor
  layout; sidecar is independently inspectable.
- *No header, rely on directory name*: rejected — directory names can be renamed; SHA in the
  file is tamper-evident.

**Test plan**: `tests/unit/test_manifest.py` covers cache header round-trip; integration test
covers reading a cache file with a stale `manifest_sha256` and verifying it triggers a halt
(not a silent fallback).

---

## §10 — Degenerate Forman-Ricci atomic units (top-`k_attn` truncation produces isolated nodes)

**Decision**: When a node has zero edges after top-`k_attn` truncation, its Forman-Ricci scalar
is recorded as **NaN** in the F tensor, and downstream composite logistic fits use scikit-learn's
NaN-handling (impute with per-bin per-class median at fit time, with a separate indicator
feature recording whether the value was imputed). The imputation policy is recorded in the
manifest.

**Rationale**: Three alternatives were considered:
1. **0**: pretends absence of information is zero curvature; collapses two distinct semantic
   conditions (truly-zero Ricci vs no-data-available).
2. **NaN with median imputation + indicator**: preserves the distinction; standard practice in
   missing-data analysis; auditable from the manifest.
3. **Drop the atomic unit**: leaves holes in the F tensor that propagate into the head-graph
   spine computation; complicates indexing.

Option 2 is the cleanest semantically and is what `sklearn`'s `HistGradientBoostingClassifier`
and similar do natively. Option 1 risks biased coefficient estimates in the composite logistic.

**Alternatives considered**: See above.

**Test plan**: `tests/unit/test_ricci_parity.py` includes a graph with an isolated node after
truncation and asserts the production code emits NaN; `tests/contract/test_sklearn_logistic.py`
asserts that NaN-bearing feature matrices flow through composite fit without raising.

---

## §11 — Adversarial distractor design for B1 (and possibly B2)

**Decision**: Defer the adversariality policy to the dataset-construction phase at pilot time.
The pilot estimates natural failure rate in B1 and B2; if either is below 5%, the dataset
construction phase enables adversarial distractor injection with one of these three documented
policies (chosen by experiment-time inspection of base failure rate):
1. **Lexical-overlap distractors**: select distractor sentences from the document that share ≥2
   content tokens with the question.
2. **Wikidata sibling-entity distractors**: inject sentences asserting a fact about a different
   entity from the same Wikidata class as the gold-answer entity.
3. **Self-contradiction distractors**: insert a sentence that contradicts the evidence
   elsewhere in the document.

The chosen policy is recorded in the manifest under `adversariality_policy` and applied
identically across all B1 (or B2) events. (Brainstorm Open Decision #4.)

**Rationale**: This is a pilot-time decision because natural failure rate is unknown until
empirical observation. Pre-committing to a policy now would either over-engineer (if natural
rate is already ≥5%) or under-specify (if the chosen policy doesn't push rate to 5%).

**Alternatives considered**:
- *Pre-commit to one policy*: rejected — premature.
- *No adversarial injection*: rejected — would yield bins with <5% failures, making CEM
  matching impossible.

**Test plan**: `tests/unit/test_evidence_distance.py` parameterizes over each of the three
policies on tiny synthetic documents.

---

## §12 — Atomic-unit feature ordering (load-bearing for cache layout)

**Decision**: Feature axis order in F is fixed as:
```
[stable_rank_qkt, grassmannian_qkt, spectral_entropy_qkt,
 stable_rank_avwo, grassmannian_avwo, spectral_entropy_avwo,
 forman_ricci_attention_graph]
```
This is recorded in the cache header `feature_layout` and in `src/phi3geom/geometry/__init__.py`
as the canonical `FEATURE_NAMES` tuple. Changing this order is a breaking change requiring a
constitution-version bump on Principle IV (the dimensionality decision is pinned at v1.0.0).

**Rationale**: A fixed feature ordering is necessary for cache files to be interchangeable
across runs and machines. The order is grouped by matrix (QKᵀ block, then AVWO block, then
Ricci) for human readability.

**Alternatives considered**:
- *Group by metric type* (`stable_rank_qkt, stable_rank_avwo, grassmannian_qkt, ...`): rejected
  — less readable when inspecting a single matrix's metrics.
- *Alphabetical*: rejected — couples canonical order to incidental naming choices.

**Test plan**: `tests/unit/test_manifest.py` asserts `FEATURE_NAMES` is bit-identical across
package imports; cache writer asserts feature axis matches before write.

---

## Summary of Decisions

| § | Decision | Rationale |
|---|----------|-----------|
| 1 | Forward hook on `Phi3Attention`; recompute `QKᵀ` from cached Q/K | Minimum-intrusion extraction; preserves model bit-exactness |
| 2 | Pin HF revision SHA at pilot kickoff | Manifest is authoritative; avoids stale spec-time pin |
| 3 | `skfda` as FPCA backend | Wider test coverage, ships functional-logistic class |
| 4 | `GraphRicciCurvature` as Forman-Ricci parity oracle | De facto reference; 3 known-good reference graphs |
| 5 | `k_attn=16` pilot default; sweep {8,16,32} at pilot | Balances signal vs cost; sweep is cheap |
| 6 | Port DCSBM spectral + event-alignment + composite + CUSUM verbatim; rewrite hooks + crossbars + FDA + EM-norm + Ricci wrapper + dataset gen | Per the brainstorm porting plan |
| 7 | CUSUM as primary stage-2 detector | Preserves DCSBM comparison; EWMA in appendix |
| 8 | 95% variance threshold for spine FPCs | FDA standard; supports 3–5 FPCs typical |
| 9 | Sidecar `.header.json` for cache files | Tamper-evident provenance |
| 10 | NaN + median imputation + indicator for degenerate Forman-Ricci | Preserves missing-vs-zero distinction |
| 11 | Adversariality policy chosen at pilot time from 3 candidates | Pre-commit would be premature |
| 12 | Fixed feature axis order; pinned in `FEATURE_NAMES` | Cache portability across runs |

**All NEEDS CLARIFICATION items resolved.** Ready for Phase 1.
