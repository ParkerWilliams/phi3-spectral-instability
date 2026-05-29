# Running phi3geom on a fresh RunPod GPU instance

End-to-end runbook for cloning and validating the pipeline on a fresh RunPod box,
through to the pilot run. Branch: `001-phi3-attention-geometry-v1`.

## 0. Instance choice

Pick a **RunPod PyTorch template** (torch + CUDA pre-installed — saves a ~5 GB torch
download).

| Phase | GPU | Why |
|-------|-----|-----|
| Validation (steps 4–5) | 24 GB (RTX 4090 / A5000) | Cheap; toy docs are short |
| Full study (B6 at 4096 tokens) | 48–80 GB (A6000 / A100 / H100) | Eager attention materializes `(32 heads, T, T)` per layer; ~34 GB just for attention at T=4096 |

- **Disk volume**: ~60 GB for validation/pilot, ~120–150 GB for the full study (model ~8 GB + HF cache + ~46 GB F/D cache + headroom).
- **System RAM**: 32 GB+ (the spectral work is CPU-side numpy; attention captures are offloaded to CPU, so B5/B6 want ~64 GB RAM).
- **vCPUs**: 8+ cores — the per-head SVDs and crossbar are CPU-bound and are the real bottleneck, not the GPU.

## 1. Clone

```bash
cd /workspace    # RunPod's persistent volume mount
git clone https://github.com/ParkerWilliams/phi3-spectral-instability.git
cd phi3-spectral-instability
git checkout 001-phi3-attention-geometry-v1
```

If the repo is private, clone with a token instead:

```bash
git clone https://<YOUR_GITHUB_PAT>@github.com/ParkerWilliams/phi3-spectral-instability.git
```

## 2. Environment + dependencies

```bash
# Inherit the template's pre-installed torch instead of re-downloading ~5 GB:
python -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

If the template has **no** torch (plain Ubuntu image), drop `--system-site-packages`
and install the CUDA build of torch first (match `cu121`/`cu124` to the box's CUDA):

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install -e ".[dev]"
```

## 3. HuggingFace auth + pre-download the model

```bash
export HF_TOKEN=hf_...                                          # faster downloads, no rate-limit warnings
huggingface-cli download microsoft/Phi-3-mini-128k-instruct     # ~7.6 GB, one-time
```

## 4. Verify the numerical seam (CPU-only, ~1 min)

```bash
python -m pytest tests/unit tests/contract
```

Expect **all pass** — **245 passed, 1 skipped** without torch; on a PyTorch template
the torch hooks test runs too (**246 passed, 0 skipped**). This command does not
collect `tests/integration/` — the GPU end-to-end test runs in step 5.

## 5. GPU integration test + per-event timing (the real validation)

```bash
time PHI3_RUN_GPU_TESTS=1 python -m pytest tests/integration/test_pilot_pipeline.py -s
```

**Expect 2 passed**: the GPU end-to-end test (6 toy events on real Phi-3) plus a
CPU report-writer smoke test (no GPU marker, so it always runs). The `time` prefix
gives total wall clock — **divide by 6 for per-event seconds** (the report test is
near-instant), which is the number used to size the pilot.

This test prints no per-event progress, so it can look frozen. To confirm it's alive,
in another shell:

```bash
top -bn1 | grep -m1 python                       # python should be R (running), CPU near 100%+
find /tmp/pytest-of-root -name 'F.npy' | wc -l   # rough completed-event count (may include stale dirs)
```

CPU-bound is expected — `nvidia-smi` will show the GPU mostly idle while a CPU core is
pegged. That's the spectral/crossbar math, not a hang.

## 6. The pilot (only after step 5 passes)

```bash
bash scripts/run_pilot.sh            # 600 events, full pipeline, writes reports/pilot/
bash scripts/run_pilot.sh --with-ricci   # US2: adds the Forman-Ricci feature
```

Outputs land in `reports/pilot/`:
- `pooled_auroc.json` — **headline**: the pooled, distance-blind detector's AUROC +
  95% CI + `beats_chance` (constitution v2.0.0, Principle III)
- `distance_diagnostic.json` — the same detector's AUROC sliced by *measured*-distance
  bin (diagnostic only — never assists the detector; shows where it degrades)
- `confound_audit.json` — a length+distance-only logistic's AUROC vs the geometry
  detector, with an `is_suspicious` flag if geometry looks like a length/position proxy
- `cem_yield.json` — per-bin CEM match yield (flags compromised bins)
- `runtime.json` — wall time + GPU-hour estimate
- `handcheck_sample.jsonl` — 50 events for manual SC-007 verification

**Pilot success criterion (constitution v2.0.0):** pooled AUROC whose 95% CI lower
bound is > 0.5 — i.e. `"beats_chance": true` in `pooled_auroc.json` — within the
≤72 GPU-hr budget. Distance bins are now a **post-hoc diagnostic**, so the old
per-bin SC-004 gate (≥5/6 bins ≥50% CEM yield) and the B6 RoPE-wrap check are
**deferred** with the B5/B6 long-context work — the 201-fact corpus reaches only
B1–B4. See `docs/superpowers/specs/2026-05-28-distance-blind-failure-detector-design.md`.

## 7. Full study (after pilot validates)

```bash
# k_attn sweep first (writes reports/pilot/k_attn_sweep.json):
python -m phi3geom.scripts.kattn_sweep
# then the full 4800-event study:
bash scripts/run_full_study.sh
```

## Reproducibility check (SC-005, run on a second box)

```bash
bash scripts/regenerate_dataset.sh   # regenerates from the manifest; targets >=99% event_id agreement
```

## Notes / gotchas already handled in this branch

- `transformers` is pinned `>=4.45,<5.0`. The hooks + `output_attentions` + eager-attention
  path target the 4.x `Phi3Attention` API; transformers 5.x is a major release not yet
  validated against this code. A fresh `pip` on a 2026 box will otherwise grab 5.x.
- `huggingface_hub` is pinned `<1.0` to match the 4.x transformers line.
- HF token is **optional** — Phi-3-mini-128k is public, so `check-hf-auth` warns and
  continues without one (downloads just may be rate-limited). Set `HF_TOKEN` for speed.
- `skfda` is **not** a dependency (FPCA is done via numpy SVD); the PyPI name would be
  `scikit-fda` if ever needed.
- `accelerate` is required for `device_map="auto"` and is in the deps.
- The attention-extraction hooks capture the **prefill** pass only and offload to CPU.
- The crossbar computes each head's projector once and reuses it; the 10 log-D positions
  are filled by copy (no recomputation).

## Non-blocking warnings you can ignore

- `torch_dtype is deprecated! Use dtype instead!` — cosmetic; still works on the pinned
  `transformers>=4.45` range.
- `rope_parameters['original_max_position_embeddings']` — transformers-internal config note.
- `unauthenticated requests to the HF Hub` — set `HF_TOKEN` (step 3) to silence it.
