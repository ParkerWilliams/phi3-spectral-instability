# Design: A correctness/hallucination geometry across models and regimes (v2 program)

**Date**: 2026-06-17
**Status**: Approved (brainstorming) — feeds `/speckit-specify` for SP-0
**Supersedes**: `docs/superpowers/specs/2026-06-16-v2-feature-set-design.md` (the narrow L1/L2/L3 note — same object as v1)
**Builds on**: the v1 null (`docs/superpowers/findings/2026-06-16-v1-geometry-null-result.md`)
**Branch**: `001-phi3-attention-geometry-v1`

---

## 1. Motivation — what the v1 null actually rejected, and why we change the object

The v1 result is a clean, well-powered null on HotpotQA (485 events, 49% fail):
per-head spectral shape, the full per-`(layer,head)` 7168-dim representation, and
the cross-head crossbar are all at chance (honest CV 0.513 ± 0.053, permutation
p = 0.37, all `|d| < 0.10`). That much is settled.

But reading the extraction code (`extraction/hooks.py:209` `recover_qkt_avwo`,
`extraction/pipeline.py:237`) shows the *object* v1 measured is narrower than the
"single-token" framing implies. The two operators are per-head `d_head × d_head`
**second-moment (Gram) matrices aggregated over the entire prefill sequence**:

- `QKt = Qₕᵀ Kₕ = Σₜ qₜ ⊗ kₜ` — cross second-moment of the query/key projections
  over *all* token positions.
- `AVWO = (AV)ᵀ (AV) = Σ_q cᵩ ⊗ cᵩ` — Gram of the per-query context vectors.
  Note `W_O` is captured but **never applied** (`hooks.py:270` returns `avᵀav`),
  so the operator is mislabeled; the realized output-write geometry is unmeasured.

`token_idx` is ignored (`hooks.py:277`). So v1's null is specifically:

> The **scale-free spectral shape of per-head, position-washed second-moment
> operators** does not separate correct from incorrect Phi-3 answers.

That is a *static head-geometry* object. It barely conditions on what happened for
**this** query — which tokens were read, what got written into the residual stream
at the answer position, how the representation moved through depth. Those are
exactly the quantities the Gram aggregation integrates away. The v1 null is
therefore far less surprising than it first reads, and it points at **changing the
object**, not at bolting magnitude/dynamics onto the same Grams.

v2 changes the object: from static per-head operator spectra to **(a) the
residual-stream trajectory** (the information carrier), **(b) the realized routing**
(which tokens were actually read, and what they wrote), and **(c) the
ensemble/spectral structure of the per-layer token cloud** — measured across
**multiple model architectures** and **multiple DocQA regimes**, and validated
**causally**.

## 2. Research question & success bars

> Does a geometry of a transformer's forward pass separate hallucinations from
> grounded/abstaining outputs — **beyond** what cheap confidence signals already
> reveal, and **transferably** across architectures and DocQA regimes?

Three pre-registered bars (the v1 lesson: a single-split point estimate lies):

1. **Existence.** Pooled AUROC whose 95% CI lower bound > 0.5 **and** permutation
   p < 0.05. Reuse the `null_evidence` pack (repeated CV + permutation + Cohen's d
   + split-luck distribution).
2. **Beats baselines.** **Incremental** AUROC over the cheap-baseline ceiling
   (§5.0), CI lower bound > 0 via a nested model / DeLong test. A geometry that
   merely re-derives "the model was unsure" fails this bar.
3. **Transfers (the headline differentiator).** Train on regime/model A, test on
   B; report **cross-corpus** and **cross-model** transfer AUROC. Real geometry
   transfers; confounds and corpus artifacts do not. This single test does more
   than any in-corpus CI to separate signal from artifact.

## 3. Data & labeling

**Corpora (4 regimes):**

| Corpus | Role | Gold spans | Routing metrics |
|---|---|---|---|
| HotpotQA | multi-hop, continuity with v1 null | yes (supporting sentences) | yes |
| SQuAD2 (answerable + unanswerable) | abstention geometry | yes | yes |
| Closed-book TriviaQA / NQ | clean labels, strongest logprob baseline | n/a (no context) | dark — trajectory/RMT/confidence only |
| Long-context (RULER / LongBench / needle) | far-evidence / RoPE-wrap (re-opens deferred B5/B6) | yes | yes (quadratic; H200-feasible) |

**Label — 4-way stored, hallucination-vs-safe headline:**

```
positive (FAIL/HALLUCINATE):  { wrong-answer, hallucination-on-unanswerable }
negative (SAFE):              { correct-answer, correct-abstention }
```

| Condition | Model output | 4-way class | Headline |
|---|---|---|---|
| answerable | matches gold alias (norm-EM) | correct-answer | safe |
| answerable | mismatch (incl. wrongful abstain) | wrong-answer | positive |
| unanswerable | abstains | correct-abstention | safe |
| unanswerable | asserts an answer | hallucination | positive |

Labeling needs: an **abstention detector** (pattern + NLI), and **alias/normalized-EM
+ token-F1** robustness (EM brittleness was flagged in v1 — see
[[project_001_hotpotqa_pilot_2026-06-09_results]]). The 4-way label is recorded at
extraction at near-zero cost so all slicings remain available.

## 4. Architecture — capture once, sweep offline

The reason v1 cannot be extended without GPU is that it **discarded the raw
material** at extraction. v2 inverts this: **one rich forward pass dumps the raw
tensors; every metric is an offline CPU sweep.** GPU cost is paid once per
`(model, corpus, event)`; metric breadth becomes unbounded and re-runnable.

The **capture manifest (metric → raw material)** is the foundation's primary
deliverable (full table in the SP-0 design). Two families cannot be stored raw and
**must be reduced in-pass on the GPU**:

- **RMT token-cloud spectra** — the `T × d` per-layer activation cloud is too big
  to store (~300 MB/event); compute the eigen-spectrum + Marchenko–Pastur-fit
  stats in-pass, store only those.
- **Full attention rollout** — needs full `T × T` per layer; store a layer subset
  (or all layers when budget allows), or compute the rollout-to-evidence scalar
  in-pass.

Forgetting a raw tensor means a re-extraction — the exact v1 failure mode — so the
manifest must be **all-axis-complete** before the first big run.

## 5. Metric catalog (the five lenses)

Tags: `[BASE]` cheap/known-strong ceiling · `[HIGH]` high-prior new bet · `[MED]` ·
`[SPEC]` speculative-but-in-scope. Each metric carries its raw-material dependency.

**5.0 · Baselines / the ceiling** (SP-1 — the tools v1 never touched, probably the
hardest to beat)
- `[BASE]` Answer-token max-softmax · predictive entropy · top1–top2 margin ·
  length-normalized sequence logprob · energy/logsumexp.
- `[BASE]` **Semantic entropy** (Kuhn/Farquhar): K sampled gens → entailment
  clusters → entropy over meaning-clusters. SOTA black-box hallucination detector.
- `[BASE]` **Linear probe on the raw residual stream** at the answer position, per
  layer (Azaria–Mitchell). Plus `p(True)` self-eval. If this hits ~0.9, it's the
  number to beat.

**5.1 · Residual-stream trajectory** (differential geometry — the carrier)
- `[HIGH]` Logit-lens / tuned-lens convergence: depth at which the answer token
  enters top-k, monotonicity of its logit across layers, entropy-vs-depth.
- `[HIGH]` Trajectory curvature of `h₀→…→h_L` at the answer position: total
  turning angle, path length, tortuosity, max curvature.
- `[MED]` Local intrinsic dimension (TwoNN/MLE) and participation ratio per layer.
- `[MED]` Anisotropy / representation-degeneration structure.

**5.2 · Realized routing** (functional analysis / operator theory — the real `T×T`)
- `[HIGH]` Attention-to-evidence: mass on the gold span from the answer position,
  per layer/head; answer-position attention entropy; participation ratio.
- `[HIGH]` Direct logit attribution (DLA) per head/layer — each component's direct
  contribution to the answer-token logit (the "which head mattered" attribution).
- `[HIGH]` Retrieval-head signatures (Wu et al): is the known retrieval-head set
  firing on the evidence?
- `[MED]` Attention rollout / flow (operator product `A_L···A_1`) → end-to-end
  influence of each input token on the answer position; mass-on-evidence.
- `[MED]` Attention Markov-operator spectra: per-layer spectral gap / 2nd
  eigenvalue / stationary entropy (mixing = diffuse = confused).

**5.3 · Random matrix theory** (the right objects this time)
- `[HIGH]` Marchenko–Pastur deviation of the per-layer token covariance: count /
  spacing of outlier spikes beyond the bulk edge (signal eigenvalues).
- `[MED]` Eigenvalue-spacing statistics (Poisson vs GOE / Wigner) — level
  repulsion as an order↔chaos diagnostic.
- `[MED]` Effective/stable rank of the residual covariance per layer (v1's stable
  rank, done on the carrier not per-head Grams).
- `[SPEC]` Heavy-tailed ESD exponent α (HT-SR) on activation Grams; free-probability
  view of layer composition.

**5.4 · Attention-graph geometry** (the Ricci family done right — dead/NaN in v1)
- `[HIGH]` Ollivier-Ricci (optimal-transport) curvature on the realized attention
  graph — the over-squashing / bottleneck detector.
- `[MED]` Graph-Laplacian spectral gap / Cheeger constant per layer.
- `[SPEC]` Persistent homology / TDA of the token cloud or attention graph.

**5.5 · The v1 object, repaired** (kept for a clean matched contrast to the null)
- `[MED]` L1 magnitude norms (already coded, `db3437a`) + L2 per-token dynamics on
  the same head Grams; **and fix the dropped `W_O`** so "AVWO" is actually `AV·W_O`.

**Rigor note:** 5.0–5.1 likely all correlate with one latent "model confidence."
"No tool untouched" done honestly therefore requires the redundancy analysis in §6,
or the program collapses into 12 copies of one detector.

## 6. Evaluation harness (shared across all metric families)

Per family: pooled AUROC + bootstrap CI · repeated CV · permutation p · Cohen's d
(the `null_evidence` pack) **plus**:
- **Incremental AUROC over the §5.0 baseline** (nested logistic / DeLong) — the
  beats-baselines bar.
- **Cross-corpus & cross-model transfer** — the headline differentiator.
- **Redundancy / orthogonality** — partial correlations + nested ablation, so
  breadth ≠ redundancy.

Cross-model transfer lives at the **geometric-feature (scalar) level**: curvature,
MP-spike count, attention-to-evidence mass, semantic entropy are comparable across
models with different `d_model`/`n_heads`. Raw-activation probes and DLA stay
model-specific (they cannot transfer across differing dims) and are reported
per-model.

## 7. Program decomposition (the DAG)

```
SP-0  FOUNDATION  ──►  SP-1  BASELINE  ──►  SP-2  OBSERVATIONAL  ──►  SP-3  CAUSAL
 (extraction substrate)   (the ceiling)        (metric sweep)         (interventions)
```

- **SP-0 · Foundation** (critical path, GPU-heavy). Model-agnostic capture
  substrate + storage schema keyed by `(model, corpus, event)`; 4-way labeling +
  abstention detector; corpus adapters incl. long-context; the shared evaluation
  harness. Validated on a small **multi-model** pilot. *(Own design doc; feeds
  `/speckit-specify` first.)*
- **SP-1 · Baseline ceiling** (CPU on frozen cache) — §5.0. The existence control
  and the number to beat.
- **SP-2 · Observational sweep** (CPU on frozen cache) — §5.1–5.5. Where
  cross-model × cross-corpus × long-context transfer is tested.
- **SP-3 · Causal validation** (GPU-heavy, live model) — knockout / patching /
  tracing **targeted at SP-2's winners**. Depends on SP-2 by construction.

Compute concentrates in **SP-0** (models × corpora × long-context × rich capture)
and **SP-3** (interventions). SP-1/SP-2 are near-free CPU sweeps.

## 8. Expansion axes → DAG mapping

The four axes are **dimensions, not extra stages**:

| Axis | Where it lives |
|---|---|
| A · Cross-model | dimension of SP-0 (capture per model) + SP-2 (transfer) |
| B · Causal interventions | **is** SP-3 |
| C · Long-context | a corpus in SP-0 + a slice in SP-2 |
| D · Depth (full `T×T`, full per-token dynamics, larger N) | richer SP-0 capture |

## 9. Budget, roster, and the first-allocation cut

**Roster (schema-complete, ~10 checkpoints):** diverse architectures
(Phi-3-mini 3.8B — the v1-continuity anchor — plus 7–14B Llama-3-8B, Qwen2.5-7B,
Mistral-7B, Gemma-2-9B) + scaling ladder (Qwen2.5 0.5/1.5/7/72B; 7B shared with the
diverse set) + 70B anchor (Llama-3-70B or Qwen2.5-72B) + a base/instruct pair
(Llama-3-8B base alongside its instruct sibling).

**Envelope:** modest first allocation, ~1–2 H200s, ~300–600 GPU-hr.

**Principle:** full-ambition design, budget-scoped run. The SP-0 schema is
**roster-complete** (all 10 models, long context, full `T×T`, SP-3 hooks), so later
allocations **add data to the same cache with zero re-extraction**. The budget
decides only *which waves run now*.

**First-allocation cut — RUN NOW (the universality headline, full power):**
- 5 diverse architectures @ 7–14B **+ Llama-3-8B base** (the RLHF-reshaping
  mini-result for one extra model's cost) = 6 checkpoints.
- 3 short/medium corpora at full N (~1000/corpus): HotpotQA, SQuAD2±, closed-book.
- Long-context as a **reduced-N probe** (a few hundred events).
- SP-1 (ceiling) + SP-2 (observational sweep) on the frozen cache.
- Reachable headline: *a 6-checkpoint, model-agnostic hallucination geometry that
  beats cheap baselines and transfers cross-corpus.*

**DEFER to next allocation (pre-architected, no re-extraction):**
- Scaling ladder + 70B anchor → the scale-law claim. (Optional "scale teaser": one
  screening-N 72B run.)
- SP-3 causal study — deferral **forced by the DAG** (interventions need SP-2's
  winners first), not only by budget. (Optional ~100-event knockout POC on one
  model to de-risk SP-3.)

**Gate:** SP-0's first task is the **real per-event H200 benchmark across the
roster** — it replaces every estimate here and sets the exact N / long-context
split before the big runs commit (per [[feedback_measure_dont_estimate_perf]]).

## 10. Risks

- **Redundancy with confidence** — everything tracks one latent. → the §6
  orthogonality analysis is mandatory, not optional.
- **Storage / OOM** — v1 lost data twice. → benchmark + pilot first; the v1 fixes
  (force-add past `.gitignore`, per-event `empty_cache`, `expandable_segments`)
  already landed (`fe190b7`) but the OOM fix is not GPU-validated — watch
  `nvidia-smi`.
- **Label noise + abstention-detector accuracy** → alias/EM + token-F1 + optional
  judge robustness check.
- **Capture manifest incompleteness** → a forgotten tensor forces re-extraction;
  manifest must be all-axis-complete before the first big run (§4).
- **Cross-model schema drift** → store per-model metadata (`d_model`, `n_layers`,
  `n_heads`, unembed); transfer claims live at the scalar-feature level only (§6).

## 11. Governance & provenance

- Per `CLAUDE.md` and Constitution Principle V, the extracted-feature-set and
  methodology change ratifies through **`/speckit-specify`**, not a direct jump to
  writing-plans. This program doc + the SP-0 design doc are the brainstorm artifacts
  that feed it.
- The manifest's `feature_layout` / a new `capture_version` keeps v1 and v2 caches
  distinguishable.
- v1 data + reports: branch `experiment/pilot/2026-06-14-hotpot`. v2 design + the
  landed infra/norm code: branch `001-phi3-attention-geometry-v1`.
