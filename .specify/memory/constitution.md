<!--
Sync Impact Report
==================
Version change: 2.0.0 → 3.0.0 (MAJOR)
Amendment (2026-06-17): Generalize the v1-specific parameter-level contracts to
govern the v2 correctness-geometry program — MULTI-MODEL, MULTI-CORPUS,
SAMPLED-GENERATION, HALLUCINATION-LABELING. The five principles' SPIRIT is
preserved; several backward-incompatible contract redefinitions force a MAJOR bump.
Drivers: docs/superpowers/specs/2026-06-17-v2-correctness-geometry-program-design.md
and specs/002-sp0-extraction-substrate/plan.md (Constitution Check).

Modified principles:
- I. Reproducibility by Content Hash — now MULTI-MODEL (each roster model's HF
  revision SHA pinned); the v1 "raw QKᵀ/A_h/Q/K/V/O MUST NOT be cached" rule is
  SUPERSEDED for v2 by a reproducible-cache discipline (raw capture allowed iff
  recomputable + manifest-SHA + capture_version stamped; source of truth stays
  seed+model+input).
- III. Pooled Distance-Blind Primary Analysis — headline target generalized from
  "fail vs control on CEM-50/50" to "hallucination-vs-safe, balanced by natural
  rate across corpora/models"; cross-corpus + cross-model TRANSFER added as
  first-class; two pre-registered bars (existence AND beats-baselines).
- IV. Numerical Discipline at the Spectral Seam — float64 rule restated
  OBJECT-AGNOSTICALLY (any singular-value/eigenvalue scalar incl. in-pass
  token-cloud spectra + MP fit); the fixed-parameter locks (k_Grass=8, J=256,
  QKᵀ/AVWO as THE objects) scoped to v1.
- II. Test-First — TDD scope EXTENDED to the v2 primitives.
Unchanged in spirit: V. Spec-Driven Workflow.

Modified contracts (Numerical & Reproducibility Standards):
- Determinism: multi-model roster + sampled generations (K=10 @ T=1.0, top-p 0.9)
  + greedy T=0 scored answer, per-sample seeds pinned.
- Failure-event: EM-after-normalization stays the HEADLINE; token-F1 (reported
  cross-check), abstention classifier/NLI/judge (unanswerable detection), and
  substring scoring (RULER) are now PERMITTED with scope; 4-way label defined.
- Matching: CEM scoped to v1; v2 uses natural-difficulty corpora balanced to a
  25–75% fail/hallucination band.
- Pilot gate: the v1 Ricci-variant pilot is superseded by the v2 benchmark gate +
  multi-model pilot as the pre-full-run gate.

Added sections: none (existing sections amended in place).
Removed sections: none.

Templates/docs status:
- ✅ .specify/templates/plan-template.md — generic Constitution Check slot; no edit.
- ✅ .specify/templates/spec-template.md — no principle-specific slots; no edit.
- ✅ .specify/templates/tasks-template.md — principle-agnostic; no edit.
- ✅ CLAUDE.md — SPECKIT pointer already on the SP-0 plan; the "amendment required"
  NOTE updated to "ratified v3.0.0" in the same change set.
- ⚠ README.md — still absent; deferred (not required).
Follow-up TODOs: none.

----- Amendment 1.0.1 → 2.0.0 -----
Version change: 1.0.1 → 2.0.0 (MAJOR)
Amendment (2026-05-28): Redefined Principle III. Per-regime analysis is no
longer primary. The PRIMARY analysis is now a single POOLED classifier, BLIND
to evidence distance, evaluated on a balanced (CEM 50/50) set — testing whether
attention-geometry is a deployable failure detector "in the wild." Per-regime /
per-bin analysis is retained only as a SECONDARY DIAGNOSTIC (slice the pooled
detector by measured distance). MAJOR bump: a principle is redefined backward-
incompatibly (the per-regime-primary requirement is dropped). Driver:
docs/superpowers/specs/2026-05-28-distance-blind-failure-detector-design.md.

----- Amendment 1.0.0 → 1.0.1 -----
Version change: 1.0.0 → 1.0.1
Amendment (2026-05-21): Removed the cross-implementation parity-vs-DCSBM
requirement from Principles II and IV. The prior DCSBM work was a
research-direction scaffold, not a ground-truth oracle; spectral/Ricci
primitives are now verified by analytic property tests against closed-form
values in float64. PATCH bump: clarifies the verification method without
changing the float64-discipline rule.

----- Original 1.0.0 ratification notes -----
Version change: (uninitialized template) → 1.0.0
Bump rationale: Initial ratification; first concrete principles defined from the
v1 design brainstorm. Principles defined: I. Reproducibility by Content Hash;
II. Test-First for Scientific Primitives; III. Per-Regime Analysis; IV. Numerical
Discipline at the Spectral Seam; V. Specification-Driven Research Workflow.
-->

# Phi-3 Attention Geometry Constitution

*Scope note (v3.0.0): this project began as a single-model (Phi-3-mini) v1 study and
is now a multi-model, multi-corpus v2 program (the "correctness/hallucination
geometry" study). Phi-3-mini remains the continuity anchor. Where a contract below is
explicitly marked "v1", it is retained for the archived v1 result and superseded for
v2 by the adjacent v2 contract.*

## Core Principles

### I. Reproducibility by Content Hash (multi-model)

Every artifact that influences a reported result MUST be addressable by a content
hash or a deterministic seed. The experiment manifest MUST pin, and every result
MUST be re-derivable from the manifest plus the code at the recorded commit SHA:
**the HF revision SHA of EACH roster model**, tokenizer/processor configs (same
revision), generation config (SHA256 of canonical JSON), prompt template (SHA256),
per-event seed, **per-sample generation seeds** (the sampled-decoding set, Numerical
Standards), matching/split/analysis seeds, dataset manifest SHA256, and the git
commit SHA of the analysis code. Event identity is
`event_id = SHA256(prompt_template_sha || document_bytes || question_bytes || gold_answer_bytes)`.

**Caching of raw forward-pass material (v2 amendment, supersedes the v1 rule).** The
v2 capture-once architecture MAY cache raw per-layer hidden states, per-head Q/K/V,
post-softmax attention rows, and a full-`T×T` layer subset — BUT ONLY as a
**reproducible, derived cache**: each bundle MUST be deterministically recomputable
from `(pinned model revision + seed + input)` and MUST carry the manifest SHA **and a
`capture_version`** in its header so divergence is detectable. The **source of truth
remains `seed + model + input`**; the raw cache MUST NOT be the sole irreproducible
record. (v1 rule, retained for the archived v1 result: raw `QKᵀ`/`A_h`/`Q/K/V/O` were
recomputed on demand and not cached.)

**Rationale:** This study's claims rest on small effect sizes. Any silent drift in a
model revision, prompt, decoding config, or seed could explain effects away — across
a *roster* of models the pinning burden multiplies, so it is enumerated per model.
The capture-once cache is an efficiency layer, not a new source of truth; the
reproducibility guarantee is what makes caching raw tensors admissible.

### II. Test-First for Scientific Primitives (NON-NEGOTIABLE within scope)

Within the TDD scope enumerated here, tests MUST be written and MUST fail before
implementation (Red-Green-Refactor enforced). The TDD scope is: spectral metric
primitives (stable rank, top-k Grassmannian, spectral entropy, magnitude norms);
Ricci-token (Ollivier-Ricci, Forman-Ricci); per-head extraction hooks; dataset
construction and evidence-distance computation; failure-EM normalization; crossbar
pairwise Grassmannian; event-alignment infrastructure; storage manifest
read/write/integrity; and the FPCA/changepoint adapters. **v2 additions to the TDD
scope:** model-agnostic capture + per-architecture adapters incl. **GQA/MQA head
expansion**; the **in-pass token-cloud eigen-spectrum + Marchenko–Pastur fit**;
**4-way labeling + abstention detection**; the **manifest-completeness check**;
**storage integrity + the data-loss regression test**; and the **evaluation-harness
interfaces** (loader, null-evidence pack, transfer splitters, redundancy).

Spectral, Ricci, and the new **spectral-density** primitives MUST be verified by
analytic property tests against closed-form values in `float64` (e.g., rank-1
spectral entropy = 0, identity stable rank = N, **the Marchenko–Pastur bulk edge for
a known-aspect-ratio Gaussian**). External library wrappers require a contract test
pinning input/output shape + one numerical sanity check. End-to-end inference
pipelines require an integration test only. Exploratory probes/visualizations/
notebooks are carved out of TDD and MUST live under `exploratory/`/`notebooks/` and
MUST NOT be imported by code under TDD scope.

**Rationale:** A spectral, capture, GQA-expansion, or labeling bug silently corrupts
every downstream result without a visible failure. The seam is defended by property
tests; the analysis layer above it tolerates exploration.

### III. Pooled Distance-Blind Primary Analysis (generalized target + transfer)

The PRIMARY analysis MUST be a single classifier fit over all events POOLED across
evidence-distance bins, fed ONLY geometry features and BLIND to evidence distance:
the bin — or the distance itself — MUST NOT be an input feature, a stratification
gate, or a free parameter of the primary model. (The "no phase bucketing on the layer
axis" commitment is unchanged and applies to the layer axis only.)

**v2 target (supersedes the v1 CEM-50/50 target).** The headline detector separates
**hallucination-vs-safe** — positive = {wrong-answer, hallucination-on-unanswerable},
negative = {correct-answer, correct-abstention} — on a set **balanced by natural
fail/hallucination rate across corpora and models** (not CEM-matched synthetic 50/50).

**Transfer is first-class.** The study MUST report **cross-corpus** and
**cross-model** transfer (train on one corpus/model, test on another); cross-model
transfer is evaluated at the **scalar-geometric-feature** level (comparable across
differing `d_model`/`n_heads`). Two bars are PRE-REGISTERED and BOTH required for a
positive claim: **(1) existence** — pooled AUROC 95% CI lower bound > 0.5 AND
permutation p < 0.05; **(2) beats-baselines** — incremental AUROC over the
cheap-confidence ceiling (logprob/entropy/semantic-entropy/probe), CI lower bound > 0.

Per-regime / per-bin analysis is RETAINED but SECONDARY and DIAGNOSTIC ONLY (slice
the pooled detector by measured distance); per-bin slices MUST be labeled diagnostics
and MUST NOT be reported as the primary result.

**Rationale:** Per-regime stratification flatters a weak detector; pooling,
distance-blind, is the realistic deployment scenario. The v1 single-split point
estimate lied (0.645 → 0.513), so the existence bar is a CI-plus-permutation pack, and
the beats-baselines bar guards against a geometry that merely re-derives model
confidence. Transfer across corpora/models is the strongest available test that the
signal is geometry, not a corpus/length/confound artifact.

### IV. Numerical Discipline at the Spectral Seam (object-agnostic)

The spectral seam — **every computation that produces a singular-value- or
eigenvalue-derived scalar**: stable rank, Grassmannian subspace distance, spectral
entropy, magnitude norms, **and the in-pass per-layer token-cloud eigen-spectrum +
Marchenko–Pastur fit** — MUST execute in `float64`. Downcasting to `float32` (or
`float16` for stored activations/attention) is permitted only at the storage
boundary. Tests assert correctness at the seam via analytic property checks in
float64 (Principle II). Ricci-token computations operate on attention graphs
sparsified to top-`k_attn` edges per node; `k_attn` MUST be pinned per-study.

**Parameter locks (v1-scoped).** `k_Grass = 8`, the lookback `J = 256`, and the
`QKᵀ`/`AVWO` head-internal operators as the measured objects are **fixed for v1
only**. v2 changes the measured object (residual-stream trajectory, realized routing,
token-cloud spectra) and MUST pin its own parameters (e.g., `k_eig`, the stored-`T×T`
layer subset `S`, the token window `W`) in the feature's spec.

**Rationale:** Subspace, entropy, and spectral-density computations on
near-degenerate spectra are numerically fragile; a silent float32 truncation shifts
AUROCs by amounts comparable to the effects under study — true for the new
token-cloud spectra as much as for the v1 operators.

### V. Specification-Driven Research Workflow

All non-trivial work — anything beyond a single-file edit or typo fix — MUST flow
through the Spec Kit workflow: brainstorm → `/speckit-specify` → `/speckit-clarify`
(when needed) → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`. Each
feature branch corresponds to one specification, and one program sub-project (SP-0,
SP-1, …) corresponds to one feature. Specifications MUST resolve any
`NEEDS CLARIFICATION` markers before implementation. Plans MUST include a Constitution
Check addressing each principle; violations MUST be enumerated in Complexity Tracking
with the rejected simpler alternative and why it is insufficient. A change to the
extracted feature set or the analysis methodology MUST be ratified by amending this
constitution (Governance) before the implementing commit lands. Exploratory work is
exempt but MUST NOT be promoted into a reported analysis without passing through the
workflow.

**Rationale:** A research project with a high cost of irreproducible or scope-crept
analyses needs a structural defense against drift between intent and implementation.

## Numerical & Reproducibility Standards

**Precision contract:** Float64 in the spectral seam — any singular-value/eigenvalue
scalar, including the in-pass token-cloud spectra (Principle IV). Float32/float16
permitted only in the storage cache. The manifest records which columns/tensors were
stored in which precision, plus the `capture_version`.

**Determinism contract (v2).** Forward passes run across the **pinned multi-model
roster** (each model's HF revision SHA recorded). For correctness scoring, the
answer is generated **greedily** (`temperature=0, do_sample=False`,
`max_new_tokens` 32–64, stop on EOS/newline/"Question:"). For uncertainty
(semantic entropy), **K=10 additional samples** are drawn at `temperature=1.0,
top_p=0.9`, each with a **pinned per-sample RNG seed**. The greedy generation is the
one scored for correctness; the K samples feed offline semantic-entropy estimation.
(v1 contract, retained for the archived result: Phi-3-mini-128k only, greedy-only,
`max_new_tokens=32`.)

**Failure-event contract (v2).** The HEADLINE correctness label is
exact-match-after-normalization (alias max-over-references). The normalization
sequence is: NFKC → lowercase → strip leading whitespace/punctuation → strip leading
articles (`a`, `an`, `the`) → collapse internal whitespace → strip trailing
punctuation/whitespace. The following are PERMITTED with explicit scope and MUST NOT
become the headline: **token-F1** (SQuAD-style, as a REPORTED robustness
cross-check); an **abstention classifier / NLI / LLM-judge** solely for detecting
abstention on unanswerable questions; and **substring-match scoring** for the
synthetic long-context corpus (RULER). The label is **4-way** — {correct-answer,
wrong-answer, correct-abstention, hallucination} — with the headline binary
positive = {wrong-answer, hallucination-on-unanswerable}; abstention is its own class
and MUST NOT be folded into "incorrect". (v1 contract, retained for the archived
result: EM-only against Wikidata-templated gold; F1/judge/substring/semantic
similarity were forbidden.)

**Matching contract (v2).** CEM on (question-template id, distractor density,
gold-answer length) within evidence-distance bins is **v1-specific**. v2 uses
**natural-difficulty corpora** (HotpotQA, SQuAD2 incl. unanswerable, closed-book
TriviaQA/NQ, long-context RULER) sampled toward a **healthy fail/hallucination rate
(target band 25–75%)**, with **no synthetic distractor inflation**. Balance is by
natural difficulty + the unanswerable split, not by exact matching.

**Storage contract:** Primary storage on local SSD; durable persistence such that
captured bundles are never silently dropped by storage-ignore rules (the v1 data-loss
defect class); resilient resume reads what was actually persisted. Dataset manifest
and code in git, pushed continuously. External object-storage tiers MAY be used at
full-program scale without changing the durability/resumability/SHA-stamp contract.

## Research Workflow & Quality Gates

**Specification gate:** A spec is ready for `/speckit-plan` only when (a) no
`NEEDS CLARIFICATION` markers remain, (b) relevant resolved design decisions are cited
or amended, and (c) the feature's place in the program decomposition (SP-0..SP-3) and
its v1/v2 scope relationship are stated.

**Plan gate:** A plan is ready for `/speckit-tasks` only when its Constitution Check
addresses each principle and Complexity Tracking justifies any violation. Plans that
propose float32 in the seam, skipping tests for Principle II TDD-scope items, or a
feature-set/methodology change without a ratified constitution amendment MUST list the
violation and a rejection-justification — there is no implicit exemption.

**Implementation gate:** Tests under the TDD scope MUST exist and fail before
implementation. Contract tests for library wrappers MUST exist before use in any
reported analysis. Integration tests for end-to-end capture MUST exist before any
production-scale collection run.

**Benchmark & pilot gate (v2, supersedes the v1 Ricci-variant pilot).** Before any
full-scale collection run: (a) a **benchmark gate** MUST measure real per-event time,
peak memory, and on-disk size per `(model, context-length)` under full rich capture
and set N, the stored-`T×T` layer subset `S`, and the long-context N from those
measurements (no estimate-only commitments); and (b) a **multi-model pilot**
(≥2 architectures × all corpora × small N) MUST validate schema, GQA expansion,
labeling/abstention precision-recall, storage, resume, and OOM behavior. Both
outcomes are recorded in the spec; the chosen parameters are pinned thereafter.

## Governance

This constitution supersedes ad-hoc convention. All amendments MUST be made by editing
this file via the `/speckit-constitution` workflow, which increments the version,
dates the amendment, propagates changes through dependent templates, and produces a
Sync Impact Report.

**Versioning policy:** Semantic versioning applies.
- MAJOR: A principle is removed or its meaning/contract is redefined backward-
  incompatibly (e.g., generalizing the v1 single-model/EM-only/CEM contracts to v2).
- MINOR: A new principle or section is added, or guidance is materially expanded.
- PATCH: Wording, typo, or clarification edits that do not change enforced rules.

**Amendment procedure:** As a solo-developer project, amendments are author-approved
but MUST be committed in a discrete commit whose message begins
`docs: amend constitution to vX.Y.Z` and whose body summarizes the change. The
amendment commit MUST land before any feature commit that depends on the new guidance.

**Compliance review:** Every `/speckit-plan` run executes a Constitution Check against
this file. Every `/speckit-analyze` run cross-checks spec, plan, and tasks for
consistency, including consistency with these principles. Research artifacts (figures,
tables, reported numbers) are subject to a final compliance check before any external
writeup.

**Runtime guidance:** `CLAUDE.md` at the project root points AI assistants to the
current plan; that pointer is the runtime entry into spec-derived context. This
constitution is the standing entry.

**Version**: 3.0.0 | **Ratified**: 2026-05-18 | **Last Amended**: 2026-06-17
