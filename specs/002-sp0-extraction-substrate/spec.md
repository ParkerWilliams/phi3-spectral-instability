# Feature Specification: SP-0 — Multi-Model Geometry Extraction Substrate

**Feature Branch**: `002-sp0-extraction-substrate`

**Created**: 2026-06-17

**Status**: Draft

**Input**: User description: "SP-0: multi-model attention/representation-geometry extraction substrate for the v2 correctness-geometry program."

**Governing design**: `docs/superpowers/specs/2026-06-17-sp0-extraction-substrate-design.md`
(parent program: `docs/superpowers/specs/2026-06-17-v2-correctness-geometry-program-design.md`).

---

## User Scenarios & Testing *(mandatory)*

SP-0 is research infrastructure. Its "users" are the research team running
extraction and the three downstream sub-projects that consume its output: SP-1
(baseline ceiling), SP-2 (observational metric sweep), SP-3 (causal interventions).
The central value is **capture-once**: pay the GPU cost a single time per
`(model, corpus, event)`, then let every metric be an offline CPU sweep and let
later compute allocations add data with **zero re-extraction**.

### User Story 1 - Capture-once substrate, one model and corpus (Priority: P1)

A researcher runs the substrate on a single model over a single answerable corpus.
In one forward pass per event, the substrate records the complete raw material the
program's metric catalog needs, stores it under a documented schema, attaches a
correctness label, and frees the model. A downstream consumer then computes a
geometry scalar **and** a confidence-baseline scalar for every event **without
reloading the model or touching a GPU**.

**Why this priority**: This is the architectural thesis and the MVP. If only this
exists, the extraction substrate already delivers value for one model — and it is
the slice that proves the capture manifest is complete enough that downstream work
is offline.

**Independent Test**: Run capture on Phi-3-mini over HotpotQA at small N; confirm
each event's stored bundle lets an offline script compute (a) one geometry scalar
(e.g., residual-trajectory length) and (b) one baseline scalar (e.g., answer-token
entropy) with no model load and no GPU.

**Acceptance Scenarios**:

1. **Given** a loaded model and a labeled answerable event, **When** capture runs,
   **Then** the stored bundle contains every raw tensor required by the program
   metric catalog (per-layer hidden states at the answer position + window;
   answer-position attention rows; full attention for the configured layer subset;
   in-pass per-layer token-cloud spectra + Marchenko–Pastur-fit stats; gold-evidence
   spans; sampled answers + logprobs; answer-token logits; per-model metadata).
2. **Given** a frozen cache produced by capture, **When** an offline consumer reads
   one event, **Then** it computes at least one geometry scalar and one baseline
   scalar with zero GPU use and zero model reload.
3. **Given** an event whose prompt is too short to populate the lookback window,
   **When** capture runs, **Then** the event is skipped or flagged explicitly (never
   silently mis-stored).

---

### User Story 2 - Model-agnostic capture across architectures (Priority: P2)

The substrate captures correctly across the roster's distinct architectures, not
just Phi-3. It resolves Q/K/V, attention weights, the output projection, and
per-layer hidden states from each model's own structure, expands grouped KV heads
(GQA/MQA) to per-query-head before forming per-head operators, and records the
effective attention support for models whose layers do not all attend globally.

**Why this priority**: The whole "model-agnostic hallucination geometry" claim
depends on the substrate working across families. Without it the program collapses
to a single-model study.

**Independent Test**: Run capture on ≥3 architectures including ≥1 grouped-KV model
(Llama-3 / Qwen2.5 / Mistral) and Gemma-2; verify recovered per-head Q/K/V and
attention shapes match each model's own forward pass (round-trip), and that
grouped-KV expansion yields one key/value per query head.

**Acceptance Scenarios**:

1. **Given** a grouped-KV model, **When** per-head operators are formed, **Then**
   each query head is paired with its correctly expanded key/value head.
2. **Given** a model with non-global attention in some layers (sliding window),
   **When** capture runs, **Then** the stored record marks each layer's effective
   attention support so routing metrics are never computed against a mask the model
   never used.
3. **Given** any roster model, **When** its bundle is written, **Then** per-model
   metadata (`d_model`, `n_layers`, `n_heads`, `d_head`, tokenizer id, pinned
   revision) is stored alongside it.

---

### User Story 3 - Trustworthy hallucination labels across regimes (Priority: P2)

Every captured event carries a four-way class (correct-answer, wrong-answer,
correct-abstention, hallucination) and the derived hallucination-vs-safe headline
binary, computed consistently whether the item is answerable or unanswerable and
whether the gold answer has one form or many aliases.

**Why this priority**: The cache is supervised-useless without trustworthy labels,
and the unanswerable split is the program's clean hallucination testbed.

**Independent Test**: On a hand-labeled validation sample spanning answerable and
unanswerable items, confirm the four-way truth table is applied correctly and the
abstention detector meets its precision/recall target.

**Acceptance Scenarios**:

1. **Given** an answerable event whose normalized output matches any gold alias,
   **When** labeling runs, **Then** it is `correct-answer` (safe); on mismatch
   (including a wrongful abstention) it is `wrong-answer` (positive).
2. **Given** an unanswerable event, **When** the model abstains, **Then** it is
   `correct-abstention` (safe); when it asserts an answer, it is `hallucination`
   (positive).
3. **Given** the validation sample, **When** the abstention detector is scored,
   **Then** its precision and recall each meet the target (see SC-004), and a
   token-overlap robustness check is reported alongside exact-match labeling.

---

### User Story 4 - Corpus coverage across the four regimes (Priority: P2)

Adapters present HotpotQA, SQuAD2 (answerable + unanswerable), closed-book
TriviaQA/NQ (no document), and a long-context benchmark to the substrate through one
common event record, so the same capture path serves every regime. Each corpus is
sampled toward a balanced fail/hallucination rate.

**Why this priority**: Cross-corpus transfer is a headline test; it requires all
regimes flowing through one record shape. Long-context is reduced-N in the first
allocation.

**Independent Test**: Each adapter yields the common record with the right fields
populated (empty document for closed-book; evidence spans present where the corpus
provides them); a sampled batch from each corpus lands in the target balance band.

**Acceptance Scenarios**:

1. **Given** any of the four corpora, **When** its adapter runs, **Then** it emits
   the common record with `is_answerable`, gold alias set, evidence spans (when
   available), and corpus id populated.
2. **Given** the closed-book corpus, **When** an event is built, **Then** the
   document is empty and routing-dependent fields are marked not-applicable rather
   than fabricated.
3. **Given** a sampled batch per corpus, **When** labels are tallied, **Then** the
   fail/hallucination rate falls in the healthy band (SC-005).

---

### User Story 5 - Evaluation-harness interfaces for downstream sub-projects (Priority: P3)

SP-0 ships the *interfaces* the later sub-projects build on: a frozen-cache loader
that returns, per event, the labeled target plus a pluggable feature assembler; the
null-evidence evaluation pack generalized to any feature width; an
incremental-over-baseline comparison; cross-corpus and cross-model transfer
splitters; and a redundancy/partial-correlation utility. It ships these contracts,
not the metrics that fill them.

**Why this priority**: It is the consumer contract that lets SP-1/SP-2 run as pure
offline sweeps; valuable but only after capture, labels, and corpora exist.

**Independent Test**: A stub downstream consumer registers a trivial feature
assembler, loads the frozen cache through the interface, and obtains a pooled AUROC
with the full null-evidence pack and a cross-corpus transfer split — without
re-running extraction.

**Acceptance Scenarios**:

1. **Given** a frozen cache, **When** a consumer requests events through the loader,
   **Then** it receives the four-way/binary target and can plug in an arbitrary
   feature assembler of any width (no hard-coded feature count).
2. **Given** a feature matrix and labels, **When** the evaluation pack runs, **Then**
   it returns repeated-CV AUROC, a permutation p-value, Cohen's d, the split-luck
   distribution, and an incremental-over-baseline comparison.
3. **Given** events tagged by corpus and model, **When** a transfer split is
   requested, **Then** the harness trains on one corpus/model and tests on another.

---

### User Story 6 - Benchmark gate, pilot, and durable persistence (Priority: P3)

Before any full run, a benchmark measures real per-event time, peak memory, and
on-disk size per model and context length under full rich capture, and those numbers
set the run scale, the stored-attention layer subset, and the long-context count. A
multi-model pilot then exercises the whole path end-to-end, and the persistence layer
guarantees that an interrupted run loses no previously-committed event.

**Why this priority**: Operational de-risking. The v1 history (out-of-memory cascade,
silent data loss) makes this a gate, but it follows the capability slices.

**Independent Test**: The benchmark emits a table of time/peak-memory/disk per
`(model, context-length)`; the pilot runs ≥2 architectures × all corpora at small N
without out-of-memory; a simulated mid-run interruption followed by resume restores
100% of previously-committed events.

**Acceptance Scenarios**:

1. **Given** the benchmark output, **When** the run scale, attention-layer subset,
   and long-context count are chosen, **Then** they are derived from measured numbers,
   not estimates.
2. **Given** a run interrupted mid-way, **When** it resumes, **Then** every event
   that was committed before the interruption is restored and not recomputed.
3. **Given** the pilot, **When** it completes, **Then** it reports per-corpus
   fail/hallucination balance and abstention-detector precision/recall, and records
   no out-of-memory skips.

---

### Edge Cases

- **Prompt shorter than the lookback window** → event is explicitly skipped/flagged,
  never silently stored with a malformed window.
- **A head/layer with degenerate geometry** (all-zero operator, isolated attention
  node) → recorded with the project's established convention (e.g., NaN sentinel),
  not a crash or a silently imputed value.
- **Grouped-KV model where a per-head assumption would misalign Q and K/V** →
  expansion is mandatory; a mismatch must fail loudly, not produce a plausible-wrong
  operator.
- **Sliding-window / locally-attending layers** → effective support recorded; metrics
  must not assume full `T×T` everywhere.
- **Closed-book event with no document** → routing/evidence fields marked
  not-applicable, never fabricated.
- **Ambiguous abstention** ("I'm not sure, but possibly X") → classified by the
  documented rule; the validation sample must include such cases.
- **Cache larger than the git-branch store can hold at full-program scale** → the
  first-allocation cut stays within the durable store; the scale risk is documented
  and bounded (see Assumptions), and the completeness/durability checks still hold.
- **Adding a roster model or corpus after some captures exist** → existing event
  bundles are untouched; only the new combinations are computed.

## Requirements *(mandatory)*

### Functional Requirements

**Capture & completeness**

- **FR-001**: The substrate MUST capture, in a single forward pass per event, every
  raw tensor required by the parent program's metric catalog, and a completeness
  check MUST confirm 100% of catalog metrics map to a stored tensor before any full
  run.
- **FR-002**: The substrate MUST store as raw: per-layer hidden states at the answer
  position and a short surrounding token window; answer-position attention rows per
  `(layer, head)`; full attention matrices for a configurable layer subset;
  gold-evidence token spans; K sampled answers with token logprobs; answer-token
  logits; and per-model metadata.
- **FR-003**: The substrate MUST compute, in-pass, the per-layer token-cloud
  eigen-spectrum and Marchenko–Pastur-fit statistics (the raw token cloud is too
  large to store) and store only those reductions.
- **FR-004**: The substrate MUST save each model's unembedding/final-normalization
  once per model so per-layer logit projections are reconstructable offline without
  storing per-event per-layer logits.
- **FR-005**: Spectral computations MUST run in double precision; the downcast to a
  compact storage precision MUST happen only at the cache boundary.
- **FR-006**: The substrate MUST capture the prefill (square) attention pass and MUST
  NOT mis-store decode-step attention.

**Inter-head attention-drift surface** *(amendment 2026-06-18; design:
`docs/superpowers/specs/2026-06-18-interhead-attention-drift-family-design.md`)*

- **FR-027**: The substrate MUST compute, **in-pass**, an inter-head
  attention-drift surface `S(t, ℓ)` over a log-spaced query-position set
  (`{answer − offset : 0,1,2,4,…,256} ∪ gold-evidence positions`) across all
  layers, and store **only** the reduced surface (new bundle field
  `interhead_drift_surface`) — never the raw `H×T` attention blocks (too large,
  same rule as the token-cloud spectra).
- **FR-028**: Each `S(t, ℓ)` cell MUST include the corpus-agnostic measures —
  inter-head Jensen–Shannon (and Hellinger) **dispersion** and the head-head
  overlap-matrix **effective rank / Fiedler gap / top eigenvalue** — computed in
  double precision at the spectral seam; the evidence-coverage scalar is recorded
  only for corpora that provide a gold span (a with-context diagnostic).

**Model-agnostic generality**

- **FR-007**: The substrate MUST resolve Q/K/V, attention weights, the output
  projection, and per-layer hidden states from each roster architecture's own
  structure, driven by model configuration rather than a single hard-coded layout.
- **FR-008**: The substrate MUST expand grouped/multi-query KV heads to one key/value
  per query head before forming per-head operators, and MUST fail loudly on any
  head-count mismatch.
- **FR-009**: For models with non-global attention in some layers, the substrate MUST
  record each layer's effective attention support.
- **FR-010**: Every stored bundle MUST carry per-model metadata (`d_model`,
  `n_layers`, `n_heads`, `d_head`, tokenizer id, pinned model revision).

**Labeling**

- **FR-011**: The substrate MUST assign each event a four-way class
  {correct-answer, wrong-answer, correct-abstention, hallucination} per the design's
  truth table, and MUST derive the hallucination-vs-safe headline binary
  (positive = {wrong-answer, hallucination-on-unanswerable}).
- **FR-012**: Correctness MUST be decided by matching the normalized output against a
  gold alias set, with a token-overlap measure reported as a robustness cross-check.
- **FR-013**: The substrate MUST include an abstention detector (rule-based plus an
  entailment fallback) whose precision and recall are validated on a hand-labeled
  sample.

**Corpora**

- **FR-014**: The substrate MUST provide adapters for HotpotQA, SQuAD2
  (answerable + unanswerable), closed-book TriviaQA/NQ, and one long-context
  benchmark, each emitting one common event record.
- **FR-015**: The common event record MUST carry: document (possibly empty),
  question, gold alias set, answerable flag, evidence spans (when the corpus provides
  them), corpus id, and provenance fields.
- **FR-016**: Corpus sampling MUST target a balanced fail/hallucination rate per
  corpus drawn from natural difficulty and the unanswerable split (no synthetic
  distractor inflation).

**Storage & durability**

- **FR-017**: The cache MUST be keyed by `(model, corpus, event)` and carry a
  capture-version identifier distinct from the v1 feature-layout identifier so v1 and
  v2 caches never collide.
- **FR-018**: Persistence MUST guarantee that captured event data is durably stored and
  never silently dropped by storage-ignore rules (the v1 data-loss defect class), and a
  regression test MUST keep that guarantee green.
- **FR-019**: Resilient resume MUST restore previously-committed events from what was
  actually persisted, so an interrupted run recomputes nothing already done.
- **FR-020**: Adding a roster model or corpus after some captures exist MUST require
  zero re-extraction of existing event bundles.

**Harness interfaces (contracts only)**

- **FR-021**: The substrate MUST expose a frozen-cache loader that returns, per event,
  the four-way/binary target and accepts a pluggable feature assembler of arbitrary
  width (no hard-coded feature count).
- **FR-022**: The substrate MUST provide the null-evidence evaluation pack
  (repeated cross-validation AUROC, permutation p-value, Cohen's d, split-luck
  distribution) generalized to any feature width.
- **FR-023**: The substrate MUST provide an incremental-over-baseline comparison and
  cross-corpus and cross-model transfer splitters, plus a redundancy/partial-
  correlation utility.

**Gate & scope**

- **FR-024**: A benchmark MUST measure real per-event time, peak memory, and on-disk
  size per `(model, context-length)` under full rich capture, and those measurements
  MUST set the run scale, the stored-attention layer subset, and the long-context
  count before any full run.
- **FR-025**: A multi-model pilot (≥2 architectures × all corpora × small N) MUST
  validate schema, grouped-KV handling, labeling/abstention precision-recall,
  storage, resume, and out-of-memory behavior end-to-end before the headline run.
- **FR-026**: The substrate MUST expose a reusable forward-pass capture surface that
  SP-3 can re-invoke with interventions, but MUST NOT itself implement any baseline
  metric (SP-1), geometry metric (SP-2), or intervention (SP-3).

### Key Entities

- **Capture bundle**: the per-`(model, corpus, event)` stored unit — hidden states,
  attention rows, the configured full-attention subset, in-pass spectra, gold spans,
  sampled answers, answer-token logits, metadata, and labels.
- **Model descriptor**: per-model metadata enabling cross-model comparison
  (`d_model`, `n_layers`, `n_heads`, `d_head`, tokenizer, revision, attention-support
  profile).
- **DocQA event record**: the common cross-corpus input (document, question, gold
  aliases, answerable flag, evidence spans, corpus id, provenance).
- **Label**: four-way class + hallucination-vs-safe binary + the evidence used
  (alias match, abstention decision, token-overlap cross-check).
- **Inter-head drift surface**: the per-event in-pass reduction
  `interhead_drift_surface = S(t, ℓ)` over the sampled query positions × layers —
  the captured material for the §5.6 inter-head attention-drift family (FR-027/028).
- **Capture manifest**: the authoritative metric→raw-tensor mapping that the
  completeness check enforces.
- **Cache (versioned, keyed)**: the durable store keyed by `(model, corpus, event)`
  with a capture-version identifier.
- **Harness interface**: the frozen-cache loader + evaluation-pack contracts that
  SP-1..SP-3 consume.
- **Benchmark report / Pilot report**: the measured numbers and end-to-end validation
  that gate the full run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the parent program's metric catalog maps to a stored raw tensor
  (or an in-pass reduction), verified by the completeness check before any full run.
- **SC-002**: From a frozen cache, a downstream consumer computes at least one
  geometry scalar and one baseline scalar for every event with zero GPU use and zero
  model reload.
- **SC-003**: Capture succeeds on at least 5 distinct architectures including at least
  one grouped-KV model and Gemma-2, with recovered per-head Q/K/V and attention shapes
  matching each model's own forward pass (round-trip verified).
- **SC-004**: Every event carries a four-way label and the headline binary, and the
  abstention detector achieves ≥0.90 precision and ≥0.90 recall on the hand-labeled
  validation sample.
- **SC-005**: Each corpus in the first-allocation cut yields a fail/hallucination rate
  within the 25%–75% balance band.
- **SC-006**: Adding one new roster model and one new corpus leaves every existing
  event bundle byte-for-byte unchanged (zero re-extraction).
- **SC-007**: After a simulated mid-run interruption, resume restores 100% of
  previously-committed events and recomputes none of them; the data-loss regression
  test stays green.
- **SC-008**: The benchmark yields per-`(model, context-length)` time, peak-memory,
  and on-disk-size numbers, and the chosen run scale / attention subset / long-context
  count are each traceable to those numbers (no estimate-only commitments).
- **SC-009**: The multi-model pilot completes on ≥2 architectures × all four corpora
  at small N with zero out-of-memory skips and validated labels.
- **SC-010**: The first-allocation deliverable is a frozen, schema-complete cache +
  labels for 6 checkpoints (5 diverse @ 7–14B + Llama-3-8B base) × 3 short corpora at
  full N + a reduced-N long-context probe, consumable by SP-1/SP-2 as pure offline
  sweeps.
- **SC-011**: Every captured event carries an `interhead_drift_surface` `S(t, ℓ)`
  (corpus-agnostic dispersion + overlap-matrix spectrum at every cell; evidence-
  coverage where a gold span exists), and the manifest completeness check covers the
  §5.6 family — so the inter-head attention-drift detector runs as a pure offline
  sweep with zero re-extraction.

## Assumptions

- **Model & continuity**: Phi-3-mini (3.8B) is the v1-continuity anchor in an
  otherwise 7–14B diverse roster; the schema is roster-complete (supports the scaling
  ladder, the 70B anchor, and base/instruct pairs) even though the first allocation
  runs only the 6-checkpoint cut.
- **Long-context benchmark**: a synthetic, distance-controllable benchmark with known
  evidence spans (e.g., RULER/needle-style) is the default; it runs at reduced N in
  the first allocation. The full far-evidence/RoPE-wrap study is a later sub-project.
- **Label adjudication**: alias + normalized-exact-match with a token-overlap
  cross-check is the default correctness rule; an LLM-judge is an optional robustness
  add-on, not a dependency.
- **Abstention detector**: a rule set plus an entailment-model fallback; its exact
  threshold and model are pinned during the pilot against the validation sample.
- **Storage medium**: the v1 git-branch store with force-add persistence carries the
  first-allocation cache (tens of GB at the modest cut). At full-program scale the
  cache may exceed what the branch store should hold; that scale risk is acknowledged
  and bounded to a later allocation, and does not change the SP-0 contract.
- **Compute**: a modest first allocation (~1–2 H200s, ~300–600 GPU-hr); the benchmark
  gate sets exact counts. Per the project's measurement rule, all timing/scale figures
  are set by the benchmark, not estimated.
- **Infra prerequisites**: the v1 out-of-memory and ignore-rule data-loss fixes have
  landed; SP-0 keeps their regression tests green and re-validates out-of-memory
  behavior on H200 (the fix is reasoned, not yet GPU-validated).
- **Downstream boundary**: SP-1 baseline metrics, SP-2 geometry metrics, and SP-3
  interventions are out of scope; SP-0 delivers the substrate, storage, labels, harness
  interfaces, and the SP-3 hook surface only. (The §5.6 in-pass surface is a capture
  responsibility; the §5.6 *detector* is an SP-2 family.)
- **Constitution gate (FR-027/028)**: adding `interhead_drift_surface` changes the
  captured feature set, so per Principle V the **pod capture-wiring commit is gated on
  a constitution v3.1.0 touch** (extend Principle II TDD scope to the new inter-head
  dispersion / overlap-matrix primitives; record the §5.6 family). The CPU-only summary
  primitives (library code, not yet "the extracted set") and the spec amendment may land
  before that touch — exactly as SP-0 implement was gated on v3.0.0.
