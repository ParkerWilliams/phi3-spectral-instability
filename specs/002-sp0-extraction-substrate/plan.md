# Implementation Plan: SP-0 — Multi-Model Geometry Extraction Substrate

**Branch**: `002-sp0-extraction-substrate` | **Date**: 2026-06-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-sp0-extraction-substrate/spec.md`

**Governing design**: `docs/superpowers/specs/2026-06-17-sp0-extraction-substrate-design.md`
(parent program: `docs/superpowers/specs/2026-06-17-v2-correctness-geometry-program-design.md`)

## Summary

SP-0 is the GPU-heavy, capture-once foundation of the v2 correctness-geometry
program. It generalizes the v1 Phi-3-only extraction pipeline into a
**model-agnostic rich-capture substrate** that, in one forward pass per
`(model, corpus, event)`, dumps the raw material every downstream metric needs —
per-layer hidden states, per-head Q/K/V + post-softmax attention, in-pass
token-cloud spectra, gold-evidence spans, K-sample generations, and per-model
metadata — under a versioned, durable, manifest-stamped cache. It ships the
labeling (4-way + hallucination-vs-safe), the four corpus adapters, and the
evaluation-harness **interfaces** SP-1/SP-2/SP-3 consume, plus a benchmark gate and
a multi-model pilot. The technical approach is settled by three verified research
threads (`research.md`): eager-attention capture pinned to a single transformers
≥4.48, RULER as the long-context corpus (it emits the gold needle token index
natively), and the K=10/T=1.0 discrete-semantic-entropy recipe with all clustering
offline. **It does not implement any baseline metric (SP-1), geometry metric (SP-2),
or intervention (SP-3).**

## Technical Context

**Language/Version**: Python ≥3.11 (extends the existing `src/phi3geom` package).

**Primary Dependencies**:
- `torch>=2.3`; `transformers` **pinned to a single version ≥4.48** (e.g. 4.51–4.53)
  — research.md §1 found the 4.48 attention refactor changes RoPE placement and
  decoder-layer return arity, so the study must not span it. **This tightens the v1
  `pyproject` pin of `transformers>=4.45,<5.0`** and is a deliberate plan decision.
- `accelerate>=0.26` (device_map for the 70B anchor); `datasets` (HotpotQA, SQuAD2,
  TriviaQA/NQ); `numpy`/`scipy`/`scikit-learn`; `GraphRicciCurvature` (retained).
- Offline-only (downstream, not on the GPU capture path): an NLI model
  (`microsoft/deberta-large-mnli`) for semantic-entropy clustering and an
  abstention judge/classifier — both consumed by SP-1, but their **stored inputs**
  (K-sample texts + logprobs) are an SP-0 responsibility.
- RULER generator (NVIDIA, Apache-2.0) for the long-context corpus; NoLiMa
  (secondary, Adobe non-commercial — license to be confirmed before redistribution).

**Storage**: Local-SSD cache keyed by `(model, corpus, event)`, each bundle carrying
a `capture_version` (distinct from v1's `feature_layout`) and the manifest SHA in a
sidecar header (the v1 `storage/cache.py` pattern, extended). Durable persistence via
the v1 force-add-past-ignore fix; resilient resume reads what was committed.

**Testing**: `pytest` + `hypothesis`. Analytic property tests for the in-pass MP
reduction (closed-form bulk edge on a Gaussian), per-architecture capture round-trip
tests (recovered Q/K/V/attention shapes vs the model's own; GQA expansion correct),
labeling truth-table + abstention fixtures, the data-loss regression test, and a
manifest-completeness contract test.

**Target Platform**: Linux + CUDA (H200), 1–2 GPUs in the first allocation.

**Project Type**: Single research library + extraction CLI — extend `src/phi3geom`.

**Performance Goals**: Per-event capture time, peak memory, and on-disk size are
**measured by the benchmark gate, not estimated** (per
[[feedback_measure_dont_estimate_perf]]); the gate's numbers set N, the stored-`T×T`
layer subset S, and the long-context N. OOM-free across the roster (eager attention
materializes a full `(B,H,T,T)` tensor per layer — research.md §1 — so attention is
captured **layer-by-layer with immediate CPU offload/downcast** to bound peak memory,
the binding constraint on the 70B anchor and long context).

**Constraints**: Float64 at the spectral seam (Constitution IV); eager attention
mandatory (research.md §1, and required for Gemma-2 softcap fidelity); ~300–600
GPU-hr first allocation; zero re-extraction when a model/corpus is added later;
durable persistence (no silent data loss).

**Scale/Scope**: Schema-complete 10-checkpoint roster; first-allocation run = 6
checkpoints (5 diverse @ 7–14B + Llama-3-8B base) × 3 short corpora at full N
(~1000/corpus) + a reduced-N RULER probe.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution is **v2.0.0 and v1-specific** — several of its concrete contracts
were written around a single Phi-3 model, temperature-0 single generation, Wikidata
gold answers, and CEM-matched evidence-distance bins. SP-0's multi-model,
multi-corpus, sampled-generation, hallucination-labeling regime preserves every
**principle's spirit** but breaks several **v1 parameter-level contracts**. This is a
methodology change, so per Principle V + Governance it must route through
`/speckit-constitution` (a v3.0.0 amendment) **before SP-0 implementation begins**.
Enumerated below; the required amendments are tracked in Complexity Tracking.

| Principle / Contract | Status | Resolution |
|---|---|---|
| **I. Reproducibility by content hash** | ✅ spirit / ⚠ letter | SP-0 keeps the manifest-SHA sidecar + content-hash `event_id`. BUT Principle I says "raw `QKᵀ`/`A_h`/`Q/K/V/O` MUST NOT be cached as the source of truth." SP-0's whole architecture caches raw attention + hidden states. Resolution: they are a **reproducible, manifest-SHA-stamped cache** (deterministic from pinned revision + seed + input), not the irreproducible source of truth — the source of truth remains `seed+model+input`. The amendment must **bless raw-tensor caching for the offline-sweep architecture**, with the reproducibility guarantee (recomputable, SHA-stamped) intact. |
| **II. Test-first for scientific primitives** | ✅ compliant | TDD scope extends naturally to the new primitives: per-arch capture hooks, in-pass MP reduction (analytic property test), labeling/abstention, manifest-completeness, storage integrity, harness interfaces. Honored in Phase 1 + tasks. |
| **III. Pooled distance-blind primary analysis** | ✅ spirit | The detector stays pooled + distance-blind; the headline target generalizes from "fail vs control on CEM-50/50" to "hallucination vs safe, balanced by natural difficulty across corpora/models." Amendment generalizes the CEM-50/50 wording; distance-blind is unchanged. (SP-0 only ships the harness interfaces; the analysis is SP-1/SP-2.) |
| **IV. Float64 at the spectral seam** | ✅ compliant + ⚠ fixed params | Float64-in-seam is honored for the in-pass spectra. BUT IV pins `k_Grass=8`, `J=256`, and names `QKᵀ/AVWO` as *the* objects "fixed for v1." v2 changes the object (residual-stream + realized routing + token-cloud spectra). Amendment must scope IV's fixed-parameter clause to v1 and restate the float64 rule object-agnostically. |
| **Determinism contract** (Numerical Standards) | ⚠ violation | "Forward passes through Phi-3-mini-128k-instruct use temperature=0, do_sample=False." v2 needs **K=10 sampled generations at T=1.0** (semantic entropy) across **multiple models**. Amendment must allow sampled generations (seed-pinned for reproducibility) + the multi-model roster. |
| **Failure-event contract** | ⚠ violation | "EM-after-normalization against Wikidata gold; **F1, LLM-judge, substring match … FORBIDDEN**." v2 uses alias-EM (ok) **plus token-F1 as a robustness cross-check, an abstention judge/NLI, and RULER substring scoring** — all currently forbidden. Amendment must permit token-F1 *as a reported cross-check* (EM stays headline), the abstention classifier, and substring scoring for the synthetic long-context corpus. |
| **Matching contract** (CEM) | ⚠ n/a | v2 drops synthetic CEM for natural-difficulty corpora + the unanswerable split. Amendment marks CEM as v1-specific; v2 balances by natural fail/hallucination rate. |
| **V. Spec-driven workflow** | ✅ compliant | This brainstorm→specify→plan flow *is* the workflow. The amendment itself goes through `/speckit-constitution`. |

**Gate decision**: SP-0 planning proceeds (Phases 0–1 below), but **a v3.0.0
constitution amendment via `/speckit-constitution` is a hard prerequisite for
`/speckit-implement`.** No principle is being discarded; the v1 parameter-level
contracts are being generalized to v2. This is logged, not waved through.

**Post-design re-check (after Phase 1)**: The design artifacts introduce **no new
violations** and reinforce compliance — content-hash `event_id` + manifest-SHA
headers (I), TDD scope extended to per-arch capture / MP-fit analytic / labeling /
data-loss regression / manifest-completeness (II), float64 in-pass spectra at the
seam (IV), pooled distance-blind harness interfaces (III). The single prerequisite
remains the v3.0.0 amendment above. Gate stands: **plan ready for `/speckit-tasks`;
implement blocked on the amendment.**

## Project Structure

### Documentation (this feature)

```text
specs/002-sp0-extraction-substrate/
├── plan.md              # This file
├── research.md          # Phase 0 output (3 verified research threads)
├── data-model.md        # Phase 1 output (entities)
├── quickstart.md        # Phase 1 output (benchmark gate → pilot → capture)
├── contracts/           # Phase 1 output
│   ├── capture-manifest.md
│   ├── corpus-adapter.md
│   ├── harness-interface.md
│   └── cache-storage.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root) — extends the existing `src/phi3geom`

```text
src/phi3geom/
├── extraction/
│   ├── hooks.py                 # generalized: model-agnostic capture (was Phi-3-only)
│   ├── adapters/                # NEW: per-architecture resolvers
│   │   ├── base.py              #   ModelAdapter protocol (q/k/v/o/hidden/unembed, GQA, masks)
│   │   ├── phi3.py  llama.py  qwen2.py  mistral.py  gemma2.py
│   ├── capture.py               # NEW: rich-capture pass + in-pass MP reduction + manifest write
│   └── pipeline.py              # re-pointed at capture.py (v1 path retained for provenance)
├── dataset/
│   ├── types.py                 # extended common record (is_answerable, aliases, evidence spans)
│   ├── adapters/                # NEW: hotpotqa.py squad2.py triviaqa_nq.py ruler.py (nolima.py)
│   ├── labeling.py              # NEW: normalize_answer, alias-EM, token-F1, 4-way truth table
│   └── abstention.py            # NEW: rule pre-filter + classifier/judge backstop interface
├── storage/
│   └── cache.py                 # extended: capture_version, raw-tensor bundles, completeness check
├── analysis/
│   └── harness/                 # NEW: SP-1..SP-3 INTERFACES only (no metrics)
│       ├── loader.py            #   frozen-cache loader + pluggable feature assembler
│       ├── null_evidence.py     #   generalized off the 7-feature hardcode
│       ├── transfer.py          #   cross-corpus / cross-model splitters
│       └── redundancy.py        #   partial-correlation / incremental-AUROC utilities
└── scripts/
    ├── benchmark_gate.py        # NEW: per-(model,context) time/mem/disk → sets N, S, long-N
    └── run_pilot_v2.py          # NEW: multi-model pilot driver

tests/
├── unit/                        # per-arch round-trip, MP-fit analytic, labeling/abstention, GQA
├── integration/                 # end-to-end capture on ≥2 architectures × corpora (small N)
└── contract/                    # manifest completeness, cache schema, harness interface, data-loss regression
```

**Structure Decision**: Single-project extension of `src/phi3geom`. The v1 modules
stay for provenance; SP-0 adds the `extraction/adapters`, `dataset/adapters`,
`analysis/harness` packages and generalizes `hooks.py`/`cache.py`. Exploratory
probes stay under `exploratory/` (Constitution II carve-out).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| **Constitution v3.0.0 amendment required before implement** | v2's multi-model + sampled-generation + token-F1/abstention/substring labeling + raw-tensor caching break v1 parameter-level contracts (Determinism, Failure-event, Matching, Principle I letter, IV fixed params) | Proceeding under v2.0.0 unamended would make every SP-0 commit violate the standing constitution; silently reinterpreting the contracts violates Principle V. The amendment is the constitution's own Governance path for methodology change. |
| **Cache raw attention + hidden states** (vs Principle I "recompute on demand") | The capture-once architecture is the program's core cost lever — it turns N GPU re-extractions into one pass + offline CPU sweeps | Recompute-on-demand means every metric re-runs the forward pass (re-paying GPU for SP-1, SP-2, and each SP-3 iteration), defeating the entire program design and the modest GPU budget. Mitigated by keeping the cache reproducible + SHA-stamped (Principle I's actual intent). |
| **Pin a single `transformers` ≥4.48** (narrower than v1's `>=4.45,<5.0`) | The 4.48 refactor moves RoPE placement + changes layer-return arity (research.md §1); spanning it makes per-arch capture code architecture-version-dependent | Supporting the whole 4.45–4.x range doubles the capture code paths (pre/post-refactor) for no scientific gain; one pinned version is the reproducibility-correct choice (Principle I). |
| **Eager attention (no sdpa/flash) for the capture pass** | Post-softmax `T×T` weights only materialize under eager; Gemma-2 softcap only applies under eager (research.md §1, §3) | sdpa/flash never expose the attention matrix and silently drop Gemma-2 softcap → "geometry against a mask the model never used." Recompute-from-Q/K is more error-prone than eager. Memory cost mitigated by layer-by-layer offload. |
