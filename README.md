# phi3geom

Phi-3 attention-geometry as a leading indicator of DocQA failures (v1 study).

Extends the [DCSBM spectral-instability work][1] to `microsoft/Phi-3-mini-128k-instruct`:
build a balanced 4800-event DocQA dataset stratified across 6 evidence-distance bins, extract
per-(token, layer, head) spectral and Forman-Ricci features, and recover per-bin AUROC plus
β(ℓ) coefficient functions identifying discriminative depths.

## Status

Spec-Kit artifact under `specs/001-phi3-attention-geometry-v1/`. Implementation in progress.

- **Constitution**: `.specify/memory/constitution.md` (v1.0.0, ratified 2026-05-18)
- **Spec**: `specs/001-phi3-attention-geometry-v1/spec.md`
- **Plan**: `specs/001-phi3-attention-geometry-v1/plan.md`
- **Quickstart**: `specs/001-phi3-attention-geometry-v1/quickstart.md`

## Quick start

See `specs/001-phi3-attention-geometry-v1/quickstart.md`.

```bash
git clone git@github.com:ParkerWilliams/phi3-spectral-instability.git
cd phi3-spectral-instability
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/unit/          # parity tests vs DCSBM reference (requires the pinned dcsbm-transformer)
bash scripts/run_pilot.sh   # 600-event pilot; needs CUDA GPU + HF auth
```

## License

MIT — see `pyproject.toml`.

[1]: https://parkerwilliams.org/rambling/2026/3/21/spectral-instability-in-attention-matrices-as-a-leading-indicator-of-transformer-rule-violations
