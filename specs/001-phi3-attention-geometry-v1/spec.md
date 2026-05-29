# Feature Specification: Phi-3 Attention-Geometry as a Leading Indicator of DocQA Failures (v1)

> **SUPERSEDED IN PART (2026-05-28, constitution v2.0.0):** The primary analysis
> is now a single POOLED, distance-blind detector; per-regime/per-bin analysis is
> a secondary diagnostic. See
> `docs/superpowers/specs/2026-05-28-distance-blind-failure-detector-design.md`.
> Sections describing per-regime composites as the headline are retained for
> history but are no longer the primary methodology.

**Feature Branch**: `001-phi3-attention-geometry-v1`

**Created**: 2026-05-18

**Status**: Draft

**Input**: User description: "Extend the spectral instability analysis from prior DCSBM work to
`microsoft/Phi-3-mini-128k-instruct`. Build a balanced dataset of 4800 DocQA events (synthetic
Wikidata-style, EM-graded with constrained `Answer:` prompt) stratified across 6 evidence-distance
bins, then probe attention-head geometry on it using a three-edge lattice (within-layer crossbars,
across-token long lines, depth-axis spine over 32 raw layers) computed from per-(token, layer,
head) atomic units. Each atomic unit produces 8 scalar features from QKᵀ and AVWO matrices
(stable rank, Grassmannian distance, spectral entropy, Forman-Ricci on the token-attention graph).
Analysis uses per-regime composite logistic regression (the DCSBM-R2 lesson — no pooling across
bins in primary analysis) and functional data analysis on 32-point spine curves to recover β(ℓ)
coefficient functions showing which depths carry discriminative signal."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pilot End-to-End Pipeline (Priority: P1)

The researcher runs the full data → forward-pass → geometry-extraction → per-regime composite
pipeline at pilot scale (50 fail + 50 control per bin × 6 bins = 600 events) on
Phi-3-mini-128k-instruct, producing a per-bin AUROC report for a spectral-only baseline composite
(no Ricci features yet). This proves the pipeline works on the target model and is the smallest
viable slice that verifies every stage of the methodology before scaling cost-of-failure rises.

**Why this priority**: Without a working pilot, full-study collection is uninsurable. The pilot
exposes pipeline defects, CEM match-yield problems per bin, B6 anomalies (e.g., RoPE-wrap
artifacts), and runtime estimates for the full study. It is also the minimum that can validate
the failure-event EM normalization on a hand-checked sample.

**Independent Test**: Run the pipeline end-to-end on 600 events. Verify (a) per-bin AUROC values
are produced, (b) hand-verifying the EM normalization on 50 events yields 100% agreement with
human judgment, (c) CEM matching reports per-bin yield, (d) end-to-end runtime is recorded.
Forman-Ricci computation is not required for this story.

**Acceptance Scenarios**:

1. **Given** the pinned model revision and 600 pilot events generated under the dataset manifest,
   **When** the pilot pipeline runs end-to-end, **Then** a per-bin AUROC report is produced for
   the spectral-only baseline composite within 72 GPU-hours.
2. **Given** the model's constrained-prompt outputs and the canonical Wikidata-templated gold
   answers, **When** the EM normalization sequence is applied to both sides, **Then** the
   automated fail/control labels agree with a human-judged label on 100% of a 50-event sample.
3. **Given** the pilot run, **When** CEM matching is applied per bin on (question template,
   distractor density, gold-answer-length) coarsenings, **Then** ≥50% match yield is achieved at
   ≤1.5× oversampling in at least 5 of 6 bins.

---

### User Story 2 - Forman-Ricci Feature Integration (Priority: P2)

The researcher adds the Forman-Ricci-token feature to the atomic unit by computing Forman-Ricci
curvature on the per-(token, layer, head) attention graph (sparsified to top-`k_attn` edges per
node), then re-runs the per-regime composite to report Ricci's marginal AUROC gain per bin.

**Why this priority**: Forman-Ricci is the committed Ricci variant for v1 (chosen for cost:
~80 GPU-hr full study vs. ~440-720 for Ollivier-Ricci). Adding it after the pilot keeps the
Ricci-integration risk separate from pipeline correctness risk. The marginal-gain measurement
also directly answers whether Ricci is load-bearing in the composite.

**Independent Test**: Given the pilot dataset and the pilot's spectral-only composite results,
add Forman-Ricci-token features and re-fit the per-regime composite. Report each bin's marginal
AUROC change with confidence intervals.

**Acceptance Scenarios**:

1. **Given** the pilot's per-(t, ℓ, h) attention graphs, **When** Forman-Ricci-token is computed
   on each graph sparsified to top-`k_attn` edges, **Then** the result matches a published
   reference implementation within parity tolerance for at least 100 seeded random inputs.
2. **Given** the spectral-only baseline composite per bin from US1 and the Ricci-augmented
   composite, **When** per-bin marginal AUROC is reported, **Then** each bin shows a point
   estimate of marginal gain with 95% confidence interval and the report identifies in how many
   bins Ricci is statistically distinguishable from zero.
3. **Given** the cost projection of ~80 GPU-hr for the Forman path, **When** Ricci is integrated
   into the pilot, **Then** observed wall-time and GPU-hour usage for the Ricci step alone are
   within 1.5× of the projection, or a revised projection is recorded before US3 begins.

---

### User Story 3 - Full-Study Dataset Collection (Priority: P3)

The researcher scales from pilot to the full balanced dataset of 4800 events (400 fail + 400
control per bin × 6 evidence-distance bins) with CEM matching, dataset manifest committed to
git, and all reproducibility pins (model revision SHA, prompt template SHA256, generation config
SHA256, per-event seeds, matching RNG seed, split seed) recorded.

**Why this priority**: The full-study dataset is the input substrate for the headline analysis
(US4). It is separable from analysis because its correctness criteria (balance, hash integrity,
manifest reproducibility) can be verified independently of any composite-model results.

**Independent Test**: Given pilot validation and the chosen Forman-Ricci variant, generate the
4800-event dataset and verify: per-bin balance (400/400 after CEM), manifest SHA committed,
event-identity reproducibility from manifest + code SHA, and CEM match yield reported per bin.

**Acceptance Scenarios**:

1. **Given** the pilot-validated dataset contract, **When** the full-study dataset is generated,
   **Then** each of the 6 bins contains exactly 400 fail and 400 control events post-CEM (or is
   flagged as compromised with explicit yield numbers).
2. **Given** the dataset manifest, **When** event_ids are recomputed from
   `SHA256(prompt_template_sha || document_bytes || question_bytes || gold_answer_bytes)` on a
   different machine, **Then** at least 99% of events produce identical event_ids and identical
   fail/control assignments under the EM normalization.
3. **Given** the manifest SHA, model revision SHA, and code commit SHA, **When** the artifacts
   directory is inspected, **Then** all three are present and the dataset cannot be confused
   with an artifact from a different run.

---

### User Story 4 - Per-Regime Composite + β(ℓ) Spine Report (Priority: P4)

The researcher fits the per-regime composite logistic on the full-study dataset and performs
functional principal component analysis plus functional logistic regression on the 32-point
spine curves to recover β(ℓ) coefficient functions per bin, producing the headline writeup.

**Why this priority**: This is the deliverable result. It directly answers the headline question:
does the DCSBM-R2 finding generalize to Phi-3 attention geometry on DocQA?

**Independent Test**: Given the full-study dataset and cached F/D tensors, fit and report per-bin
AUROC and β(ℓ) coefficient functions with confidence bands. Verify that the pooled-across-bin
composite collapses (negative control).

**Acceptance Scenarios**:

1. **Given** the full-study dataset and atomic-unit features, **When** a per-regime composite
   logistic with L2 regularization is fit independently in each of the 6 bins, **Then** at least
   4 of the 6 bins (target: B2-B5) report AUROC above 0.80 with 95% CI not crossing 0.50.
2. **Given** the 32-point spine curves per token, **When** functional PCA and functional logistic
   regression are fit per bin, **Then** β(ℓ) coefficient functions with 95% confidence bands are
   produced per bin and at least one depth-interval per bin (for at least 4 of 6 bins) has CI
   not crossing zero.
3. **Given** the per-regime composites, **When** an across-bin pooled composite is fit as a
   negative control, **Then** its AUROC is below 0.75 or its CI overlaps 0.50 substantially,
   demonstrating that pooling collapses the signal (the DCSBM-R2 lesson confirmed).
4. **Given** the QKᵀ-Grassmannian head-graph and the AVWO-Grassmannian head-graph (analyzed
   independently per Principle III), **When** results are compared, **Then** the writeup reports
   their per-bin agreements and disagreements qualitatively.

---

### Edge Cases

- **B1/B2 below natural 5% failure rate**: easy-end bins may not produce enough failures without
  intervention. Adversarial distractor generation is enabled if natural failure rate after 1.5×
  oversampling is below 5%; the adversariality policy is recorded in the dataset contract.
- **B6 RoPE-wrap artifact**: if pilot results show B6 (3072-4096 tokens) baselines qualitatively
  diverging from B5 in ways suggesting RoPE wrap rather than longer-distance difficulty, B6 is
  reported as appendix-only and excluded from the headline AUROC table.
- **Bins with low CEM match yield**: <50% at 1.5× → escalate to 3× oversample. <30% at 3× → flag
  as compromised in writeup. <10% at 3× → escalate to researcher for explicit scope decision.
- **Pilot runtime overrun**: end-to-end pilot exceeds 72 GPU-hours → investigate before scaling.
  The bottleneck stage is identified and either optimized or budget-revised before US3.
- **HF model revision unavailable**: the pinned HuggingFace revision SHA becomes inaccessible →
  halt and escalate; do NOT silently fall through to a different revision.
- **Forman-Ricci on degenerate graphs**: nodes with no edges after top-`k_attn` truncation → a
  documented convention (e.g., 0, NaN, or drop atomic unit) is recorded in the dataset contract
  and applied consistently.
- **Generation early-stops before answer**: when the model emits a stop token immediately,
  defining `t_answer_commit` is ambiguous; the convention used is recorded and applied.
- **Identical document selected by two events**: distinct (document, question, gold-answer)
  triples may collide on document bytes; event_id remains unique by construction, but matching
  must not double-count.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST generate a balanced DocQA dataset of 4800 events (400 fail + 400
  control per bin × 6 evidence-distance bins) using synthetic Wikidata-style templates, with
  evidence positioned at controlled distances measured as tokens from end-of-evidence to first
  generated answer token: B1 [128, 256), B2 [256, 512), B3 [512, 1024), B4 [1024, 2048),
  B5 [2048, 3072), B6 [3072, 4096).

- **FR-002**: System MUST classify each event as fail or control by exact-match-after-
  normalization on the model's constrained `Answer:`-prompted output against the canonical
  Wikidata-templated gold answer. Normalization sequence: (1) NFKC unicode normalize, (2)
  lowercase, (3) strip leading whitespace and punctuation, (4) strip leading articles `a`,
  `an`, `the`, (5) collapse internal whitespace, (6) strip trailing punctuation and whitespace.
  Match criterion: exact string equality after normalization. LLM-as-judge, F1, substring match,
  and semantic similarity are FORBIDDEN as match criteria.

- **FR-003**: System MUST balance fail and control events within each bin via Coarsened Exact
  Matching on three covariates: (a) question template id (≈10 Wikidata templates, no
  coarsening), (b) distractor density coarsened to {low <25%, medium 25-75%, high >75%} of
  bin-width minus evidence-span, (c) gold-answer length coarsened to {1 token, 2-3 tokens,
  4+ tokens}.

- **FR-004**: For each event, system MUST execute one forward pass through
  `microsoft/Phi-3-mini-128k-instruct` at a HuggingFace revision SHA pinned in the dataset
  manifest, using generation parameters `temperature=0, do_sample=False, max_new_tokens=32,
  stop_strings=["\n", "<|end|>"]` and a SHA256-pinned prompt template, and extract per-(token,
  layer, head) attention components for all tokens `t` in the lookback window
  `[t_answer_commit − 256, t_answer_commit]`, all 32 layers `ℓ`, and all 32 heads `h`.

- **FR-005**: For each atomic unit (token, layer, head), system MUST compute the per-atomic-unit
  feature vector consisting of **7 scalars**: stable rank, top-`k_Grass=8` Grassmannian subspace
  distance, and spectral entropy each computed on QKᵀ and on AVWO independently (6 spectral
  scalars), plus Forman-Ricci-token curvature computed once on the per-(t, ℓ, h) attention
  graph derived from `softmax(QKᵀ/√d_head + mask)` and sparsified to top-`k_attn` edges per
  node (1 Ricci scalar). The "8 features" mention in the user description is reconciled as the
  design-doc-default asymmetric variant: Forman-Ricci is graph-defined and lives once at the
  (t, ℓ, h) level rather than once per matrix. Adding a 4th spectral metric on each matrix to
  restore QKᵀ↔AVWO symmetry is a v2 ablation, not v1 scope.

- **FR-006**: For each (token, layer), system MUST compute pairwise Grassmannian distances
  between all 32 heads taken in pairs (496 edges per token-layer) on the QKᵀ subspace and
  separately on the AVWO subspace, yielding two parallel head-graphs per (token, layer) which
  are analyzed independently.

- **FR-007**: For each token, system MUST produce a 32-point spine curve over all 32 raw
  layers without phase bucketing, where each point is a head-graph aggregate (mean Grassmannian,
  spectral gap, mean Forman-Ricci, modularity) at that depth.

- **FR-008**: System MUST fit a per-regime composite logistic regression with L2 regularization
  independently within each of the 6 evidence-distance bins, using the per-atomic-unit features,
  head-graph aggregates, and per-bin spine FPC scores as candidate features. System MUST report
  per-bin AUROC with 95% confidence intervals.

- **FR-009**: System MUST fit functional principal component analysis on the 32-point spine
  curves per bin and per class, then fit functional logistic regression to recover β(ℓ)
  coefficient functions per bin, and report β(ℓ) with 95% confidence bands per bin.

- **FR-010**: System MUST NOT pool events across the 6 evidence-distance bins in any primary
  FPCA fit, functional logistic regression, per-regime composite logistic, or AUROC report.
  Pooled estimates, if included at all, are appendix material only and MUST be explicitly
  labeled as the negative-control "pooling collapses signal" demonstration.

- **FR-011**: System MUST persist per run, in an artifact directory: the dataset manifest SHA,
  the HuggingFace model revision SHA, the prompt template SHA256, the generation config SHA256,
  per-event seeds derived from `SHA1("event:" + event_id)[:8]`, the matching RNG seed derived
  from `SHA1("match:" + bin_id)[:8]`, the split seed derived from `SHA1("split:v1")[:8]`, and
  the code commit SHA at run time.

- **FR-012**: System MUST run a pilot at 50 fail + 50 control per bin × 6 bins = 600 events
  end-to-end before initiating full-study collection. The pilot MUST verify: (a) end-to-end
  runtime, (b) per-bin CEM match yield, (c) B6 qualitative behavior relative to B5, (d) EM
  normalization correctness on a hand-verified 50-event sample. The pilot covers US1 (and US2,
  if Forman-Ricci is integrated at pilot time).

- **FR-013**: System MUST cache per event the per-atomic-unit feature tensor `F` at dense token
  resolution over the `J=256` lookback window and the pairwise head-head distance tensor `D`
  at log-spaced lookback positions `j ∈ {0, 1, 2, 4, 8, 16, 32, 64, 128, 256}`. Raw `QKᵀ`,
  `A_h`, `Q`, `K`, `V`, and `O` MUST NOT be persisted as cached source-of-truth tensors; they
  are recomputed on demand from seed + model + input.

- **FR-014**: System MUST produce a writeup containing: per-bin AUROC table with 95% confidence
  intervals, β(ℓ) coefficient functions per bin, qualitative comparison of QKᵀ-Grassmannian vs
  AVWO-Grassmannian head-graph results, and an explicit statement of which bins (if any)
  reproduce the DCSBM-R2 finding that within-regime composites achieve near-perfect failure
  discrimination while pooled-across-regime composites collapse.

- **FR-015**: System MUST report per-bin CEM match yield and MUST flag any bin with yield below
  50% at 1.5× oversample; such bins escalate to 3× oversample. Bins below 30% at 3× MUST be
  labeled as compromised in the writeup. Bins below 10% at 3× MUST escalate to the researcher
  for explicit scope decision before being included in the headline.

- **FR-016**: System MUST handle the B1 (and possibly B2) case where natural failure rate is
  below 5% by enabling adversarial distractor generation. The adversariality policy used MUST
  be recorded in the dataset contract and the manifest, and MUST be the same across all events
  in that bin.

- **FR-017**: System MUST treat the B6 bin as conditionally headline based on pilot results.
  If B6 metric baselines diverge qualitatively from B5 in ways consistent with RoPE-wrap
  artifacts rather than longer-distance difficulty (e.g., a discontinuity rather than a smooth
  monotone trend across B4 → B5 → B6 on baseline spectral measurements), B6 is reported as
  appendix-only and excluded from the headline AUROC table.

- **FR-018**: System MUST treat the v2 scope boundary as a hard limit for this feature: cross-
  layer composition (Elhage-style QK-OV between heads at different depths), GQA generalization,
  multi-scale time series proper (beyond two-stage FDA → CUSUM/EWMA), head-graph Ricci, and
  evidence-distance bins beyond 4096 tokens are OUT OF SCOPE for v1 and MUST NOT be silently
  pulled into the analysis or implementation.

### Key Entities *(include if feature involves data)*

- **DocQA Event**: a triple of (document with evidence at a controlled position, question
  targeting that evidence, canonical gold answer), augmented with an evidence-distance bin
  assignment and a CEM stratum identifier. Identified by `event_id =
  SHA256(prompt_template_sha || document_bytes || question_bytes || gold_answer_bytes)`.

- **Atomic Unit**: a single (token, layer, head) location at which one QKᵀV computation occurs.
  Carries the per-atomic-unit feature vector derived from that location's QKᵀ matrix, AVWO
  matrix, and per-(t,ℓ,h) attention graph.

- **Head-Graph**: a graph at fixed (token, layer) with 32 nodes (one per head) and 496 edges
  weighted by pairwise Grassmannian subspace distance. Two parallel head-graphs exist per
  (token, layer): one with QKᵀ-Grassmannian edge weights, one with AVWO-Grassmannian edge
  weights. Analyzed independently.

- **Spine Curve**: a 32-point function over the depth axis at fixed token; each point is a
  head-graph aggregate (mean Grassmannian, spectral gap, mean Forman-Ricci, modularity) at the
  corresponding layer. The unit of functional data analysis.

- **Long Line**: a time series at fixed (layer, head) over tokens within the lookback window
  `[t_answer_commit − 256, t_answer_commit]`. The unit of two-stage FDA → change-detection
  analysis.

- **Evidence-Distance Bin**: one of 6 logarithmically-spaced ranges (B1 through B6) of
  question-to-evidence token distance. The stratification axis. Never pooled in primary
  analysis.

- **CEM Stratum**: a cell defined by (question-template-id, distractor-density-coarsening,
  gold-answer-length-coarsening) within a single bin. Approximately 90 cells per bin. The unit
  of fail/control balancing.

- **Per-Regime Composite**: a logistic regression model fit independently within one
  evidence-distance bin, taking atomic-unit features and aggregates as input and producing a
  per-event failure probability. Six per-regime composites exist (one per bin).

- **Dataset Manifest**: a JSON-Lines file listing all events with their event_ids, bin
  assignments, CEM strata, generation seeds, and fail/control labels. SHA256-pinned and
  committed to git.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Within-regime DCSBM-R2 transfer: at least 4 of the 6 bins (target: B2-B5) report
  per-regime composite AUROC above 0.80 with 95% confidence intervals not crossing 0.50. This
  is the headline finding that within-regime attention geometry of Phi-3 is a leading indicator
  of DocQA failure.

- **SC-002**: Discriminative-depth locator: β(ℓ) coefficient functions from functional logistic
  regression on the 32-point spine identify at least one layer-depth interval with 95%
  confidence band not crossing zero in at least 4 of 6 bins (target: B2-B5). The writeup names
  the identified depths and interprets them.

- **SC-003**: Pooling-collapse negative control: a composite logistic fit on events pooled
  across the 6 bins achieves AUROC below 0.75 OR has a 95% CI that overlaps 0.50 substantially.
  This confirms the DCSBM-R2 lesson on Phi-3 attention geometry.

- **SC-004**: Pilot timeliness and validity: the 600-event pilot completes within 72 GPU-hours
  and produces per-bin AUROC values for a spectral-only baseline composite. Pilot output is
  sufficient to (a) confirm or disconfirm full-study readiness, (b) identify B6 RoPE-wrap risk
  if present, and (c) validate EM normalization against human judgment at 100% agreement on a
  50-event sample.

- **SC-005**: Dataset reproducibility: re-generating the dataset from the committed manifest
  SHA and code commit SHA on a different machine produces identical event_ids and identical
  fail/control assignments under the EM normalization for at least 99% of events.

- **SC-006**: CEM yield: at least 5 of 6 bins achieve ≥50% CEM match yield at ≤1.5× oversample
  (sufficient to populate 400/400 without escalation). Remaining bins, if any, escalate to 3×
  oversample with explicit yield reporting.

- **SC-007**: Hand-verification of failure-classification: on a 50-event sample, the automated
  exact-match-after-normalization classification agrees with human-judged correctness on 100%
  of events. This validates the failure-event definition before scaling.

- **SC-008**: Cost budget: full-study cost stays within ≤120 GPU-hours and ≤$400 cloud spend
  (the Forman-Ricci ~80 GPU-hr projection × 1.5× safety margin).

- **SC-009**: Both head-graphs reported: the writeup reports per-bin AUROC and β(ℓ) results
  independently for the QKᵀ-Grassmannian head-graph and the AVWO-Grassmannian head-graph, and
  compares their qualitative agreement and disagreement per bin.

## Assumptions

- **Forman-Ricci is committed as the v1 Ricci variant**, overriding the prior-design-document
  pilot-then-commit path between Ollivier-Ricci and Forman-Ricci. The user description pinned
  Forman-Ricci directly, prioritizing the lower cost projection (~80 GPU-hr full study, ~$240
  cloud) over the literature anchor of Ollivier-Ricci. The pilot in US1 verifies pipeline
  correctness, not Ricci variant choice. (Recorded as a deviation from
  `docs/superpowers/specs/2026-05-18-phi3-attention-geometry-failure-prediction-design.md`
  section (b).)
- **HF revision SHA** for `microsoft/Phi-3-mini-128k-instruct` is pinned at the start of US1
  (pilot kickoff) and recorded in the dataset manifest. The same SHA is used for the full study.
- **Solo-developer cadence**: multi-day work increments, single-GPU local environment, cloud
  burst (H100 spot) available for the pilot and full-study collection.
- **TDD scope** per Constitution Principle II applies: spectral primitives, Forman-Ricci-token,
  per-head extraction hooks, dataset construction and evidence-distance computation, CEM
  matching, failure-EM normalization, crossbar pairwise Grassmannian, event-alignment
  infrastructure, storage manifest, and the two-stage CUSUM/EWMA adapter on FPCA scores are
  test-first. External library wrappers (FPCA, functional logistic, per-regime logistic) require
  contract tests only. Exploratory and visualization scripts are exempt from TDD.
- **No phase bucketing on the layer axis**: the spine analysis uses all 32 raw layers without
  any coarse pooling into early/middle/late phases. Per-regime stratification on the
  evidence-distance axis is independent and remains mandatory per Constitution Principle III.
- **k_Grass = 8** (Grassmannian subspace dimension) is pinned for v1 per Constitution Principle
  IV. Varying k_Grass is a v2 ablation.
- **J = 256** (lookback window length) is pinned for v1 per Constitution Principle IV.
- **k_attn** (top-k attention-graph sparsification for Forman-Ricci) is decided once per study
  and pinned in the dataset manifest. Resolved at pilot time; not varied within an analysis.
- **k_Grass and k_attn are distinct constants** and MUST NOT be confused in implementation.
- **Constitution v1.0.0** (`.specify/memory/constitution.md`) governs this feature. Any
  deviation from the principles MUST be enumerated in the plan's Constitution Check complexity
  table with a rejection justification.
- **v2 deferrals**: cross-layer composition, GQA generalization, multi-scale time-series proper,
  head-graph Ricci, and evidence distances >4096 tokens are OUT OF SCOPE for v1 per FR-018.
