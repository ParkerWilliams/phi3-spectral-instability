---
description: "Task list for Phi-3 Attention-Geometry v1"
---

# Tasks: Phi-3 Attention-Geometry as a Leading Indicator of DocQA Failures (v1)

**Input**: Design documents from `/specs/001-phi3-attention-geometry-v1/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Test tasks are included throughout. Tests are mandatory for items in the Constitution
Principle II TDD scope (spectral primitives, Forman-Ricci-token, hooks, dataset construction +
evidence-distance, CEM matching, EM normalization, crossbar, event-alignment, storage manifest,
CUSUM/EWMA on FPCA scores). Library wrappers (`skfda`, `sklearn`) get contract tests. End-to-end
pipeline gets one integration test. Exploratory probes under `exploratory/` are exempt.

**Organization**: Tasks grouped by user story (US1 Pilot → US2 Forman-Ricci → US3 Full-Study → US4
Headline Report). Phase 1 (Setup) and Phase 2 (Foundational) precede all stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story this task serves (US1, US2, US3, US4) — required in story phases
- File paths are absolute from repository root

## Path Conventions

- Source: `src/phi3geom/`
- Tests: `tests/unit/` (TDD scope), `tests/contract/` (library wrappers), `tests/integration/`
- Scripts: `scripts/` (bash drivers), `src/phi3geom/scripts/` (Python entrypoints)
- Exploratory carve-out: `exploratory/` (must NOT be imported by `src/phi3geom/`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependency declaration, lint/test tooling, directory layout.

- [X] T001 Create `src/phi3geom/` package structure with submodules per `plan.md` (dataset, extraction, geometry, lattice, analysis, storage, reproducibility, reporting, scripts) — empty `__init__.py` files only
- [X] T002 Initialize `pyproject.toml` with project metadata, runtime deps (`torch>=2.3`, `transformers>=4.45`, `numpy`, `scipy`, `scikit-learn`, `skfda`, `GraphRicciCurvature`, `networkx`, `pandas`, `huggingface_hub`), and `[project.optional-dependencies]` dev block (`pytest`, `hypothesis`, `ruff`, `mypy`)
- [X] T003 [P] Add DCSBM reference repo as pinned git dev dependency in `pyproject.toml` (parity oracle for spectral primitives — Constitution Principle II)
- [X] T004 [P] Configure `pytest` with `hypothesis` profile (100 examples per `@given`, 5-minute deadline disabled for parity tests) in `pyproject.toml` `[tool.pytest.ini_options]`
- [X] T005 [P] Configure `ruff` (line length 100, no-trailing-whitespace) and `mypy` (strict) in `pyproject.toml`
- [X] T006 [P] Create `tests/unit/`, `tests/contract/`, `tests/integration/` with `__init__.py` and `conftest.py` containing shared fixtures (seeded RNG, tiny synthetic attention module factory)
- [X] T007 [P] Create root-level `exploratory/` (with `notebooks/` and `probes/` subdirs) and `scripts/` directories; add `exploratory/README.md` documenting the TDD carve-out per Constitution Principle II
- [X] T008 Add `src/phi3geom/scripts/check_hf_auth.py` that calls `huggingface_hub.whoami()` and prints actionable failure on missing token

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Scientific primitives and infrastructure required by every user story. No user story
work may begin until this phase is complete. Every module in this phase is TDD scope per
Constitution Principle II — tests are written FIRST and MUST FAIL before the corresponding
implementation passes.

**CRITICAL**: No user story work can begin until this phase is complete.

### Reproducibility seam

- [X] T009 Write `tests/unit/test_seeds.py` — assert `seed_for_event(event_id)`, `seed_for_match(bin_id)`, `seed_for_split("v1")`, `seed_for_analysis(step_name)` are deterministic, return `int`, and match the SHA1-derivation rule from `data-model.md` (Constitution Principle I)
- [X] T010 Implement `src/phi3geom/reproducibility/seeds.py` to pass T009

### Spectral primitives (parity vs DCSBM)

- [X] T011 [P] Write `tests/unit/test_spectral_parity.py` — 100 Hypothesis-driven random `(96, 96)` float64 matrices; assert `max_abs_diff ≤ 1e-7` between local `stable_rank`/`top_k_grassmannian`/`spectral_entropy` and DCSBM reference (Constitution Principle IV)
- [X] T012 [P] Write `tests/unit/test_spectral_individual.py` — per-primitive correctness tests (rank-1 entropy = 0, identity stable rank = N, k_grass dim sanity)
- [X] T013 Implement `src/phi3geom/geometry/spectral.py` (`stable_rank`, `top_k_grassmannian`, `spectral_entropy`) to pass T011 and T012; reject float32 inputs with `TypeError` per `contracts/atomic_unit.md`

### Forman-Ricci primitive (parity vs GraphRicciCurvature)

- [X] T014 [P] Write `tests/unit/test_ricci_parity.py` — 3 explicit reference graphs (K₃, C₄, K₁,₄) + 100 random 16-node graphs with edge density `[0.1, 0.8]`; assert `max_abs_diff ≤ 1e-10` vs `GraphRicciCurvature`; isolated-node case returns `np.nan`
- [X] T015 Implement `src/phi3geom/geometry/ricci.py::forman_ricci_token(graph)` to pass T014; define canonical `FEATURE_NAMES` tuple in `src/phi3geom/geometry/__init__.py` per `research.md §12`

### Failure-EM normalization

- [X] T016 [P] Write `tests/unit/test_normalization.py` — golden table covering each of the 6 normalization steps independently and the full pipeline; verify NFKC, lowercase, article-strip, whitespace-collapse on adversarial inputs (`"  The Eiffel Tower."` → `"eiffel tower"`)
- [X] T017 Implement `src/phi3geom/dataset/normalization.py::normalize_em(text)` to pass T016 per spec FR-002

### Evidence-distance computation

- [X] T018 [P] Write `tests/unit/test_evidence_distance.py` — verify token-distance from end-of-evidence to first generated answer token under known tokenizer fixtures; assert bin assignment correctness for all 6 bins
- [X] T019 Implement `src/phi3geom/dataset/distance.py::compute_evidence_distance(prompt, evidence_span, answer_commit_idx)` and `assign_bin(distance)` to pass T018

### CEM matching

- [X] T020 [P] Write `tests/unit/test_matching.py` — verify CEM cell partitioning on (template_id, density_coarsening, length_coarsening); assert `min(n_fail, n_ctrl)` per cell; assert cells with `min=0` are dropped; assert balanced 400/400 output when input pool supports it
- [X] T021 Implement `src/phi3geom/dataset/matching.py::cem_match(events, target_per_class)` to pass T020 per spec FR-003

### Dataset manifest I/O

- [X] T022 [P] Write `tests/unit/test_manifest.py` per `contracts/manifest.md` test obligations — `test_event_id_reproducible`, `test_sha_integrity_failure`, `test_round_trip`, `test_header_required_fields`
- [X] T023 Implement `src/phi3geom/dataset/manifest.py` (`write_manifest`, `read_manifest`, `verify_event_id`) to pass T022; uses `seeds.py` from T010

### Storage cache I/O

- [X] T024 [P] Write `tests/unit/test_cache.py` per `contracts/cache.md` test obligations — `test_write_read_F_round_trip`, `test_stale_sha_raises`, `test_shape_mismatch_raises`, `test_dtype_rejection`
- [X] T025 Implement `src/phi3geom/storage/cache.py` (`write_F`, `read_F`, `write_D`, `read_D`, `write_F_summary`, `read_F_summary` + sidecar `.header.json`) to pass T024

### Phi-3 attention hooks

- [X] T026 [P] Write `tests/unit/test_hooks.py` — build a tiny 2-layer 4-head synthetic `nn.Module` matching `Phi3Attention`'s shape contract; hand-compute expected Q/K/V/A/O; assert hook recovery to 1e-12 (mechanical correctness, no spectral computation)
- [X] T027 Implement `src/phi3geom/extraction/hooks.py` (`register_phi3_attention_hooks`, `recover_qkt_from_cached_qk`) to pass T026 per `research.md §1`

### Constitution Principle III segregation

- [X] T028 [P] Write `tests/unit/test_principle_iii_segregation.py` — assert `pooled_negative_control.fit` is NOT importable from `phi3geom.analysis.composite`; assert `fit_per_regime_composite(bin_id=None)` raises `ValueError`; assert `bin_id="ALL"` raises
- [X] T029 Implement skeleton `src/phi3geom/analysis/composite.py` (raise-on-bad-bin shell) and `src/phi3geom/analysis/pooled_negative_control.py` (separate module shell) to pass T028; both files contain `raise NotImplementedError` bodies for the actual fit logic (filled in US1 and US4)

### Setup polish

- [X] T030 Add `[project.scripts]` entries to `pyproject.toml` for `pin-model-revision`, `run-pilot`, `run-full-study`, `regenerate-dataset`, `check-hf-auth`

**Checkpoint**: Foundation ready — all scientific primitives parity-verified, all data-layer
contracts enforced by tests. User story work can now begin.

---

## Phase 3: User Story 1 - Pilot End-to-End Pipeline (Priority: P1) 🎯 MVP

**Goal**: Run the full data → forward-pass → geometry-extraction → per-regime composite pipeline
at pilot scale (600 events) on Phi-3-mini-128k-instruct, producing a per-bin AUROC report for a
spectral-only baseline composite. Ricci integration is US2.

**Independent Test**: Run `scripts/run_pilot.sh` on 600 events. Verify per-bin AUROC report
produced, hand-verification on 50 events shows 100% agreement, CEM yield reported per bin,
runtime ≤72 GPU-hours. Spec acceptance scenarios US1.1–US1.3.

### Model revision pinning

- [X] T031 [P] [US1] Write `tests/unit/test_pin_model_revision.py` — assert SHA is written to `manifest_header.json`; assert re-running without `--force-repin` refuses to overwrite an existing pin
- [X] T032 [US1] Implement `src/phi3geom/scripts/pin_model_revision.py` to pass T031 per `research.md §2`

### Synthetic Wikidata DocQA generator

- [X] T033 [P] [US1] Write `tests/unit/test_generation.py` — enumerate ~10 template ids, verify document construction places evidence at requested token distance, verify gold-answer canonical form (no leading article/preposition), verify event_id derivation from text fields
- [X] T034 [US1] Implement `src/phi3geom/dataset/generation.py` with ~10 Wikidata-style templates (e.g., "Where was X born?", "What is the capital of X?", "When did X die?") to pass T033 per spec FR-001

### End-to-end forward pipeline

- [X] T035 [P] [US1] Write `tests/contract/test_event_alignment.py` — port DCSBM lookback-indexing tests; verify log-spaced D positions `{0,1,2,4,8,16,32,64,128,256}` and dense F positions `[-255, …, 0]` align to `t_answer_commit`
- [X] T036 [US1] Implement `src/phi3geom/extraction/pipeline.py::run_event_forward_pass(event, model, tokenizer)` — orchestrates hook attach → forward → QKᵀ recovery → atomic-unit feature compute → crossbar → spine aggregate → cache write; depends on T013, T015, T025, T027

### Atomic-unit feature assembly

- [X] T037 [P] [US1] Write `tests/unit/test_atomic_unit_assembly.py` — verify the assembled 7-vector matches `FEATURE_NAMES` axis order; for US1 baseline, allow Ricci slot = NaN (US2 will populate); verify float64 throughout the seam
- [X] T038 [US1] Implement `src/phi3geom/geometry/atomic_unit.py::compute_atomic_unit_features(qkt, avwo, attention_graph, k_grass, k_attn)` per `contracts/atomic_unit.md`; passes T037

### Crossbar (pairwise head-head Grassmannian)

- [X] T039 [P] [US1] Write `tests/unit/test_crossbar.py` — verify 32-choose-2 = 496 edge ordering in lex `(i<j)` order; verify QKᵀ-Grassmannian and AVWO-Grassmannian computed independently; verify symmetry property `D[i,j] = D[j,i]`
- [X] T040 [US1] Implement `src/phi3geom/lattice/crossbar.py::compute_pairwise_grassmannian(qkt_heads, avwo_heads, k_grass)` to pass T039 per spec FR-006

### Spine curves

- [X] T041 [P] [US1] Write `tests/unit/test_spine.py` — verify 32-point curve over all 32 raw layers (no phase bucketing); verify aggregate order `[mean_grassmannian, spectral_gap, mean_forman_ricci, modularity]`; verify NaN-aware averaging when Ricci slot has NaN entries
- [X] T042 [US1] Implement `src/phi3geom/lattice/spine.py::compute_spine_curve(head_graphs_per_layer)` to pass T041 per spec FR-007; depends on T040 (uses crossbar output)

### Per-regime composite logistic (spectral-only baseline)

- [X] T043 [P] [US1] Write `tests/contract/test_sklearn_logistic.py` — input `(N, F)` float64 with NaN in Ricci column → output coefficients length F + scalar intercept; identical inputs + seed → bit-identical fit; below-100-event input raises `InsufficientDataError`
- [X] T044 [US1] Implement `src/phi3geom/analysis/composite.py::fit_per_regime_composite(features, labels, bin_id, *, l2_penalty, random_state)` per `contracts/composite.md`; passes T043 and T028 (single-bin invariant); uses median imputation for NaN per `research.md §10`

### Pilot reporting and driver

- [X] T045 [US1] Implement `src/phi3geom/reporting/pilot_reports.py` — writes `reports/pilot/per_bin_auroc.json`, `cem_yield.json`, `runtime.json`, `handcheck_sample.jsonl` (50-event sample for spec SC-007); reads from manifest and per-bin composite fits
- [X] T046 [US1] Implement `scripts/run_pilot.sh` and `src/phi3geom/scripts/pilot_main.py` — driver that generates 600 events, runs forward passes, fits per-bin composite, writes pilot reports

### Pilot integration test

- [X] T047 [P] [US1] Write `tests/integration/test_pilot_pipeline.py` — synthesize a 6-event toy dataset (1 per bin), run `pilot_main` end-to-end on a CPU stub of Phi-3 (or skip with `@pytest.mark.gpu` marker for full Phi-3 runs); assert reports written and shape contracts hold

**Checkpoint**: At this point, US1 (Pilot End-to-End Pipeline) should be fully functional. The
researcher can run the pilot on real Phi-3 hardware; pilot acceptance criteria from spec SC-004
can be evaluated. Demonstrable MVP.

---

## Phase 4: User Story 2 - Forman-Ricci Feature Integration (Priority: P2)

**Goal**: Populate the Forman-Ricci-token slot in the atomic-unit feature vector (previously NaN
in US1 baseline), sweep `k_attn ∈ {8, 16, 32}` on a 100-event subset, pin the winning `k_attn`,
and report per-bin marginal AUROC gain from Ricci.

**Independent Test**: Given the US1 pilot dataset and the spectral-only per-bin AUROC, integrate
Forman-Ricci, run the k_attn sweep, re-fit the per-regime composite, and emit
`reports/pilot/per_bin_auroc_with_ricci.json` + `reports/pilot/ricci_marginal_gain.json`. Each
bin shows a marginal-AUROC point estimate and 95% CI. Cost wall-time is within 1.5× of the
~80 GPU-hr full-study projection.

### Ricci integration

- [X] T048 [P] [US2] Write `tests/unit/test_ricci_integration.py` — verify Ricci slot in the F tensor is populated (not NaN) for non-degenerate attention graphs; verify NaN is preserved for isolated-node atomic units; verify `k_attn` parameter flows from caller to graph construction
- [X] T049 [US2] Wire `forman_ricci_token` into `geometry/atomic_unit.py` so the 7th feature is populated when `compute_ricci=True`; default the parameter to `False` so US1's baseline path remains a clean comparison; passes T048

### k_attn sweep

- [X] T050 [P] [US2] Write `tests/unit/test_kattn_sweep.py` — verify sweep harness parameterizes over `k_attn ∈ {8, 16, 32}` on a 12-event toy (2 per bin); verify each sweep value writes its own `per_bin_auroc_k{k}.json`
- [X] T051 [US2] Implement `src/phi3geom/scripts/kattn_sweep.py` — runs the sweep on a 100-event subset of the pilot, writes `reports/pilot/k_attn_sweep.json` with per-bin marginal AUROC gain per `k_attn` value; passes T050 per `research.md §5`

### Ricci marginal-gain reporting

- [X] T052 [P] [US2] Implement `src/phi3geom/reporting/ricci_marginal_gain.py` — given `per_bin_auroc.json` (spectral-only) and `per_bin_auroc_with_ricci.json`, write `ricci_marginal_gain.json` with per-bin `delta_auroc`, 95% CI, and a flag for "marginal gain ≥0.02 in this bin"
- [X] T053 [US2] Update `src/phi3geom/dataset/manifest.py` to record the pinned `k_attn` value after sweep completes; add `--with-ricci` flag to `scripts/run_pilot.sh` so US2 runs are reproducible end-to-end

**Checkpoint**: US2 ready. Ricci-augmented per-regime composite available; `k_attn` pinned for
full-study collection.

---

## Phase 5: User Story 3 - Full-Study Dataset Collection (Priority: P3)

**Goal**: Scale from 600-event pilot to 4800-event full-study dataset (400 fail + 400 control
per bin × 6 bins) with CEM matching, adversariality policies for low-rate bins, S3 replication,
and reproducibility-cross-machine check.

**Independent Test**: Run `scripts/run_full_study.sh`. Verify per-bin 400/400 balance post-CEM,
manifest SHA committed to git, event_ids reproduce from manifest+code on a second machine for
≥99% of events. Spec acceptance scenarios US3.1–US3.3.

### Adversariality policies (FR-016)

- [X] T054 [P] [US3] Write `tests/unit/test_adversariality_policies.py` — for each of the 3 policies (`lexical`, `sibling_entity`, `self_contradiction`), verify distractor injection on a tiny synthetic document; verify the policy name is correctly threaded into the manifest record per event
- [X] T055 [US3] Implement `src/phi3geom/dataset/adversarial.py` with the 3 policies from `research.md §11`; integrate into `dataset/generation.py` so B1 (and possibly B2) can request adversarial injection at generation time

### CEM oversample escalation (FR-015)

- [X] T056 [P] [US3] Write `tests/unit/test_cem_oversample_escalation.py` — verify that <50% yield at 1.5× escalates to 3× automatically; <30% at 3× sets the bin's `is_compromised` flag in `cem_yield.json`; <10% at 3× raises `CEMYieldEscalationError` requiring researcher intervention
- [X] T057 [US3] Extend `src/phi3geom/dataset/matching.py` with oversample escalation logic per FR-015; passes T056

### S3 replication

- [X] T058 [P] [US3] Implement `scripts/replicate_to_s3.sh` — nightly `rsync` of `cache/` and `dataset/` to S3 hot tier; idempotent; logs to `reports/full/replication.log`

### Full-study driver

- [X] T059 [US3] Implement `scripts/run_full_study.sh` and `src/phi3geom/scripts/full_study_main.py` — generates 4800 events with CEM matching, runs all forward passes, populates the cache, fits per-bin composites with the US2 Ricci-augmented atomic unit, writes `reports/full/per_bin_auroc.json`

### Reproducibility cross-machine check (SC-005)

- [X] T060 [P] [US3] Implement `scripts/regenerate_dataset.sh` — given a manifest+code SHA, regenerates the dataset on a second machine and reports the event_id and is_fail agreement rate; targets ≥99% per spec SC-005

### Manifest integrity at scale

- [X] T061 [US3] Add a manifest-verification step at full-study completion (calls `dataset/manifest.py::verify_event_id` over all 4800 events and asserts the manifest_sha256 in `manifest_header.json` matches the recomputed SHA over `manifest.jsonl`); failure halts the full study with a clear error

**Checkpoint**: US3 ready. 4800-event dataset generated, manifest committed to git, S3
replication active, reproducibility verified.

---

## Phase 6: User Story 4 - Per-Regime Composite + β(ℓ) Spine Report (Priority: P4)

**Goal**: Fit the per-regime composite logistic on the full-study dataset and perform FPCA +
functional logistic regression on 32-point spine curves to recover β(ℓ) coefficient functions
per bin. Produce the headline writeup including the pooled-negative-control demonstration.

**Independent Test**: Given the full-study dataset and cached F/D tensors, run
`src/phi3geom/scripts/run_analysis.py`. Verify per-bin AUROC table, β(ℓ) coefficient functions
with 95% CI bands per bin, and pooled-negative-control AUROC <0.75 or CI overlapping 0.50. Spec
acceptance scenarios US4.1–US4.4.

### FPCA (skfda)

- [X] T062 [P] [US4] Write `tests/contract/test_skfda_fpca_shape.py` per `contracts/composite.md` test obligations — `(n_curves, 32)` → `(n_curves, n_fpcs)`; variance-explained monotone decreasing; threshold `0.95` returns `n_fpcs ∈ [2, 8]` on synthetic intrinsic-dim-4 curves
- [X] T063 [US4] Implement `src/phi3geom/analysis/fda.py::fit_fpca(curves, variance_threshold)` wrapping `skfda` per `research.md §3`; passes T062

### Functional logistic regression

- [X] T064 [P] [US4] Write `tests/contract/test_skfda_func_logistic.py` per `contracts/composite.md` — `(N, 32)` curves → β(ℓ) length 32 + CI bands length 32; identical inputs + seed → bit-identical fit; verifies discriminative-depth-interval extraction (intervals where CI excludes 0)
- [X] T065 [US4] Implement `src/phi3geom/analysis/fda.py::fit_functional_logistic(spine_curves, labels, bin_id, edge_type, *, n_fpcs_variance_threshold, random_state)` returning `FunctionalLogisticResult` per `contracts/composite.md`; passes T064 and T028 (single-bin invariant)

### Two-stage FDA → change-detection (long lines)

- [X] T066 [P] [US4] Write `tests/unit/test_changepoint.py` — port DCSBM CUSUM tests; assert detected change-points on synthetic FPCA-score series with planted change; verify EWMA sensitivity-check produces a distinct but qualitatively-similar output
- [X] T067 [US4] Implement `src/phi3geom/analysis/changepoint.py` — `cusum_detect`, `ewma_detect` primitives ported from DCSBM, adapted for FPCA-score input; passes T066 per `research.md §7`

### Pooled negative control (SC-003)

- [X] T068 [P] [US4] Write `tests/unit/test_pooled_negative_control.py` — pooled fit on synthetic 6-bin data with within-bin signal but across-bin noise; assert AUROC <0.75 OR CI overlaps 0.50 (the R2 lesson); verify the output is a `PooledNegativeControl` dataclass not a `PerRegimeCompositeFit`
- [X] T069 [US4] Implement `src/phi3geom/analysis/pooled_negative_control.py::fit(features, labels, *, l2_penalty, random_state)` per `contracts/composite.md`; passes T068 and T028 (segregation)

### Writeup generation

- [X] T070 [US4] Implement `src/phi3geom/reporting/writeup.py` — produces `reports/full/per_bin_auroc.md` (headline table per FR-014), `reports/full/beta_layer_functions/{bin_id}_{edge_type}.json` (β(ℓ) with 95% CI bands), `reports/full/pooled_negative_control.md` (SC-003 evidence), `reports/full/head_graph_comparison.md` (QKᵀ vs AVWO qualitative comparison per spec SC-009)
- [X] T071 [US4] Implement `src/phi3geom/reporting/long_lines.py` — runs the two-stage FDA → CUSUM pipeline on long lines, writes `reports/full/long_lines_cusum.json` (appendix-only output)
- [ ] T072 [US4] Run the end-to-end US4 analysis on the full study via `src/phi3geom/scripts/run_analysis.py`; verify all `reports/full/` artifacts are produced and match the data-model.md schemas

**Checkpoint**: US4 ready. Headline writeup artifacts produced; per-bin AUROC and β(ℓ) results
in publishable form; pooled-negative-control demonstrates the DCSBM-R2 lesson on Phi-3.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final compliance checks, documentation polish, and the empirical validations of
spec success criteria that depend on having all artifacts in hand.

- [X] T073 [P] Add `--help` and `--version` flags to all entrypoints in `src/phi3geom/scripts/`; ensure each script prints its constitution version (1.0.0) and the manifest SHA it consumed
- [ ] T074 [P] Profile end-to-end pilot runtime; if the Forman-Ricci `GraphRicciCurvature` call dominates, replace it with a hand-coded primitive in `src/phi3geom/geometry/ricci.py` and keep `GraphRicciCurvature` as the parity oracle only (per `research.md §4` contingency); re-run T014 to confirm parity holds
- [X] T075 [P] Documentation pass — add docstrings to all public functions in `src/phi3geom/**`; verify `pyproject.toml` long description renders; verify `quickstart.md` references current file paths
- [ ] T076 Run the SC-005 reproducibility cross-machine check on a second machine; record the per-event agreement rate in `reports/full/sc005_reproducibility.json`; if <99%, halt headline interpretation and investigate root cause
- [ ] T077 Run the SC-007 hand-verification on the 50-event handcheck sample; record 100% agreement target outcome in `reports/full/sc007_handcheck.json`; flag any disagreements in the writeup
- [ ] T078 Final writeup interpretation in `reports/full/headline.md` — name discriminative depths per bin per head-graph from T070's β(ℓ) output; flag any bin compromised per FR-015 (CEM yield) or B6-RoPE per FR-017; conclude whether the DCSBM-R2 finding transfers to Phi-3

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories. The Constitution
  Principle II TDD scope is gated here.
- **Phase 3 (US1 Pilot)**: Depends on Phase 2 — MVP. Independent of other user stories.
- **Phase 4 (US2 Forman-Ricci)**: Depends on Phase 3 (uses US1 pilot dataset for sweep comparison)
- **Phase 5 (US3 Full-Study)**: Depends on Phase 4 (uses US2-pinned `k_attn`)
- **Phase 6 (US4 Headline Report)**: Depends on Phase 5 (uses full-study dataset)
- **Phase 7 (Polish)**: Depends on Phase 6

### Critical-path within Phase 2 (Foundational)

- T009 → T010 (seeds: test-then-impl)
- T011, T012 → T013 (spectral: parallel tests, then impl)
- T014 → T015 (ricci: test-then-impl)
- T016 → T017 (normalization: test-then-impl)
- T018 → T019 (distance: test-then-impl)
- T020 → T021 (matching: test-then-impl)
- T022 → T023 (manifest: test-then-impl). T023 depends on T010 (uses `seeds.py`).
- T024 → T025 (cache: test-then-impl)
- T026 → T027 (hooks: test-then-impl)
- T028 → T029 (segregation: test-then-impl skeleton)
- T030 — depends on T029 having declared the scripts

### Within-story dependencies

US1: T031→T032, T033→T034, T035→T036 (uses T013, T015, T025, T027), T037→T038 (uses T013, T015),
T039→T040 (uses T013), T041→T042 (uses T040), T043→T044 (uses T029 + T010), T045 (uses T044),
T046 (uses everything above), T047 (uses T046).

US2: T048→T049 (uses T015, T038), T050→T051 (uses T046), T052 (uses T044 + T051), T053 (uses
T051 output).

US3: T054→T055 (uses T034), T056→T057 (uses T021), T058 standalone, T059 (uses T055, T057, T034,
T036, T044, T049), T060 (uses T023, T034), T061 (uses T023).

US4: T062→T063, T064→T065 (uses T063), T066→T067, T068→T069 (uses T029, T044's regularization
machinery), T070 (uses T044, T065, T069), T071 (uses T063, T067), T072 (driver, uses all of
T063+T065+T067+T069+T070+T071).

### Parallel Opportunities

- **Setup**: T003, T004, T005, T006, T007 all `[P]` — can run in parallel after T001/T002
- **Foundational**: all test-writing tasks (T009 odd-numbered through T028 even-numbered) run in
  parallel — different files. Implementations T010, T013, T015, T017, T019, T021, T023, T025,
  T027, T029 can ALSO run in parallel (different files); each just needs its corresponding test
  written first. So Phase 2 can complete in roughly 2 swimlane-passes.
- **US1**: T031, T033, T035, T037, T039, T041, T043, T047 all `[P]` (different test files);
  implementation tasks T032, T034, T036, T038, T040, T042, T044, T045 can run after their tests
  in parallel except T042 (waits on T040) and T036 (uses many Phase 2 outputs).
- **US2**: T048, T050, T052 all `[P]`
- **US3**: T054, T056, T058, T060 all `[P]`
- **US4**: T062, T064, T066, T068 all `[P]`
- **Polish**: T073, T074, T075 all `[P]`

### Parallel Example: Phase 2 (Foundational) test-writing swimlane

```bash
# All ten test files can be authored simultaneously:
Task: "Write tests/unit/test_seeds.py"                     # T009
Task: "Write tests/unit/test_spectral_parity.py"           # T011
Task: "Write tests/unit/test_spectral_individual.py"       # T012
Task: "Write tests/unit/test_ricci_parity.py"              # T014
Task: "Write tests/unit/test_normalization.py"             # T016
Task: "Write tests/unit/test_evidence_distance.py"         # T018
Task: "Write tests/unit/test_matching.py"                  # T020
Task: "Write tests/unit/test_manifest.py"                  # T022
Task: "Write tests/unit/test_cache.py"                     # T024
Task: "Write tests/unit/test_hooks.py"                     # T026
Task: "Write tests/unit/test_principle_iii_segregation.py" # T028
```

### Parallel Example: User Story 1 test-writing

```bash
Task: "Write tests/unit/test_pin_model_revision.py"        # T031
Task: "Write tests/unit/test_generation.py"                # T033
Task: "Write tests/contract/test_event_alignment.py"       # T035
Task: "Write tests/unit/test_atomic_unit_assembly.py"      # T037
Task: "Write tests/unit/test_crossbar.py"                  # T039
Task: "Write tests/unit/test_spine.py"                     # T041
Task: "Write tests/contract/test_sklearn_logistic.py"      # T043
Task: "Write tests/integration/test_pilot_pipeline.py"     # T047
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T008)
2. Complete Phase 2: Foundational (T009–T030) — CRITICAL; gates Constitution Principle II
3. Complete Phase 3: US1 Pilot (T031–T047)
4. **STOP and VALIDATE**: Run `scripts/run_pilot.sh` on real Phi-3 hardware. Confirm SC-004
   acceptance: ≤72 GPU-hours, ≥5 of 6 bins ≥50% CEM yield, 100% hand-verification agreement,
   no B6 RoPE-wrap discontinuity. This IS the MVP.
5. Decision point: if pilot fails SC-004, halt and re-spec before US2.

### Incremental Delivery

1. Setup + Foundational → Foundation ready (constitution-compliant primitives proven by tests)
2. + US1 → Pilot MVP demonstrable, headline-question answerable at small scale
3. + US2 → Forman-Ricci integrated, `k_attn` pinned, Ricci marginal gain measured
4. + US3 → 4800-event dataset committed to git, full-study cache populated
5. + US4 → Headline writeup artifacts produced (per-bin AUROC, β(ℓ), pooled negative control)
6. + Polish → SC-005 and SC-007 validated empirically; v1 closed

### Solo-Developer Strategy (Constitution: solo cadence, multi-day increments)

Single developer; sequential by phase except for the within-phase parallel-test-writing
swimlanes called out above. The constitution's TDD discipline is the productivity rate limiter,
not parallel coordination overhead. Expected calendar time: ~4 weeks for Phases 1–3 (the
critical risk-burn-down period), ~2 weeks each for Phases 4–6, ~1 week for Phase 7. Total: ~10
weeks elapsed, well within the multi-day solo cadence the spec assumes.

---

## Notes

- `[P]` tasks = different files, no dependencies on incomplete tasks
- `[Story]` label maps task to spec.md user story (US1/US2/US3/US4)
- Every test task is followed by exactly one implementation task per the TDD discipline
- The Constitution Principle II TDD scope is enforced by Phase 2 — implementation cannot proceed
  until parity tests pass
- The Constitution Principle III segregation is enforced by T028, kept alive by T070 and the
  module structure (composite.py vs pooled_negative_control.py)
- Constitution Principle IV float64-in-the-seam is enforced by `contracts/atomic_unit.md` which
  the implementation in T013/T015 honors
- Constitution Principle V is enforced by THIS workflow — any deviation goes through `/speckit-specify`
- Stop at the US1 checkpoint and validate the pilot on real Phi-3 hardware before scaling
- Commit after each task or logical group; the `after_*` git hooks in `.specify/extensions.yml`
  offer auto-commit but are optional
