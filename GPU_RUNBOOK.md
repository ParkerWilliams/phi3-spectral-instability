# Running phi3geom on a fresh GPU box (any cloud)

End-to-end runbook for cloning, validating, and running the pilot on a fresh GPU
instance. Tested on RunPod and DigitalOcean; works on any provider that gives you
SSH + a CUDA GPU. Branch: `main`.

> **For long runs / scarce availability — read §6a first.** The resilient flow
> checkpoints reduced cache + log to a git experiment branch every N events, so
> a pod death/preemption costs nothing: spin up a new pod, run the same command,
> resume.

## 0. Instance choice

This workload's bottleneck is **CPU**, not GPU — per-head SVDs and the crossbar
saturate vCPUs while the GPU sits mostly idle. So pick by **vCPU count + RAM +
availability**, not premium GPU.

| Phase | GPU | Other |
|-------|-----|-------|
| Validation + pilot (steps 4–6) | **≥16 GB VRAM** is enough — Phi-3-mini loads ~8 GB at fp16. Any of: RTX 3090, L4, RTX 4000/5000 Ada, A40, A100, H100 — take whatever's in stock. | **8+ vCPUs**, **32 GB+ RAM**, **~60 GB disk** |
| Full study (B5/B6 at 2048–4096 tokens) — **deferred in v1** | 48–80 GB (A6000 / A100 / H100); eager attention materializes `(32 heads, T, T)` per layer | 64 GB RAM, ~120–150 GB disk |

Provider notes:

| Provider | What to look for |
|---|---|
| **RunPod** | Pick a **PyTorch template** (torch + CUDA pre-installed; saves a ~5 GB torch download). Attach a **network volume** for `/workspace` if you want disk-level persistence in addition to the git checkpoint. |
| **DigitalOcean** | GPU droplets (RTX 4000 Ada, L40S, H100, MI300X). Use a **Volume** for the cache root if you want disk-level persistence; otherwise rely on §6a's git checkpoint. |
| **Lambda / Vast / Hyperstack / etc.** | Whatever's cheap and has ≥16 GB GPU + 8+ vCPUs. The resilient flow makes interruptible/spot instances safe. |

## 1. Clone + checkout main

```bash
git clone https://github.com/ParkerWilliams/phi3-spectral-instability.git
cd phi3-spectral-instability
git checkout main    # IMPORTANT: repo default is `master`, which does NOT have the v2.0.0 work
```

If the repo is private, clone with a token:

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

If the box has **no** torch (plain Ubuntu image), drop `--system-site-packages`
and install the CUDA build of torch first (match `cu121`/`cu124` to the box's CUDA):

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install -e ".[dev]"
```

## 3. HuggingFace auth + pre-download the model

```bash
export HF_TOKEN=hf_...                                          # optional, just faster
huggingface-cli download microsoft/Phi-3-mini-128k-instruct     # ~7.6 GB, one-time
```

The model is public; the HF token only speeds downloads / silences rate-limit warnings.

## 4. Verify the numerical seam (CPU-only, ~1 min)

```bash
python -m pytest tests/unit tests/contract
```

Expect **all pass** — **270 passed, 1 skipped** without torch; on a PyTorch template
the torch hooks test runs too (**271 passed, 0 skipped**). This command does not
collect `tests/integration/` — the GPU end-to-end test runs in step 5.

## 5. GPU integration test + per-event timing (the real validation)

```bash
time PHI3_RUN_GPU_TESTS=1 python -m pytest tests/integration/test_pilot_pipeline.py -s
```

**Expect 2 passed**: the GPU end-to-end test (6 toy events on real Phi-3) plus a
CPU report-writer smoke test (no GPU marker, always runs). The `time` prefix gives
total wall clock — **divide by 6 for per-event seconds** (the report test is
near-instant). Multiply by ~900 for the full-pilot estimate.

This test prints no per-event progress, so it can look frozen. Confirm it's alive
in another shell:

```bash
top -bn1 | grep -m1 python                       # python R, CPU well above 100%
find /tmp/pytest-of-root -name 'F.npy' | wc -l   # rough completed-event count
```

CPU-bound is expected — `nvidia-smi` shows GPU mostly idle while a CPU core is
pegged. That's the spectral/crossbar math, not a hang.

## 6. The pilot (only after step 5 passes)

The pilot processes ~900 candidate events and at the prior measured rate
(~345 s/event) takes ~3 days wall-clock. Two flows; **pick §6a for any run
where you can't 100% trust the box to stay alive that long**.

### 6a. Resilient flow (recommended for long runs / scarce availability)

Every N events the pilot pushes the **reduced** cache data (F_summary.npy +
event.json, ~36 KB/event ≈ ~32 MB total over the full pilot) and the run log
to an experiment branch on GitHub. If the pod dies, spin up a new pod, run the
**same command**, and `restore_from_branch` + resume-from-cache pick up where
you left off.

What's pushed: the small data the v2.0.0 pooled detector reads. The big tensors
(`F.npy` ~14.7 MB, `D.npy`) stay local — they're needed only for deferred
per-position attribution and FDA β(ℓ) work, not the pooled headline.

Required: a fine-grained **GitHub PAT** with `contents: read+write` on this repo.

> **Use `--adversariality sibling_entity` unless you have a reason not to.** The
> 2026-06-04 pilot run with the default `none` policy got a **0.25% failure rate**
> (2/796 events) — Phi-3 is too accurate on the synthetic templates with random
> distractors for CEM matching or the pooled detector to be defined. The
> `sibling_entity` policy injects same-predicate, different-subject sentences
> ("Berlin is the capital of Germany" next to the correct evidence), forcing the
> model to actually distinguish rather than pattern-match.

```bash
export GITHUB_TOKEN=ghp_yourtokenhere
mkdir -p reports
# Convention for branch names: experiment/pilot/<utc-date>[-<host>]
nohup bash scripts/run_pilot_resilient.sh \
    --experiment-branch experiment/pilot/$(date -u +%Y-%m-%d) \
    --adversariality sibling_entity --n-adversarial 5 \
    > reports/pilot_run.log 2>&1 &
tail -f reports/pilot_run.log
```

On a new pod after a death/preemption: do steps 1–3 again, then re-run
**exactly the same** command. You'll see lines like:

```
[pilot] restored 175 events from branch experiment/pilot/2026-06-02
[pilot] 1/900 (bin B1) RESUMED from cache
...
[pilot] 176/900 (bin B2) ...     ← work resumes here
```

Optional flags:
- `--checkpoint-every 25` — push cadence (default 25).
- `--with-ricci` — enables US2 Forman-Ricci feature path.

### 6b. Basic flow (no checkpoint; one shot)

Use only when you're confident the box will stay up for the whole run (e.g., a
reserved on-demand box, or a small `--n-per-bin` smoke run). A pod death loses
all progress.

```bash
mkdir -p reports
nohup bash scripts/run_pilot.sh > reports/pilot_run.log 2>&1 &
tail -f reports/pilot_run.log
```

### 6c. Smoke pilot (~1 hr, useful before the full run)

```bash
nohup bash scripts/run_pilot.sh --n-per-bin 30 --target-per-class 10 \
    > reports/smoke_run.log 2>&1 &
tail -f reports/smoke_run.log
```

### Outputs

All flows write `reports/pilot/`:

- `pooled_auroc.json` — **headline**: the pooled, distance-blind detector's AUROC
  + 95% CI + `beats_chance` (constitution v2.0.0, Principle III).
- `distance_diagnostic.json` — the same detector's AUROC sliced by *measured*-
  distance bin (diagnostic only — never assists the detector; shows where it degrades).
- `confound_audit.json` — a length+distance-only logistic's AUROC vs the geometry
  detector, with an `is_suspicious` flag if geometry looks like a length/position proxy.
- `cem_yield.json` — per-bin CEM match yield (flags compromised bins).
- `runtime.json` — wall time + GPU-hour estimate.
- `handcheck_sample.jsonl` — 50 events for manual SC-007 verification.

**Pilot success criterion (constitution v2.0.0):** pooled AUROC whose 95% CI lower
bound is > 0.5 — i.e. `"beats_chance": true` in `pooled_auroc.json` — within the
≤72 GPU-hr budget. Distance bins are now a **post-hoc diagnostic**, so the old
per-bin SC-004 gate (≥5/6 bins ≥50% CEM yield) and the B6 RoPE-wrap check are
**deferred** with the B5/B6 long-context work — the 201-fact corpus reaches only
B1–B4. See `docs/superpowers/specs/2026-05-28-distance-blind-failure-detector-design.md`.

### Pulling results back to your laptop

```bash
# On the pod:
cd /path/to/phi3-spectral-instability
tar czf pilot-results.tar.gz reports/ dataset/
# On your laptop (pick one):
runpodctl receive <code>                                # if `runpodctl send pilot-results.tar.gz` on pod
scp -P <port> root@<host>:/.../pilot-results.tar.gz .   # if you have SSH details
```

In resilient mode, the small reports + log + reduced cache are **also** safely
on the experiment branch in GitHub — `git checkout <branch>` to pull them via git.

## 7. Full study (after pilot validates)

```bash
# k_attn sweep first (writes reports/pilot/k_attn_sweep.json):
python -m phi3geom.scripts.kattn_sweep
# then the full 4800-event study:
bash scripts/run_full_study.sh
```

> The full-study scripts (`run_analysis.py`, `full_study_main.py`) still use the
> per-bin path. Reconciling them to the pooled detector is deferred future work.

## Reproducibility check (SC-005, run on a second box)

```bash
bash scripts/regenerate_dataset.sh   # regenerates from the manifest; targets ≥99% event_id agreement
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
- Resume-from-cache treats `F_summary.npy + event.json` as the resume contract; events
  with only one of the two are re-extracted. Skipped events (lookback-window failures
  on short docs) leave no cache and are retried each pod — they'll fail the same way.

## Non-blocking warnings you can ignore

- `torch_dtype is deprecated! Use dtype instead!` — cosmetic; still works on the pinned
  `transformers>=4.45` range.
- `rope_parameters['original_max_position_embeddings']` — transformers-internal config note.
- `unauthenticated requests to the HF Hub` — set `HF_TOKEN` (step 3) to silence it.
- `The following generation flags are not valid and may be ignored: ['temperature']` —
  greedy decoding ignores temperature; output is deterministic. Don't change the
  generation config (it's part of `GENERATION_CONFIG_SHA256` in the manifest).
