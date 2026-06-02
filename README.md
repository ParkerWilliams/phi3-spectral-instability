# phi3geom

Phi-3 attention-geometry as a leading indicator of DocQA failures (v1 study).

Extends the [DCSBM spectral-instability work][1] to `microsoft/Phi-3-mini-128k-instruct`:
build a balanced DocQA dataset spanning a range of evidence distances, extract per-(token, layer,
head) spectral and Forman-Ricci features, and train a single **distance-blind** detector — asking
whether attention-geometry separates DocQA failures from successes "in the wild" (Principle III,
constitution v2.0.0). Evidence distance is a secondary diagnostic — where does the detector
degrade? — not a stratification gate; β(ℓ) depth attribution is a follow-on.

## Status

Spec-Kit artifact under `specs/001-phi3-attention-geometry-v1/`. Implementation in progress.

- **Constitution**: `.specify/memory/constitution.md` (v2.0.0, amended 2026-05-28)
- **Spec**: `specs/001-phi3-attention-geometry-v1/spec.md`
- **Plan**: `specs/001-phi3-attention-geometry-v1/plan.md`
- **Quickstart**: `specs/001-phi3-attention-geometry-v1/quickstart.md`

## Quick start

See `specs/001-phi3-attention-geometry-v1/quickstart.md`.

See **[GPU_RUNBOOK.md](GPU_RUNBOOK.md)** for the full fresh-GPU-box runbook (works on
any cloud — RunPod, DigitalOcean, Lambda, Vast, etc.; includes a resilient
checkpoint+resume flow for long runs on scarce/interruptible boxes). Short version:

```bash
git clone https://github.com/ParkerWilliams/phi3-spectral-instability.git
cd phi3-spectral-instability
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/unit tests/contract   # analytic + contract tests; should all pass
bash scripts/run_pilot.sh          # 600-event pilot; needs a CUDA GPU (HF token optional)
```

## License

MIT — see `pyproject.toml`.

[1]: https://parkerwilliams.org/rambling/2026/3/21/spectral-instability-in-attention-matrices-as-a-leading-indicator-of-transformer-rule-violations
