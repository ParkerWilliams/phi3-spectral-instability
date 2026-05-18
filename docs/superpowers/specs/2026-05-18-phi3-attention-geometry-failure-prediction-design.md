# Phi-3-mini Attention Geometry as a Leading Indicator of DocQA Failures — v1 Design

**Status:** Brainstorm complete; ready for `/speckit-specify`.
**Date:** 2026-05-18
**Upstream prior work:** [Spectral Instability in Attention Matrices as a Leading Indicator of Transformer Rule Violations](https://parkerwilliams.org/rambling/2026/3/21/spectral-instability-in-attention-matrices-as-a-leading-indicator-of-transformer-rule-violations) ([code](https://github.com/ParkerWilliams/dcsbm-transformer))

## Problem statement (one-paragraph for `/speckit-specify`)

Determine whether per-head spectral and Ricci-curvature geometry of attention matrices in `microsoft/Phi-3-mini-128k-instruct` (32 layers × 32 heads, MHA, d_model=3072, d_head=96) acts as a leading indicator of rule-violation failures on document question-answering tasks where question-to-evidence token distance is controlled across 6 logarithmically-spaced bins (128–4096 tokens). Generalize the DCSBM-toy-transformer finding that per-regime logistic composites of stable rank, Grassmannian subspace distance, spectral entropy, and (newly added) Ricci curvature recover near-perfect failure discrimination within a regime, while pooled-across-regime composites collapse. Extend the prior atomic-unit feature set with a Ricci variant chosen by empirical pilot (Ollivier-Ricci-token vs. Forman-Ricci-token on per-(t,ℓ,h) attention graphs). Primary aim is the within-layer inter-head geometry expressed by the 32-node head-graph crossbar at each (token, layer), analyzed via functional data analysis on 32-point spine curves to recover β(ℓ) coefficient functions identifying depths where the geometry is discriminative. Failures are defined by exact-match-after-normalization on constrained `Answer:`-prompted Phi-3 generations against canonical Wikidata-templated gold answers; balancing uses coarsened exact matching on question template, distractor density, and answer length within each evidence-distance bin (400 fail + 400 ctrl per bin × 6 bins). Cross-layer composition, GQA generalization, head-graph Ricci, and multi-scale time-series proper are out of v1 scope.

## Committed scaffolding (carried from prior sessions)

- **Architecture target:** `microsoft/Phi-3-mini-128k-instruct`. Standard MHA, num_attention_heads = num_key_value_heads = 32. 32 layers × 32 heads = 1024 architectural heads. d_model=3072, d_head=96. Per-head QKᵀ and AVWO matrices have rank ≤ 96 regardless of T. (Originally Phi-3-mini-4k-instruct; swapped to 128k variant to give context headroom for the 2048–3072 and 3072–4096 evidence-distance bins. Architecturally identical; differs only in RoPE base θ.)
- **Evaluation lattice:** three-edge lattice over (token, layer, head). Atomic unit = one QKᵀV at (t, ℓ, h), producing per-head QKᵀ and AVWO matrices. Atomic-unit features (clarified — see Open Decision #10): 3 spectral scalars on QKᵀ (stable rank, top-k_Grass=8 Grassmannian, spectral entropy) + 3 spectral scalars on AVWO (same three) + 1 Ricci scalar computed on the per-(t,ℓ,h) attention graph derived from softmax(QKᵀ/√d_head + mask) = **7 features per unit**. (The brainstorm's original "8 features" target assumed Ricci could be computed on each of the two matrices independently; in practice Ricci is graph-defined and lives at the (t,ℓ,h) level rather than per-matrix. See Open Decision #10 for whether to add a 4th spectral on each matrix to restore symmetry.)
- **Crossbars:** within fixed (t, ℓ), pairwise over (hᵢ, hⱼ). 496 edges per (t, ℓ). Edge weights = Grassmannian on QKᵀ subspaces and Grassmannian on AVWO subspaces (two parallel head-graphs, analyzed independently).
- **Long lines:** across tokens, fixed (ℓ, h). 1024 time series per event neighborhood. Two-stage FDA → time-series: stage-1 FPCA on per-token trajectories, stage-2 CUSUM/EWMA/change-point on FPCA scores.
- **Spine:** within fixed t, vary ℓ over all 32 rungs. Per-token 32-point curve of head-graph aggregates (mean Grassmannian, spectral gap, mean Ricci, modularity). Analyzed via FPCA and functional logistic regression to recover β(ℓ) coefficient functions.
- **Storage layout:** D[t, ℓ, hᵢ, hⱼ, edge_type] (last dim = {QKᵀ-Grassmannian, AVWO-Grassmannian}) and F[t, ℓ, h, metric] (last dim = the 7 atomic-unit features defined below).
- **Event-aligned analysis** as in DCSBM: align trajectories by lookback j before failure events; matched control populations.
- **No phase bucketing on layer axis.** FDA shares strength across neighboring layers adaptively. No pooling across regime bins.

### Deferred to v2

- Cross-layer composition (Elhage-style QK-OV between heads at different depths).
- Generalization to GQA models.
- Multi-scale time series proper (the 2-stage FDA → TS framing captures the upside without importing financial-TS assumptions).
- **Head-graph Ricci** (rejected for v1 due to collinearity with the head-graph's Grassmannian edge weights — would be a non-independent feature in the per-regime composite).

## Resolved decisions

### (a) Task + regime variable + bin edges + event counts

**Task:** synthetic Wikidata-templated Document QA. Each event = (document with evidence at controlled position, question targeting the evidence, gold answer in canonical form).

**Regime variable:** evidence-distance = tokens from end-of-evidence (minimal answer-bearing span) to first generated answer token.

| Bin | Distance (tokens) | Role | Target events (fail/ctrl) |
|---|---|---|---|
| B1 | 128–256 | Easy-end baseline; adversarial distractors needed to push failure rate ≥5% | 400/400 |
| B2 | 256–512 | Early-mid | 400/400 |
| B3 | 512–1024 | Mid | 400/400 |
| B4 | 1024–2048 | Far | 400/400 |
| B5 | 2048–3072 | Hard, within 4k-context analog | 400/400 |
| B6 | 3072–4096 | Margin bin; included/excluded in headline analysis based on pilot results | 400/400 |

**Total:** 4800 paired events. Pilot at 50/class/bin = 600 events; scale-up factor 8×.

### (b) Ricci design — pilot-then-commit

**Pilot scope:** compute both Ollivier-Ricci-token and Forman-Ricci-token on per-(t,ℓ,h) attention graphs derived from softmax(QKᵀ/√d_head + mask), restricted to top-k_attn=16 attention edges per node, on shared 600-event forward passes. ~55–90 GPU-hr, ~1 week elapsed, ~$200 at H100 spot pricing.

**Decision rule** (per-bin marginal AUROC gain over a spectral + head-graph-aggregates baseline composite):

- **OR wins:** median per-bin gain ≥ 0.02 AND OR > Forman in ≥ 4 of 6 bins.
- **Forman wins:** median per-bin gain ≥ 0.05 AND Forman > OR in ≥ 4 of 6 bins.
- **Both fail:** default to OR for v1, flag in spec that Ricci signal is weak and downstream interpretation should be cautious.
- **Both pass:** take higher median gain.

Asymmetric thresholds encode "ambiguous defaults to OR for literature anchor." The 4/6 consistency rule respects R2 (no averaging across regimes).

**Production cost projection:**
- OR wins: ~440–720 GPU-hr full study, ~$1,300–2,200, 3–5 weeks elapsed.
- Forman wins: ~80 GPU-hr full study, ~$240, 1–2 weeks elapsed.

**Scope binding:** Ricci is computed on the per-(t, ℓ, h) attention graph (token-graph), filling the per-atomic-unit 4th-scalar slot. Head-graph Ricci deferred to v2.

### (c) Binary failure definition

Failure event = the model fails to answer correctly under a constrained-output prompt.

- **Prompt template (SHA256 pinned in spec):**
  ```
  <|system|>You are answering questions about the document below. Answer with only the answer, no preamble.<|end|>
  <|user|>{document}

  Question: {question}
  Answer:<|end|>
  <|assistant|>
  ```
- **Decoding:** `temperature=0, do_sample=False, max_new_tokens=32, stop_strings=["\n", "<|end|>"]`.
- **Normalization** (applied to both generation up to first stop token AND gold answer):
  1. NFKC unicode normalize
  2. lowercase
  3. strip leading whitespace + punctuation
  4. strip leading articles (`a`, `an`, `the`)
  5. collapse internal whitespace
  6. strip trailing punctuation + whitespace
- **Match criterion:** exact string equality after normalization. Binary outcome.
- **Gold answers in canonical form by dataset construction** (synthetic Wikidata templates emit canonical entity strings, dates, numbers — no preposition or article prefixes).
- **No LLM-as-judge, no F1, no substring match, no semantic similarity.**

### (d) Balancing protocol

**Stratification axis:** evidence-distance bin. The 6 bins are never pooled in any per-regime analysis, FPCA fit, or composite logistic.

**Within-bin matching: Coarsened Exact Matching (CEM)** on three confounders (all upstream of the geometry being measured):

| Covariate | Coarsening | Levels |
|---|---|---|
| Question template id (~10 Wikidata templates) | None — each template is its own stratum | ~10 |
| Distractor density | low <25%, med 25–75%, high >75% of bin-width − evidence-span | 3 |
| Gold answer length | 1 token, 2–3 tokens, 4+ tokens | 3 |

~90 cells per bin.

**Procedure:**
1. Generate raw event pool at ≥1.5× the 400/class target per bin (1200/bin nominal).
2. Partition pool into the ~90 cells.
3. Take `min(N_fail, N_ctrl)` per cell; randomly subsample within each cell to hit 400/400.
4. Cells with `min=0` are dropped (empirically unmatched).
5. Bins with <50% match yield at 1.5× oversample escalate to 3× oversample; <30% after 3× flagged in writeup as compromised.
6. Unmatched events discarded from primary analysis; logged for transparency.
7. B1 (and possibly B2) expected to need adversarial distractor generation to push natural failure rate above 5%.

### (e) Sample size justification

400/class/bin × 6 bins = 4800 paired events.

- Per-regime composite logistic with ~15 candidate features (8 atomic + 3 head-graph aggregates + ~3 spine FPCA scores + Ricci variant) and L2 regularization → ~25 events/parameter at max feature count, well above the 10–20× rule of thumb.
- Per-bin FPCA on 32-point spine curves with 400 curves/class supports stable extraction of 5–7 FPCs.
- Long-line FPCA per (ℓ, h) on 400 trajectories per class supports per-head FPC extraction at the head-pooled level; per-head individual analyses filter to "active" heads.

### (f) Reproducibility surface

| Pin | Locked value type |
|---|---|
| Model weights | HF revision SHA at `microsoft/Phi-3-mini-128k-instruct` (chosen at spec writing) |
| Tokenizer + processor configs | Same revision SHA |
| Generation config | SHA256 of JSON-serialized config |
| Prompt template | SHA256 of template string |
| Per-event seed | `int(sha1("event:" + event_id)[:8], 16)` |
| Matching RNG seed | `int(sha1("match:" + bin_id)[:8], 16)` |
| Split seed | `int(sha1("split:v1")[:8], 16)` |
| Per-analysis randomization seed | `int(sha1("analysis:" + step_name)[:8], 16)` |
| Code | git commit SHA logged in every run's artifact directory |
| Dataset manifest | SHA256 of `manifest.jsonl`, committed to git |

**Event content hashing:** `event_id = SHA256(prompt_template_sha || document_bytes || question_bytes || gold_answer_bytes)`.

**Cached tensors (lookback window only):**

| Tensor | Layout | Per-event size | Total at 4800 events |
|---|---|---|---|
| F (per-atomic-unit features) | dense at every t ∈ [t_answer_commit − 256, t_answer_commit], `(256, 32, 32, 8) float32` | ~8 MB | ~40 GB |
| D (pairwise head-head distances) | log-spaced lookback at j ∈ {0, 1, 2, 4, 8, 16, 32, 64, 128, 256}, `(10, 32, 32, 32, 2) float32` | ~2.6 MB | ~12 GB |
| Out-of-lookback F summaries | `(32, 32, 8, 5) float32` (mean, p10, p50, p90, std over full-T) | 32 KB | ~150 MB |
| Dataset + manifests | — | — | ~1 GB |
| **Total** | | | **~55 GB** |

**Not cached:** raw QKᵀ, raw A_h, raw Q/K/V/O. Deterministic from seed + model + input — recompute on demand.

**Lookback window length J=256.** Justification: spans the prefill→answer-commit window where attention over evidence is actively engaged; logarithmic D coverage out to j=256 supports DCSBM-R1's "predictive horizons scale with regime" finding which may show horizons exceeding 64 tokens in long-distance bins. Dense F supports stage-2 CUSUM/EWMA on a regular grid; log D supports spine FDA at 10 well-separated time points.

**Storage location + backup:**
- Primary: local SSD (~100 GB working set).
- Replication: nightly `rsync` to S3 bucket A (hot tier) during collection phase.
- Archive: on completion, full bundle replicated to S3 bucket B (Glacier deep archive).
- Dataset manifest + code: git, pushed to GitHub continuously.

### (g) Stress-tests flagged for the spec

These are committed-scaffolding implications worth pinning explicitly in the spec to avoid downstream regressions:

1. **Per-regime FDA, not pooled.** R2 showed pooling across regimes destroys signal. The "no phase bucketing" commitment is on the layer axis only — does NOT extend to the regime axis. FPCA and functional logistic regression run per-regime (or with regime as a covariate). Pin in spec.
2. **Top-k for Grassmannian: k_Grass=8 default** (the singular subspace dimension used when computing Grassmannian distances on QKᵀ and AVWO matrices). Pinned as a study-wide constant; varying it is a v2 ablation. Note: this is distinct from k_attn=16 used to sparsify the attention graph for Ricci-token computation (see Open Decision #6).
3. **Prefill vs generation phase atomic units.** Atomic units are computed at every (t, ℓ, h) within the lookback window of J=256 tokens before the first answer token in the prefill+generation timeline. The first answer token is the failure-event commit point; analysis aligns trajectories to that point.
4. **Question position fixity.** Convention: `[system][document with evidence at controlled position][question][Answer:][answer]`. Evidence-to-question distance = (question start index − evidence end index). Question always comes after document.
5. **Two parallel head-graphs per (t, ℓ).** One per edge-weight type (QKᵀ-Grassmannian, AVWO-Grassmannian). Analyzed independently; their results compared at writeup time.
6. **B6 inclusion is a pilot decision.** If B6 metric baselines look qualitatively different from B5 in a way suggesting RoPE wrap rather than the natural longer-is-harder trend, B6 is reported as appendix only.

### (h) DCSBM codebase porting plan

| Component | Status |
|---|---|
| Spectral metric primitives (stable rank, top-k Grassmannian, spectral entropy) | **Ports verbatim** — matrix → scalar functions, model-agnostic |
| Event-alignment infrastructure (lookback indexing, paired sampling) | **Ports verbatim** — adapt for log-spaced lookback |
| Per-regime composite logistic + AUROC framework | **Ports verbatim** |
| Per-head extraction (PyTorch forward hooks on `Phi3Attention`) | **Needs adaptation** — from 1-head toy to 32-head × 32-layer Phi-3 |
| Crossbar pairwise Grassmannian between heads | **New** — different slicing on the same primitive |
| FDA on spine curves (FPCA + functional logistic regression) | **New** — use `skfda` |
| Two-stage FDA → TS on long lines | **New** — stage 1 reuses skfda FPCA; stage 2 reuses DCSBM CUSUM/EWMA primitives |
| Failure-EM normalization + constrained-prompt evaluation | **New** — replaces DCSBM rule-violation detection |
| Ricci-token (OR + Forman via `GraphRicciCurvature`) | **New** — adapted to per-(t,ℓ,h) attention-graph input |
| Dataset generator (Wikidata-templated DocQA with controlled distance) | **New** |
| Training loop, DCSBM graph generator | **N/A** — pretrained model, no training |

### (i) TDD scope (constitution-relevant)

| Element | Category |
|---|---|
| Spectral metric primitives | **TDD** (parity 1e-7 float64 + property tests) |
| Ricci-token (OR + Forman) | **TDD** (parity against published reference cases) |
| Per-head extraction hooks | **TDD** (hand-computed expected Q/K/V/A/O on tiny synthetic module) |
| Dataset construction + evidence-distance computation | **TDD** |
| CEM matching logic | **TDD** |
| Failure-EM normalization | **TDD** |
| Crossbar pairwise Grassmannian | **TDD** |
| Event-alignment infrastructure | **TDD** (port DCSBM tests + new tests for log lookback) |
| Storage manifest (write/read/integrity) | **TDD** |
| Inference loop (end-to-end pipeline) | **Integration test only** |
| FPCA fitting (`skfda`) | **Library code + contract test** |
| Functional logistic regression (`skfda`) | **Library code + contract test** |
| Per-regime composite logistic (`sklearn`) | **Library code + contract test** |
| Two-stage CUSUM/EWMA on FPCA scores | **TDD** (port DCSBM primitives + new contract test for FPCA-score adapter) |
| Visualization scripts | **Exploratory** |
| Exploratory geometry probing scripts | **Exploratory** |
| Notebook ad-hoc analyses | **Exploratory** |

**Parity tolerance:** spectral seam computed in float64; parity tests assert `max_abs_diff ≤ 1e-7` between DCSBM reference and new implementation on 100 seeded random inputs. Production cache may downcast to float32 for storage.

## Remaining open decisions (ranked by validity impact)

| # | Open decision | Validity impact | Resolution path |
|---|---|---|---|
| 1 | Pilot outcome → Ricci variant commit | **High** — determines per-atomic-unit Ricci feature load-bearing weight and full-study cost ($250 vs $2,200) | Run pilot per (b); apply decision rule |
| 2 | Exact HF model commit SHA for `Phi-3-mini-128k-instruct` | **High** — wrong revision invalidates reproducibility | Pick at spec time; lock in constitution |
| 3 | Wikidata template catalogue (~10 templates) | **High** — determines failure-event distribution and CEM stratum count | Enumerate at dataset construction; spec dataset contract |
| 4 | Adversarial distractor design for B1 (possibly B2) | **Medium-high** — needed to push natural failure rate ≥5%; form of "adversariality" shapes failure mode distribution | Pilot-time empirical decision; record policy in dataset contract |
| 5 | B6 headline-inclusion | **Medium** — if RoPE wrap or context saturation distorts B6 metric baselines, B6 should be appendix only | Post-pilot qualitative inspection |
| 6 | k_attn for attention-graph sparsification in Ricci-token | **Medium** — k_attn=16 working; k_attn=8 cuts cost ~4×; k_attn=32 doubles cost. (Distinct from k_Grass=8 for Grassmannian subspace dim.) | Test k_attn ∈ {8, 16, 32} on pilot subset; commit one |
| 7 | Long-line stage-2 method (CUSUM vs EWMA vs PELT) | **Medium** — different false-positive characteristics on irregular FPCA-score trajectories | Pilot sensitivity check |
| 8 | Number of spine FPCs (3 vs 5 vs variance threshold) | **Low-medium** — affects degrees of freedom in functional logistic regression | Default 95%-variance threshold; sensitivity on pilot |
| 9 | FPCA backend (`skfda` vs `FDApy`) | **Low** — implementation ergonomics | Pick at implementation time |
| 10 | Atomic-unit feature count: 7 (asymmetric, Ricci only on attention graph) vs 8 (add 4th spectral metric on each matrix to restore symmetry, e.g., effective rank or von Neumann entropy) | **Low-medium** — minor change to downstream feature vector dimensionality; doesn't change the analysis pipeline but affects feature-importance reporting | Default to 7 (asymmetric); revisit if pilot suggests a missing spectral signal on AVWO that a 4th metric would capture |

Items 1–4 must resolve before production-scale data collection begins. Items 5–9 can defer to post-pilot or analysis time without blocking the spec.

## Constraints

- Solo developer, multi-day cadence, Python.
- Single-GPU local + cloud burst available.
- TDD scope as tabulated in section (i); exploratory geometry probing scripts explicitly carved out from TDD discipline.
- Output is research-artifact-grade (spec → plan → execute) using Spec Kit + Superpowers; not production software.
