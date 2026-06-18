---
description: "Task list for SP-0 — Multi-Model Geometry Extraction Substrate"
---

# Tasks: SP-0 — Multi-Model Geometry Extraction Substrate

**Input**: Design documents from `specs/002-sp0-extraction-substrate/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: **INCLUDED** — Constitution Principle II (NON-NEGOTIABLE within scope) mandates
test-first for the scientific primitives here: capture hooks + GQA expansion, in-pass
MP fit, labeling/abstention, manifest-completeness, storage integrity + the data-loss
regression, harness interfaces. Write each test FIRST and confirm it FAILS before
implementing.

**Constitution gate**: v3.0.0 ratified (2026-06-17) — `/speckit-implement` is unblocked.

**Organization**: by user story (US1–US6 from spec.md), priority order. The DAG note: this
is SP-0; SP-1/SP-2/SP-3 are out of scope (US5 ships only their *interfaces*).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no incomplete-task dependency)
- **[Story]**: US1–US6; Setup/Foundational/Polish carry no story label
- Paths are repo-relative; single-project layout under `src/phi3geom` + `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Tighten `transformers` to a single pinned version ≥4.48 (e.g. `==4.53.*`) and add `datasets`/RULER-generator deps in `pyproject.toml` (research.md R1.6 — do not span the 4.48 refactor)
- [X] T002 [P] Create package skeletons with `__init__.py`: `src/phi3geom/extraction/adapters/`, `src/phi3geom/dataset/adapters/`, `src/phi3geom/analysis/harness/`
- [ ] T003 [P] Extend roster revision pinning in `src/phi3geom/scripts/pin_model_revision.py` to record each roster model's HF revision SHA into the manifest (Constitution I, multi-model)

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user-story work begins until this phase is complete.

### Tests (write first, must fail)

- [X] T004 [P] Test: storage `capture_version` + manifest-SHA round-trip and `CacheStaleError` on mismatch in `tests/contract/test_cache_storage.py` (contracts/cache-storage.md)
- [X] T005 [P] Test: GQA expansion helper — query head `q` → KV head `q // n_rep`, analytic on synthetic head counts, in `tests/unit/test_gqa_expansion.py` (research.md R1.2)

### Implementation

- [X] T006 Create `ModelDescriptor` + config-driven metadata reader (d_model/n_layers/n_heads/n_kv_heads/head_dim/n_rep/attention_profile/tied_embeddings — **read from config, never computed**) in `src/phi3geom/extraction/adapters/base.py` (data-model.md)
- [~] T007 Define the `ModelAdapter` protocol + GQA/MQA expansion helper + capture-config (eager, `output_attentions`/`output_hidden_states`, `use_cache=False`) in `src/phi3geom/extraction/adapters/base.py` (depends T006; research.md R1.1/R1.2) — **PARTIAL**: `ModelAdapter` Protocol (with the SP-3 `intervention` surface) + GQA expansion helper done & tested (T005); the live `from_pretrained` capture-config helper pends a torch/model env (GPU pod)
- [X] T008 [P] Extend the common event record (`is_answerable`, `gold_aliases`, `evidence_spans`, `corpus_id`, `provenance`) in `src/phi3geom/dataset/types.py` (data-model.md DocQAEventRecord)
- [X] T009 Extend the cache for `capture_version` + `CaptureBundle` write/read + header, raising on `capture_version`/`manifest_sha` mismatch, in `src/phi3geom/storage/cache.py` (depends T004; contracts/cache-storage.md)
- [X] T010 Create the `CaptureManifest` metric→field mapping + completeness-check skeleton in `src/phi3geom/extraction/capture.py` (manifest) and `src/phi3geom/scripts/check_manifest_completeness.py` (contracts/capture-manifest.md)

**Checkpoint**: substrate scaffolding ready — user stories can begin.

---

## Phase 3: User Story 1 — Capture-once substrate, one model + corpus (Priority: P1) 🎯 MVP

**Goal**: One forward pass on Phi-3 over HotpotQA records the complete raw bundle; an
offline consumer computes a geometry scalar AND a baseline scalar with zero GPU/model reload.

**Independent Test**: Capture Phi-3 × HotpotQA at small N; an offline script computes
residual-trajectory length and answer-token entropy per event with no model load.

### Tests (write first, must fail)

- [ ] T011 [P] [US1] Test: Phi-3 capture round-trip — recovered per-head Q/K/V + attention shapes match the model's own forward, in `tests/unit/test_capture_roundtrip_phi3.py` (research.md R1.4)
- [X] T012 [P] [US1] Test: in-pass MP fit vs closed-form bulk edge on a known-aspect-ratio Gaussian (float64), in `tests/unit/test_mp_fit_analytic.py` (Constitution II/IV)
- [X] T013 [P] [US1] Test: manifest completeness for the US1-implemented fields, in `tests/contract/test_manifest_completeness.py` (SC-001)
- [ ] T014 [P] [US1] Integration: capture one HotpotQA event on Phi-3 → bundle → offline consumer returns 1 geometry + 1 baseline scalar, zero model reload, in `tests/integration/test_capture_offline_consumer.py` (SC-002)
- [ ] T014a [P] [US1] Contract test: the rich-capture pass exposes a reusable **intervention-callback surface** (accepts an optional per-layer hook) so SP-3 can re-invoke it with interventions — SP-0 ships the surface, not the interventions — in `tests/contract/test_intervention_surface.py` (FR-026; remediation C3)

### Implementation

- [ ] T015 [US1] Implement the Phi-3 `ModelAdapter` (fused `qkv_proj` contiguous slicing, MHA `n_rep=1`, `o_proj` slice, hidden-state + unembed capture) in `src/phi3geom/extraction/adapters/phi3.py` (research.md R1.4/R1.5)
- [~] T016 [US1] Implement the in-pass per-layer token-cloud eigen-spectrum + MP fit (**float64**, store only the reduction) in `src/phi3geom/extraction/capture.py` (depends T012; contracts/capture-manifest.md in-pass rule) — **PARTIAL**: the MP reduction primitive (`marchenko_pastur_edges`/`covariance_eigenvalues`/`token_cloud_spectrum`) is done & analytically tested in `src/phi3geom/geometry/spectral.py` (T012 green); wiring it into the live capture pass pends the GPU pod
- [ ] T017 [US1] Implement the rich-capture pass in `src/phi3geom/extraction/capture.py`: eager forward, **layer-by-layer attention CPU offload**, assemble `CaptureBundle` (hidden@answer-pos + window, attn rows, `T×T` subset S, spectra, answer logits) and write via the cache; expose an **optional per-layer intervention callback** as the reusable SP-3 surface (depends T007, T009, T015, T016; research.md R1.1; FR-026/C3)
- [ ] T018 [US1] Implement K+1 generation (greedy T=0 scored + K=10 samples T=1.0/top-p 0.9, per-sample seeds) and `GenerationSample` storage (text/token_ids/chosen-token logprobs/seq logprob/length/greedy-flag) in `src/phi3geom/extraction/capture.py` (research.md R3.1)
- [ ] T019 [US1] Implement the HotpotQA adapter → common record + evidence spans from gold supporting sentences in `src/phi3geom/dataset/adapters/hotpotqa.py` (contracts/corpus-adapter.md)
- [X] T020 [US1] Implement minimal `normalize_answer` + alias-EM correctness → `Label` (greedy sample) in `src/phi3geom/dataset/labeling.py` (full 4-way deferred to US3; research.md R3.2)
- [ ] T021 [US1] Wire a single-`(model, corpus, event)` capture entrypoint (re-point `src/phi3geom/extraction/pipeline.py` at `capture.py`; keep the v1 path for provenance)
- [ ] T022 [US1] Confirm `check_manifest_completeness` passes for the US1 metric subset and the offline consumer demo runs (depends T010, T017)

**Checkpoint**: MVP — Phi-3 × HotpotQA capture-once works and is consumable offline.

---

## Phase 4: User Story 2 — Model-agnostic capture across architectures (Priority: P2)

**Goal**: The substrate captures correctly across roster architectures (GQA expansion;
Gemma-2 sliding-window/softcap), with per-model metadata enabling cross-model comparison.

**Independent Test**: Round-trip on ≥3 architectures incl. ≥1 GQA model and Gemma-2;
grouped-KV expansion yields one K/V per query head; effective attention support recorded.

### Tests (write first, must fail)

- [ ] T023 [P] [US2] Test: round-trip **parametrized over ALL GQA adapters** (Llama-3, Qwen2.5, Mistral — distinct `head_dim`/tied-embedding configs) — each query head paired with KV head `q // n_rep`, in `tests/unit/test_capture_roundtrip_gqa.py` (research.md R1.2; SC-003 "≥5 architectures round-trip verified" — remediation C2)
- [ ] T024 [P] [US2] Test: Gemma-2 capture records per-layer effective support (sliding vs full) + softcap params, in `tests/unit/test_gemma2_capture.py` (research.md R1.3)

### Implementation

- [ ] T025 [P] [US2] Implement the Llama-3 adapter (split q/k/v_proj, GQA, RoPE timing) in `src/phi3geom/extraction/adapters/llama.py`
- [ ] T026 [P] [US2] Implement the Qwen2.5 adapter (GQA, explicit `head_dim`, tied embeddings for 0.5/1.5B) in `src/phi3geom/extraction/adapters/qwen2.py`
- [ ] T027 [P] [US2] Implement the Mistral adapter (GQA) in `src/phi3geom/extraction/adapters/mistral.py`
- [ ] T028 [US2] Implement the Gemma-2 adapter — `layer_types` (even=full/odd=sliding), `query_pre_attn_scalar`, both softcaps, per-layer effective support — in `src/phi3geom/extraction/adapters/gemma2.py` (research.md R1.3)
- [ ] T029 [US2] Implement an adapter registry that resolves the right `ModelAdapter` from the model config in `src/phi3geom/extraction/adapters/base.py`
- [ ] T030 [US2] Persist per-model "once" artifacts (`lm_head.weight`, final-norm, `ModelDescriptor`) under `models/<model_id>/` and reference from every bundle (contracts/cache-storage.md)

**Checkpoint**: US1 + US2 — capture works across the diverse roster.

---

## Phase 5: User Story 3 — Trustworthy hallucination labels across regimes (Priority: P2)

**Goal**: Every event carries a 4-way class + hallucination-vs-safe binary, computed
consistently across answerable/unanswerable, with a validated abstention detector.

**Independent Test**: On a hand-labeled sample, the 4-way truth table is applied correctly
and the abstention detector meets its P/R target (≥0.90).

### Tests (write first, must fail)

- [X] T031 [P] [US3] Test: 4-way truth-table fixtures `(is_answerable, em_match, abstained) → class_4way` in `tests/unit/test_labeling_truthtable.py` (data-model.md Label)
- [X] T032 [P] [US3] Test: abstention detector precision/recall on a hand-labeled fixture (target ≥0.90/≥0.90) in `tests/unit/test_abstention_validation.py` (SC-004) — hand-labeled sample + `precision_recall`; rules are high-precision/under-recall, the rules+backstop design clears ≥0.90/≥0.90 (backstop is a stub for SP-1's real NLI/judge)

### Implementation

- [X] T033 [US3] Extend `normalize_answer` + alias-EM max-over-references + SQuAD-style token-F1 cross-check in `src/phi3geom/dataset/labeling.py` (research.md R3.2)
- [X] T034 [US3] Implement the abstention detector — high-precision rule pre-filter + classifier/NLI/judge backstop interface — in `src/phi3geom/dataset/abstention.py`
- [X] T035 [US3] Implement the 4-way classifier + hallucination-vs-safe binary in `src/phi3geom/dataset/labeling.py` (depends T033, T034)
- [ ] T036 [US3] Build the hand-labeled validation sample (answerable + unanswerable) and emit the abstention P/R report in `reports/sp0/abstention_validation.json`

**Checkpoint**: US1–US3 — labeled, model-agnostic capture.

---

## Phase 6: User Story 4 — Corpus coverage across the four regimes (Priority: P2)

**Goal**: Adapters present all four regimes through one common record; each corpus
sampled toward a balanced fail/hallucination rate.

**Independent Test**: Each adapter yields the common record with correct fields (empty
document for closed-book; spans where available); a sampled batch lands in 25–75% balance.

### Tests (write first, must fail)

- [ ] T037 [P] [US4] Test: each adapter emits a valid common record incl. closed-book no-document + span-within-prompt validation, in `tests/contract/test_corpus_adapters.py` (contracts/corpus-adapter.md)

### Implementation

- [ ] T038 [P] [US4] Implement the SQuAD2 adapter (answerable + unanswerable; `is_answerable=False` ⇒ `gold_aliases=[]`) in `src/phi3geom/dataset/adapters/squad2.py`
- [ ] T039 [P] [US4] Implement the closed-book TriviaQA/NQ adapter (`document=""`, alias sets, `evidence_spans=null`) in `src/phi3geom/dataset/adapters/triviaqa_nq.py`
- [ ] T040 [US4] Implement the RULER adapter — pass the model tokenizer, carry native `token_position_answer` → `evidence_spans`, lengths {4K,8K,16K,32K} — in `src/phi3geom/dataset/adapters/ruler.py` (research.md R2; verify the `qa`-task position field)
- [ ] T041 [US4] (Optional/secondary) Implement the NoLiMa adapter in `src/phi3geom/dataset/adapters/nolima.py` — **gate on confirming the Adobe non-commercial license** (research.md R2 to-do)
- [X] T042 [US4] Implement balance sampling toward the 25–75% fail/hallucination band per corpus (no synthetic distractor inflation) in `src/phi3geom/dataset/balance.py` (SC-005) — balance_corpus/balance_dataset (downsample-only, no synthetic inflation; v1 oversample.py left intact)

**Checkpoint**: US1–US4 — all four regimes flowing through one capture path.

---

## Phase 7: User Story 5 — Evaluation-harness interfaces (Priority: P3)

**Goal**: Ship the frozen-cache loader + null-evidence pack + incremental-over-baseline +
transfer splitters + redundancy utility — the contracts SP-1/SP-2/SP-3 consume. Interfaces
only, with trivial reference assemblers for testing.

**Independent Test**: A stub consumer registers a trivial assembler, loads the frozen cache,
and obtains pooled AUROC + null-evidence + a cross-corpus split — without re-running extraction.

### Tests (write first, must fail)

- [X] T043 [P] [US5] Integration: stub consumer loads frozen cache → pooled AUROC + null-evidence pack + one cross-corpus split, zero re-extraction, in `tests/integration/test_harness_stub.py` (spec US5; contracts/harness-interface.md)

### Implementation

- [X] T044 [P] [US5] Implement the frozen-cache loader + pluggable arbitrary-width feature assembler (`HarnessDataset`) in `src/phi3geom/analysis/harness/loader.py`
- [X] T045 [P] [US5] Implement the feature-width-generic null-evidence pack (repeated CV AUROC, permutation p, Cohen's d, split-luck) in `src/phi3geom/analysis/harness/null_evidence.py` (generalize off the v1 7-feature hardcode)
- [X] T046 [US5] Implement incremental-AUROC-over-baseline (nested logistic / DeLong) in `src/phi3geom/analysis/harness/incremental.py`
- [X] T047 [P] [US5] Implement cross-corpus + cross-model transfer splitters (`group`-aware, scalar-feature level) in `src/phi3geom/analysis/harness/transfer.py`
- [X] T048 [US5] Implement the redundancy / partial-correlation utility in `src/phi3geom/analysis/harness/redundancy.py`

**Checkpoint**: US1–US5 — frozen cache is consumable as a pure offline sweep.

---

## Phase 8: User Story 6 — Benchmark gate, pilot & durable persistence (Priority: P3)

**Goal**: Measure per-event cost before any full run; validate the whole path end-to-end;
guarantee no data loss on interruption.

**Independent Test**: Benchmark emits time/mem/disk per `(model, context)`; pilot runs
≥2 architectures × all corpora at small N without OOM; a simulated interruption + resume
restores 100% of committed events.

### Tests (write first, must fail)

- [ ] T049 [P] [US6] Test: data-loss regression — captured bundles are not dropped by storage-ignore rules (reproduces the v1 `fe190b7` defect), in `tests/contract/test_data_loss_regression.py` (FR-018, SC-007)
- [~] T050 [P] [US6] Test: resilient resume restores 100% of previously-committed events and recomputes none, in `tests/integration/test_resume.py` (FR-019, SC-007) — **PARTIAL**: bundle-level resume scan (storage/resume.py: list_complete/incomplete_events) + test done; the driver/git-branch restore pends the pod
- [X] T050a [P] [US6] Test: adding one new model + one new corpus leaves every existing event bundle **byte-for-byte unchanged** (zero re-extraction), in `tests/contract/test_zero_reextraction.py` (FR-020, SC-006; remediation C1)

### Implementation

- [ ] T051 [US6] Implement `benchmark_gate.py` — per-`(model, context_bucket)` time/peak-mem/disk under full rich capture → derive `chosen_N`, layer subset `S`, `longctx_N` — in `src/phi3geom/scripts/benchmark_gate.py` (SC-008; watch `nvidia-smi`)
- [ ] T052 [US6] Implement resilient resume that reads what was actually persisted (fix the v1 `restore_from_branch` committed-vs-scheduled gap) in `src/phi3geom/storage/cache.py` / `src/phi3geom/checkpointing.py` (depends T049, T050)
- [ ] T053 [US6] Maintain durable persistence (anchored ignores + force-add) so bundles are never silently dropped (keep the `fe190b7` regression green)
- [ ] T054 [US6] Implement the multi-model pilot driver `run_pilot_v2.py` (≥2 architectures × all corpora × small N) in `src/phi3geom/scripts/run_pilot_v2.py` (SC-009)
- [ ] T055 [US6] Emit the pilot report (per-corpus fail/hallucination balance, abstention P/R, `oom_skips=0`, archs validated) to `reports/sp0/pilot.json`

**Checkpoint**: US1–US6 — gated, validated, durable substrate.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T056 [P] Run `check_manifest_completeness` against the FULL program-catalog §5 (100% coverage gate) before the first-allocation run (SC-001)
- [ ] T057 [P] Validate `quickstart.md` end-to-end (gate → pilot → capture → verify → hand off)
- [ ] T058 [P] Document the SEP synergy (store greedy hidden states → SP-2 trains a semantic-entropy probe) and the two RULER/NoLiMa verification to-dos in `specs/002-sp0-extraction-substrate/research.md`
- [ ] T059 Run the full `pytest` suite green; confirm float64-seam + no-data-loss + manifest-completeness all pass

---

## Phase 10: §5.6 inter-head attention-drift surface (amendment 2026-06-18)

**Design**: `docs/superpowers/specs/2026-06-18-interhead-attention-drift-family-design.md`
(FR-027/028, SC-011). The per-cell summary primitives are CPU-validatable now; the in-pass
GPU wiring and the constitution touch are pod-/gate-bound.

### Tests (write first, must fail)

- [X] T060 [P] Test: inter-head dispersion (JS/Hellinger) + overlap-matrix spectrum (effective rank / Fiedler / top-eig) analytic properties — e.g. identical heads ⇒ dispersion 0 / rank-1 overlap; orthogonal-support heads ⇒ max dispersion — in `tests/unit/test_interhead.py` (Constitution II/IV)

### Implementation

- [X] T061 [P] Implement the per-cell `S(t,ℓ)` summary primitives (pairwise JS/Hellinger dispersion; head-head overlap matrix + effective rank / Fiedler gap / top eigenvalue; evidence-coverage) in `src/phi3geom/geometry/interhead.py` (**float64**; CPU)
- [X] T062 Add the §5.6 metrics + `interhead_drift_surface` bundle field to `src/phi3geom/extraction/manifest.py` and update the completeness test (`tests/contract/test_manifest_completeness.py`) to cover them (SC-011)
- [ ] T063 **[pod]** Wire the in-pass `S(t,ℓ)` computation over the log-spaced query grid × all layers into `src/phi3geom/extraction/capture.py` (off the eager attention tensor; store the surface, never raw `H×T`) — depends T061, T062
- [ ] T064 **[gate]** Constitution **v3.1.0** touch via `/speckit-constitution` — extend Principle II TDD scope to the inter-head dispersion / overlap-matrix primitives and record the §5.6 family — MUST land before T063 (the capture-wiring commit; Principle V)

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)** → no deps.
- **Foundational (P2)** → after Setup; **BLOCKS all user stories**.
- **US1 (P3, MVP)** → after Foundational.
- **US2/US3/US4 (P2 stories)** → after Foundational; each independently testable. US2 extends US1's capture path; US3/US4 are largely independent (US3 labeling, US4 adapters) but both consume the US1 capture for end-to-end runs.
- **US5 (P3)** → after Foundational; consumes a frozen cache (any US1+ output), independent of US3/US4 internals.
- **US6 (P3)** → after Foundational; the pilot exercises US1–US4 end-to-end, so most valuable after them.
- **Polish (P9)** → after the desired stories.

### Critical path to MVP

Setup → Foundational → US1 (T001→T010→T011–T022).

### Within each story

- Tests FIRST and FAILING (Constitution II) → adapters/models → capture/services → wiring.

### Parallel opportunities

- Setup: T002, T003 in parallel.
- Foundational tests T004, T005 in parallel; impl T008 ∥ (T006→T007) ∥ (T009 after T004).
- US1 tests T011–T014 in parallel.
- US2 adapters T025, T026, T027 in parallel (different files); T028 (Gemma-2) after the registry shape is set.
- US4 adapters T038, T039 in parallel; T040 after.
- US5 T044, T045, T047 in parallel.

---

## Parallel Example: User Story 2

```bash
# Adapters are independent files — implement together after the registry contract (T029) is drafted:
Task: "Implement the Llama-3 adapter in src/phi3geom/extraction/adapters/llama.py"
Task: "Implement the Qwen2.5 adapter in src/phi3geom/extraction/adapters/qwen2.py"
Task: "Implement the Mistral adapter in src/phi3geom/extraction/adapters/mistral.py"
```

---

## Implementation Strategy

### MVP first (US1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (CRITICAL) → 3. Phase 3 US1 → **STOP & VALIDATE**:
   Phi-3 × HotpotQA capture-once consumable offline (SC-002). This alone is a usable
   single-model substrate.

### Incremental delivery

US1 (MVP) → US2 (roster generality) → US3 (labels) → US4 (corpora) → US5 (harness) →
US6 (gate + pilot + durability) → Polish. Each adds value without breaking the prior.

### First-allocation run (post-US6, gated)

Benchmark gate → multi-model pilot → 6-checkpoint × 3-short-corpora full-N capture +
reduced-N RULER probe → completeness check → hand off the frozen cache to SP-1/SP-2.

---

## Notes

- [P] = different files, no incomplete-task dependency.
- Constitution II: verify every primitive test FAILS before implementing.
- The constitution v3.0.0 gate is satisfied; no methodology change remains unratified.
- SP-1 (baselines), SP-2 (geometry metrics), SP-3 (interventions) are **out of scope** —
  US5 ships only their interfaces and the SP-3 capture surface.
- Commit after each task or logical group; leave the unrelated untracked
  `scripts/confound_audit_extended.py` alone.
- **Post-`/speckit-analyze` remediation**: C1 → T050a (zero-re-extraction test),
  C2 → T023 broadened to all GQA adapters, C3 → T014a + T017 intervention surface.
  62 tasks total after remediation.
