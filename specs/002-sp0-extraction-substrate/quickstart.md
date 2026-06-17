# Quickstart: SP-0 — Multi-Model Geometry Extraction Substrate

**Feature**: `002-sp0-extraction-substrate`

The order is **gate → pilot → capture → verify → hand off**. Nothing full-scale runs before
the benchmark gate and pilot pass.

## 0. Prerequisites

- A v3.0.0 constitution amendment via `/speckit-constitution` (plan.md Constitution Check)
  — **required before implementation**, generalizing the v1 Determinism / Failure-event /
  Matching / Principle-I-raw-caching contracts to v2.
- Tighten `pyproject` to a single `transformers` version ≥4.48 (e.g. 4.53) — R1.6.
- HF auth + pinned model revisions for the roster (Constitution I).
- 1–2 H200s (first allocation).

## 1. Benchmark gate (sets N, S, long-context N — no estimates)

```bash
python -m phi3geom.scripts.benchmark_gate \
    --models phi3-mini llama3-8b qwen2.5-7b mistral-7b gemma2-9b llama3-8b-base \
    --context-buckets short long \
    --rich-capture \
    --out reports/sp0/benchmark.json
```
Emits per `(model, context_bucket)`: `sec_per_event`, `peak_mem_gb`, `disk_mb_per_event`,
and the derived `chosen_N`, `layer_subset_S`, `longctx_N`. **Watch `nvidia-smi`** — the v1
OOM fix is reasoned, not GPU-validated; eager attention is the memory risk (R1.1).

## 2. Multi-model pilot (validates the whole path)

```bash
python -m phi3geom.scripts.run_pilot_v2 \
    --models llama3-8b qwen2.5-7b \         # ≥2 diverse architectures
    --corpora hotpotqa squad2 triviaqa_nq ruler \
    --n-per-corpus 40 \
    --out reports/sp0/pilot.json
```
Asserts: GQA expansion correct, Gemma-2/sliding handling, labeling + abstention P/R ≥0.90,
storage + resume, **zero OOM skips**, per-corpus fail/hallucination balance in 25–75%.

## 3. First-allocation capture (after gate + pilot pass)

```bash
python -m phi3geom.scripts.run_pilot_v2 \
    --models phi3-mini llama3-8b llama3-8b-base qwen2.5-7b mistral-7b gemma2-9b \
    --corpora hotpotqa squad2 triviaqa_nq \  # 3 short corpora at full N
    --n-per-corpus <chosen_N> \
    --long-context ruler --longctx-n <longctx_N> \   # reduced-N probe
    --capture-version 2.0.0 \
    --cache-root cache/
```
Captures the rich bundle per `(model, corpus, event)`; in-pass token-cloud spectra;
durable persistence + resilient resume.

## 4. Verify completeness (the SC-001 gate)

```bash
python -m phi3geom.scripts.check_manifest_completeness --capture-version 2.0.0
# asserts every program-catalog §5 metric maps to a stored CaptureBundle field
```

## 5. Hand off to SP-1/SP-2 (offline, zero GPU)

```python
from phi3geom.analysis.harness import load, null_evidence

ds = load("cache/", capture_version="2.0.0", corpora=["hotpotqa"])
X = ds.assemble(lambda b: my_feature_vector(b))   # arbitrary-width assembler
res = null_evidence(X, ds.targets, groups=ds.groups,
                    n_repeats=5, n_folds=20, n_perm=200, seed=0)
# -> cv_auroc, permutation_p, cohens_d, split_luck  (no model reload, no GPU)
```

SP-3 instead re-imports `phi3geom.extraction.capture` to re-run forward passes with
interventions on the structures SP-2 found predictive — using the same substrate, no
re-extraction.

## Test before you trust (Constitution II)

```bash
pytest tests/unit/test_capture_roundtrip.py      # per-arch Q/K/V/attn shapes + GQA expansion
pytest tests/unit/test_mp_fit_analytic.py        # MP bulk edge vs closed-form on a Gaussian
pytest tests/unit/test_labeling_truthtable.py    # 4-way + abstention fixtures
pytest tests/contract/test_data_loss_regression.py   # the v1 .gitignore-drop regression
pytest tests/contract/test_manifest_completeness.py  # SC-001
```
