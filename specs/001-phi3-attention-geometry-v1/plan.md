# Implementation Plan: Phi-3 Attention-Geometry as a Leading Indicator of DocQA Failures (v1)

**Branch**: `001-phi3-attention-geometry-v1` | **Date**: 2026-05-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-phi3-attention-geometry-v1/spec.md`

## Summary

Build a Python research library that generates a balanced 4800-event DocQA dataset, runs forward
passes through `microsoft/Phi-3-mini-128k-instruct` (32 layers × 32 heads, MHA), extracts per-
(token, layer, head) attention components, computes 7-scalar atomic-unit features (stable rank,
top-k_Grass=8 Grassmannian distance, spectral entropy on each of QKᵀ and AVWO, plus Forman-Ricci-
token on the per-(t,ℓ,h) attention graph), and runs per-regime composite logistic regression and
functional-data analysis on 32-point spine curves to recover β(ℓ) coefficient functions per
evidence-distance bin. Technical approach: port the DCSBM spectral/event-alignment primitives
verbatim, add Forman-Ricci-token via `GraphRicciCurvature`, add FDA via `skfda`, and pin every
random and content-derived seed to a SHA-derivation rule. No pooling across bins in primary
analysis (Constitution Principle III). Float64 in the spectral seam with 1e-7 parity tolerance
(Constitution Principle IV). TDD on all scientific primitives; library wrappers get contract
tests; exploratory probing scripts are carved out.

## Technical Context

**Language/Version**: Python 3.11+ (HuggingFace `transformers` + `torch` ecosystem; matches the
DCSBM prior-work codebase to enable verbatim port of spectral primitives).

**Primary Dependencies**:
- `torch` (PyTorch, ≥2.3 with CUDA 12.x — required for `Phi3Attention` forward and hookable
  attention components on Phi-3-mini-128k-instruct).
- `transformers` (HuggingFace, ≥4.45 — first revision with stable `Phi3Attention` API surface).
- `numpy` and `scipy` (numerical seam; SVDs, linalg, hypergeometric tests).
- `scikit-learn` (per-regime composite logistic regression with L2 regularization; ROC/AUROC).
- `skfda` (FPCA + functional logistic regression on 32-point spine curves; chosen over `FDApy`
  for v1 — see research.md decision §3).
- `GraphRicciCurvature` (Forman-Ricci reference implementation; used both for production and as
  parity oracle in tests).
- `networkx` (graph backend for Forman-Ricci computation).
- `pandas` (dataset manifest JSONL → DataFrame I/O, CEM strata tables).
- `pytest` (test framework).
- `hypothesis` (property-based tests on spectral primitives — required by Constitution
  Principle II's "100 seeded random inputs" parity rule).

**Storage**:
- Primary: local SSD, ~100 GB working set.
- Cached `F` tensor (per-atomic-unit features, dense over `J=256` lookback): ~7 MB/event × 4800
  events = ~33 GB (revised from design-doc 8-feature estimate; 7 features × float32).
- Cached `D` tensor (pairwise head-head distances, log-spaced lookback): ~2.6 MB/event × 4800 =
  ~12 GB.
- Out-of-lookback `F` summaries (mean, p10, p50, p90, std over full-T): ~32 KB × 4800 = ~150 MB.
- Dataset + manifests: ~1 GB.
- **Total working set**: ~46 GB.
- Replication: nightly `rsync` to S3 hot tier during collection.
- Archive: S3 Glacier deep archive on completion.
- Dataset manifest + code: git, pushed to GitHub continuously.

**Testing**: `pytest` with `hypothesis` for property tests on spectral primitives. Parity tests
assert `max_abs_diff ≤ 1e-7` in `float64` against the DCSBM reference on 100 seeded random
inputs. Library wrappers (`skfda` FPCA, `skfda` functional logistic, `sklearn` logistic) require
contract tests pinning input shape, output shape, and one numerical sanity check. End-to-end
pipeline has one integration test on a 6-event toy dataset.

**Target Platform**: Linux x86_64 + single NVIDIA GPU (RTX 4090 or A100 class locally; H100
spot for cloud burst). The Phi-3-mini-128k-instruct model fits in ~8 GB GPU memory at fp16; the
attention extraction layer requires fp32 attention scores for spectral parity, accepted as a
GPU-memory pressure point on local hardware.

**Project Type**: Research artifact (single Python project). Source layout under `src/phi3geom/`
with carved-out `exploratory/` directory exempt from TDD per Constitution Principle II.

**Performance Goals**:
- **Pilot**: 600-event end-to-end pipeline within 72 GPU-hours (Spec SC-004).
- **Full study**: ≤120 GPU-hours total (Forman path projection 80 GPU-hr × 1.5× safety margin)
  and ≤$400 cloud spend (Spec SC-008).
- **Parity**: `max_abs_diff ≤ 1e-7` in float64 on spectral primitives versus DCSBM reference
  (Constitution Principle IV).
- **Storage I/O**: ≤2× the actual analysis time spent on cache reads/writes during composite
  fitting (not a hard limit; flagged if exceeded for the optimization).

**Constraints**:
- **Float64 in the spectral seam** (Constitution Principle IV). Float32 permitted only at the
  storage boundary (`F` and `D` tensors).
- **No pooling across the 6 evidence-distance bins** in primary analysis (Constitution
  Principle III; Spec FR-010, SC-003).
- **Reproducibility by content hash** for every reported artifact (Constitution Principle I;
  Spec FR-011).
- **TDD on enumerated scientific primitives** (Constitution Principle II); exploratory scripts
  must live under `exploratory/` and MUST NOT be imported by code under TDD scope.
- **k_Grass = 8** (fixed for v1); **J = 256** (fixed for v1); **k_attn** decided at pilot time
  and pinned thereafter (Spec assumptions; Constitution Principle IV).
- **Single-developer cadence**, multi-day work increments.

**Scale/Scope**:
- 4800 events × (256 lookback × 32 layers × 32 heads × 7 features) = ~10.5 billion feature
  scalars in dense `F` cache.
- 4800 events × (10 log-spaced lookback positions × 32 layers × 32 heads × 32 heads × 2 edge
  types) ≈ 6.3 billion pairwise distances in `D` cache.
- ~12 source modules; ~20 unit/property test files; ~4 contract test files; 1 integration test;
  1 quickstart.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Required by Plan | Status |
|---|---|---|
| **I. Reproducibility by Content Hash** | Manifest SHA, model revision SHA, prompt template SHA256, generation config SHA256, per-event/match/split/analysis seeds derived from SHA1, code commit SHA in artifact dir, event_id = SHA256(template_sha ‖ doc ‖ q ‖ gold). | PASS. All hashing/seeding pinned in `src/phi3geom/reproducibility/seeds.py` and `src/phi3geom/dataset/manifest.py`. Raw `QKᵀ/A/Q/K/V/O` NOT cached. |
| **II. Test-First for Scientific Primitives (NON-NEGOTIABLE)** | TDD on: spectral primitives, Forman-Ricci-token, hooks, dataset construction + evidence-distance, CEM matching, EM normalization, crossbar pairwise Grassmannian, event-alignment, storage manifest, CUSUM/EWMA-on-FPCA-scores adapter. Parity 1e-7 float64 on 100 seeded random inputs. Library wrappers get contract tests. Exploratory scripts carved out. | PASS. Test plan in §Testing above. Module layout below segregates TDD-scope code from exploratory code. |
| **III. Per-Regime Analysis (No Pooling)** | All FPCAs, functional logistic regressions, per-regime composite logistics, AUROC reports per-bin. Pooled estimate is appendix-only (negative control SC-003). | PASS. `src/phi3geom/analysis/composite.py` and `src/phi3geom/analysis/fda.py` accept a `bin_id` parameter and refuse to fit on cross-bin data; a separate `pooled_negative_control.py` module exists exclusively for SC-003 reporting. |
| **IV. Numerical Discipline at Spectral Seam** | Float64 in spectral computations; float32 only at `F`/`D` cache boundary. k_Grass=8 pinned; J=256 pinned; k_attn pinned-once-at-pilot. | PASS. Spectral functions take/return `np.float64` arrays; cache writer downcasts to float32 and records the downcast in the cache header. |
| **V. Specification-Driven Research Workflow** | Spec → plan → tasks → implement. This plan addresses each principle. Plan has Constitution Check (this section). Complexity Tracking captures any violation. | PASS. Workflow is the Spec Kit flow. No violations to track. |

**No violations.** Complexity Tracking section below remains empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-phi3-attention-geometry-v1/
├── spec.md                          # /speckit-specify output (complete)
├── plan.md                          # This file (/speckit-plan output)
├── research.md                      # Phase 0 output (/speckit-plan)
├── data-model.md                    # Phase 1 output (/speckit-plan)
├── quickstart.md                    # Phase 1 output (/speckit-plan)
├── contracts/                       # Phase 1 output (/speckit-plan)
│   ├── atomic_unit.md               # Per-atomic-unit feature function signatures
│   ├── manifest.md                  # Dataset manifest JSONL schema
│   ├── cache.md                     # F/D tensor cache layout
│   └── composite.md                 # Per-regime composite logistic I/O contract
├── checklists/
│   └── requirements.md              # Spec quality checklist (passed)
└── tasks.md                         # Phase 2 output (/speckit-tasks - NOT this command)
```

### Source Code (repository root)

```text
src/
└── phi3geom/                        # The research library (TDD scope)
    ├── __init__.py
    ├── dataset/
    │   ├── generation.py            # Synthetic Wikidata-templated DocQA generator (TDD)
    │   ├── normalization.py         # EM normalization (TDD; FR-002)
    │   ├── matching.py              # CEM matching (TDD; FR-003)
    │   ├── distance.py              # Evidence-distance computation (TDD; FR-001)
    │   └── manifest.py              # Dataset manifest I/O + SHA pinning (TDD; FR-011)
    ├── extraction/
    │   ├── hooks.py                 # Phi3Attention forward hooks (TDD; FR-004)
    │   └── pipeline.py              # End-to-end forward + cache writeback (integration test)
    ├── geometry/
    │   ├── spectral.py              # stable rank, Grassmannian, spectral entropy
    │   │                            # (TDD; 1e-7 float64 parity vs DCSBM reference; FR-005)
    │   └── ricci.py                 # Forman-Ricci-token on attention graph (TDD; parity vs
    │                                # GraphRicciCurvature reference cases)
    ├── lattice/
    │   ├── crossbar.py              # 32-choose-2 pairwise head-head Grassmannian (TDD; FR-006)
    │   ├── spine.py                 # 32-point spine curve aggregates (TDD; FR-007)
    │   └── long_line.py             # Per-(ℓ,h) over-token series (TDD)
    ├── analysis/
    │   ├── composite.py             # Per-regime composite logistic (contract test; FR-008)
    │   ├── fda.py                   # FPCA + functional logistic via skfda (contract test;
    │   │                            # FR-009)
    │   ├── changepoint.py           # CUSUM/EWMA on FPCA scores (TDD; ports DCSBM primitives)
    │   └── pooled_negative_control.py  # Pooled fit ONLY for SC-003 negative control
    ├── storage/
    │   └── cache.py                 # F/D tensor cache read/write/integrity (TDD; FR-013)
    ├── reproducibility/
    │   └── seeds.py                 # SHA-derived seeds (TDD; FR-011)
    └── reporting/
        └── writeup.py               # Per-bin AUROC table, β(ℓ) plots (FR-014)

exploratory/                         # Carve-out from TDD (Constitution Principle II)
├── notebooks/                       # Ad-hoc analyses; MUST NOT be imported by src/phi3geom/
└── probes/                          # Geometry probing scripts

scripts/
├── run_pilot.sh                     # 600-event pilot driver (US1, US2)
└── run_full_study.sh                # 4800-event full study driver (US3, US4)

tests/
├── unit/                            # TDD scope
│   ├── test_spectral_parity.py      # 1e-7 float64 vs DCSBM, 100 seeded inputs (hypothesis)
│   ├── test_ricci_parity.py         # vs GraphRicciCurvature published reference cases
│   ├── test_normalization.py        # NFKC/lowercase/article-strip/whitespace pipeline
│   ├── test_matching.py             # CEM cell partitioning + balancing
│   ├── test_evidence_distance.py    # Token-distance computation correctness
│   ├── test_hooks.py                # Tiny synthetic Phi3Attention-shaped module
│   ├── test_crossbar.py             # 32-choose-2 pairwise correctness
│   ├── test_spine.py                # 32-point aggregate correctness
│   ├── test_manifest.py             # Read/write/integrity
│   ├── test_changepoint.py          # Port DCSBM CUSUM/EWMA tests
│   └── test_seeds.py                # SHA derivation determinism
├── contract/                        # Library wrapper contracts
│   ├── test_skfda_fpca_shape.py     # FPCA input/output shapes
│   ├── test_skfda_func_logistic.py  # Functional logistic shapes + sanity
│   ├── test_sklearn_logistic.py     # Per-regime composite logistic shapes
│   └── test_event_alignment.py      # Lookback indexing port from DCSBM
└── integration/
    └── test_pilot_pipeline.py       # End-to-end on 6-event toy
```

**Structure Decision**: Single Python project under `src/phi3geom/`. The module split mirrors
the spec's conceptual layers (dataset → extraction → geometry → lattice → analysis → reporting),
each enforceable as a TDD boundary. The `exploratory/` directory is the carve-out required by
Constitution Principle II — it is at the repository root (not under `src/`) to make accidental
imports from within `phi3geom` syntactically obvious (`from exploratory.probes import ...` is a
visible smell). `tests/unit/` is the TDD scope; `tests/contract/` covers library wrappers;
`tests/integration/` covers end-to-end. The `analysis/pooled_negative_control.py` module is
deliberately segregated so a code reviewer can verify that pooled fits exist ONLY for SC-003.

## Complexity Tracking

> No Constitution Check violations. This table is empty by design.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| _(none)_  | _(none)_   | _(none)_                             |
