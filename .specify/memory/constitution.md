<!--
Sync Impact Report
==================
Version change: (uninitialized template) → 1.0.0
Bump rationale: Initial ratification; first concrete principles defined from the
v1 design brainstorm (docs/superpowers/specs/2026-05-18-phi3-attention-geometry-
failure-prediction-design.md). Per semantic versioning rules: a MAJOR baseline
is appropriate because no prior numbered version existed.

Principles defined (all new):
- I. Reproducibility by Content Hash
- II. Test-First for Scientific Primitives (NON-NEGOTIABLE within scope)
- III. Per-Regime Analysis (No Pooling Across Evidence-Distance Bins)
- IV. Numerical Discipline at the Spectral Seam
- V. Specification-Driven Research Workflow

Added sections:
- Numerical & Reproducibility Standards
- Research Workflow & Quality Gates
- Governance

Removed sections: none (template placeholders replaced; no prior content existed).

Templates requiring updates:
- ✅ .specify/templates/plan-template.md — Constitution Check section uses a generic
  reference ("[Gates determined based on constitution file]"); no edit needed. The
  gates list will be derived per-feature from this constitution at /speckit-plan time.
- ✅ .specify/templates/spec-template.md — No principle-specific placeholders; generic
  sections remain valid.
- ✅ .specify/templates/tasks-template.md — Task categorization (Setup → Foundational →
  User Stories → Polish) is principle-agnostic and remains valid. Per-feature task
  generation will surface TDD scope per Principle II's categories.
- ✅ .specify/templates/constitution-template.md — Template itself unchanged.
- ✅ CLAUDE.md — Generic SPECKIT pointer to "the current plan"; no principle references
  to update.
- ⚠ README.md — does not exist; deferred. Not required for v1.0.0.

Follow-up TODOs: none. All placeholders resolved.
-->

# Phi-3 Attention Geometry Constitution

## Core Principles

### I. Reproducibility by Content Hash

Every artifact that influences a reported result MUST be addressable by a content
hash or a deterministic seed. Concretely, all of the following MUST be pinned in
the experiment manifest and re-derivable from the manifest plus the code at the
recorded commit SHA: model weights (HF revision SHA), tokenizer and processor
configs (same revision SHA), generation config (SHA256 of canonical JSON),
prompt template (SHA256 of template string), per-event seed, matching RNG seed,
split seed, per-analysis seed, dataset manifest SHA256, and the git commit SHA
of the analysis code. Event identity is defined as
`event_id = SHA256(prompt_template_sha || document_bytes || question_bytes || gold_answer_bytes)`.
Raw `QKᵀ`, raw `A_h`, and raw `Q/K/V/O` MUST NOT be cached as the source of
truth; they are recomputed on demand from `seed + model + input`. Cached
intermediate tensors (e.g., `F`, `D`) MUST carry the manifest SHA in their
directory so divergence is detectable.

**Rationale:** This study's claims rest on small effect sizes inside per-regime
composites. Any silent drift in the model revision, prompt string, decoding
config, or matching RNG could explain those effects away. A reviewer (or
future-self) MUST be able to reproduce any reported number from the manifest
alone.

### II. Test-First for Scientific Primitives (NON-NEGOTIABLE within scope)

Within the TDD scope enumerated in this section, tests MUST be written and MUST
fail before implementation. Red-Green-Refactor is enforced. The TDD scope is:
spectral metric primitives (stable rank, top-k Grassmannian, spectral entropy),
Ricci-token (Ollivier-Ricci, Forman-Ricci), per-head extraction hooks on
`Phi3Attention`, dataset construction and evidence-distance computation, CEM
matching logic, failure-EM normalization, crossbar pairwise Grassmannian,
event-alignment infrastructure (including log-spaced lookback), storage manifest
read/write/integrity, and the two-stage CUSUM/EWMA adapter on FPCA scores.
Parity tolerance for spectral and Ricci primitives is `max_abs_diff ≤ 1e-7` in
float64 on at least 100 seeded random inputs versus the DCSBM reference
implementation or against published reference cases.

External library wrappers (`skfda` FPCA, `skfda` functional logistic regression,
`sklearn` per-regime composite logistic) are NOT under TDD; they require a
contract test that pins input shape, output shape, and one numerical sanity
check. End-to-end inference pipelines require an integration test only.

Exploratory geometry probing scripts, visualization scripts, and notebook
ad-hoc analyses are explicitly carved out from TDD discipline. They MUST live
under a clearly named directory (e.g., `exploratory/`, `notebooks/`) and MUST
NOT be imported by code under TDD scope.

**Rationale:** A spectral or matching bug silently corrupts every downstream
composite without producing a visible failure. The seam must be defended by
property tests and parity tests; the analysis layer above it tolerates
exploration.

### III. Per-Regime Analysis (No Pooling Across Evidence-Distance Bins)

All FPCA fits, functional logistic regressions, per-regime composite logistic
models, AUROC reports, and Ricci-variant decision rules MUST be computed
per-bin (B1 through B6 over evidence-distance). Pooling across bins — either
by concatenating events or by fitting a model that treats the bin as a free
parameter rather than a stratification axis — is FORBIDDEN in the primary
analysis. A model that uses regime as a covariate (e.g., bin id as a
categorical predictor) is acceptable only when its per-bin marginals are also
reported and the pooled estimate is labeled as such. The "no phase bucketing on
the layer axis" commitment is on the layer axis only and explicitly does NOT
extend to the regime axis. The 6 bins are never averaged.

**Rationale:** The DCSBM prior result (R2) showed that pooled composites
collapse while per-regime composites recover near-perfect discrimination. The
present study's primary aim is to confirm this within a new architecture and
new task family; pooling is the failure mode the design is built to avoid.

### IV. Numerical Discipline at the Spectral Seam

The spectral seam — every computation that produces stable rank, Grassmannian
subspace distance, spectral entropy, or any other singular-value-derived
scalar from `QKᵀ` or `AVWO` — MUST execute in `float64`. Downcasting to
`float32` is permitted only at the storage boundary (the production cache of
`F` and `D` tensors). Tests assert float64 parity at the seam to
`max_abs_diff ≤ 1e-7` (see Principle II). Ricci-token computations operate on
attention graphs sparsified to top-`k_attn` edges per node; the chosen
`k_attn` MUST be pinned per-study in the spec and not varied during a single
analysis. The Grassmannian subspace dimension is `k_Grass = 8`, fixed for v1;
varying it is a v2 ablation. The lookback window length is `J = 256`, fixed
for v1.

**Rationale:** Subspace and entropy computations on near-rank-deficient or
near-degenerate spectra are numerically fragile. A silent float32 truncation
shifts AUROCs by amounts comparable to the effects under study.

### V. Specification-Driven Research Workflow

All non-trivial work — defined as anything beyond a single-file edit or a
typo fix — MUST flow through the Spec Kit workflow: brainstorm → `/speckit-specify`
→ `/speckit-clarify` (when needed) → `/speckit-plan` → `/speckit-tasks` →
`/speckit-implement`. Each feature branch corresponds to one specification.
Specifications MUST resolve any `NEEDS CLARIFICATION` markers before
implementation begins. Plans MUST include a Constitution Check that explicitly
addresses each principle in this document; violations MUST be enumerated in the
plan's Complexity Tracking table with the rejected simpler alternative and the
reason the simpler alternative is insufficient. Exploratory work that does not
yet target a reported result is exempt from this workflow but MUST NOT be
promoted into a reported analysis without first passing through it.

**Rationale:** This is a research project with a high cost of irreproducible
or scope-crept analyses. The Spec Kit workflow is the project's only structural
defense against accidental drift between intent and implementation.

## Numerical & Reproducibility Standards

**Precision contract:** Float64 in the spectral seam (Principle IV). Float32
permitted only in the cached `F` and `D` tensors. Manifest records which
columns were stored in which precision.

**Determinism contract:** All randomness is keyed by content-derived seeds
(Principle I). Forward passes through `Phi-3-mini-128k-instruct` use
`temperature=0, do_sample=False, max_new_tokens=32, stop_strings=["\n", "<|end|>"]`.
The prompt template is SHA256-pinned. The HF model revision SHA is pinned at
spec-writing time and recorded in the manifest.

**Failure-event contract:** A failure event is defined by exact-match-after-
normalization on the model's constrained `Answer:`-prompted generation against
the canonical Wikidata-templated gold answer. The normalization sequence is:
NFKC → lowercase → strip leading whitespace and punctuation → strip leading
articles (`a`, `an`, `the`) → collapse internal whitespace → strip trailing
punctuation and whitespace. LLM-as-judge, F1, substring match, and semantic
similarity are FORBIDDEN as match criteria.

**Matching contract:** Within each evidence-distance bin, Coarsened Exact
Matching is performed on (question template id, distractor density,
gold-answer length) at the coarsenings pinned in the v1 design document. Bins
with <30% match yield at 3× oversampling are flagged as compromised in the
writeup; bins with <50% match yield at 1.5× oversampling escalate to 3×.
Unmatched events are discarded from primary analysis and logged.

**Storage contract:** Primary storage on local SSD; replication to S3 hot
tier during collection; archive to S3 Glacier on completion. Dataset manifest
and code in git, pushed to GitHub continuously.

## Research Workflow & Quality Gates

**Specification gate:** A spec is ready for `/speckit-plan` only when (a) no
`NEEDS CLARIFICATION` markers remain, (b) all "Resolved decisions" from the v1
design brainstorm relevant to the feature are explicitly cited or amended, and
(c) the feature's relationship to the v1 scope boundary (cross-layer
composition, GQA, multi-scale TS, head-graph Ricci — all v2) is stated.

**Plan gate:** A plan is ready for `/speckit-tasks` only when its Constitution
Check addresses each of the five principles above and the Complexity Tracking
table justifies any violation. Plans that propose pooling across regimes,
float32 in the seam, or skipping tests for items in the Principle II TDD scope
MUST list the violation and a rejection-justification — there is no implicit
exemption.

**Implementation gate:** Tests under the TDD scope (Principle II) MUST exist
and fail before implementation. Contract tests for library wrappers MUST exist
before the wrapper is used in any reported analysis. Integration tests for
end-to-end inference MUST exist before any production-scale collection run.

**Pilot gate:** The Ricci-variant pilot (Ollivier-Ricci-token vs.
Forman-Ricci-token) MUST complete and the decision rule recorded in the v1
design must be applied before the full-study collection runs. The pilot
outcome is recorded in the spec; the chosen variant is pinned thereafter.

## Governance

This constitution supersedes ad-hoc convention. All amendments MUST be made by
editing this file via the `/speckit-constitution` workflow, which is
responsible for incrementing the version, dating the amendment, propagating
changes through dependent templates, and producing a Sync Impact Report.

**Versioning policy:** Semantic versioning applies to this document.
- MAJOR: A principle is removed or its meaning is redefined in a backward-
  incompatible way (e.g., dropping the per-regime requirement).
- MINOR: A new principle or section is added, or existing guidance is
  materially expanded.
- PATCH: Wording, typo, or clarification edits that do not change the
  enforced rules.

**Amendment procedure:** As a solo-developer project, amendments are author-
approved but MUST be committed in a discrete commit whose message begins
`docs: amend constitution to vX.Y.Z` and whose body summarizes the change. The
amendment commit MUST land before any feature commit that depends on the new
guidance.

**Compliance review:** Every `/speckit-plan` run executes a Constitution Check
against this file. Every `/speckit-analyze` run cross-checks spec, plan, and
tasks for consistency, which includes consistency with these principles. The
project's research artifacts (figures, tables, reported numbers) are subject
to a final compliance check before being included in any external writeup.

**Runtime guidance:** `CLAUDE.md` at the project root points AI assistants to
the current plan; that pointer is the runtime entry into spec-derived context.
This constitution is the standing entry.

**Version**: 1.0.0 | **Ratified**: 2026-05-18 | **Last Amended**: 2026-05-18
