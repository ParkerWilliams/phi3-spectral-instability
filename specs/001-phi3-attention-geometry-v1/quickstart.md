# Quickstart: Phi-3 Attention-Geometry v1

**Audience**: A researcher (or future-self) who wants to reproduce the v1 pilot end-to-end on a
fresh machine.

**Time estimate**: ~4 hours human + 72 GPU-hours machine for the pilot. ~2 weeks elapsed for
the full study after pilot validation.

---

## 0. Preconditions

- Linux x86_64 with NVIDIA GPU (RTX 4090, A100, or H100). The pilot fits on a single 24 GB
  GPU. Cloud burst (H100 spot) is recommended for the full study.
- Python 3.11+.
- ~100 GB free disk on a local SSD.
- `git`, `aws-cli` (for S3 replication), and `huggingface-cli` available on PATH.
- HuggingFace authentication: `huggingface-cli login` with a token that has read access to
  `microsoft/Phi-3-mini-128k-instruct`.

---

## 1. Clone and set up the environment

```bash
git clone <this-repo> phi3
cd phi3
git checkout 001-phi3-attention-geometry-v1

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"   # Installs torch, transformers, skfda, GraphRicciCurvature,
                          #   sklearn, scipy, numpy, networkx, pandas, pytest, hypothesis
```

The `.[dev]` extra installs the DCSBM reference repo (pinned git ref) needed by parity tests.

Verify TDD-scope tests pass before doing anything else:

```bash
pytest tests/unit/ -x
pytest tests/contract/ -x
```

If any TDD test fails, **STOP**. Constitution Principle II is non-negotiable; the scientific
primitives must be parity-verified before generating data.

---

## 2. Pin the Phi-3 model revision

```bash
python -m phi3geom.scripts.pin_model_revision
# Writes the current HuggingFace revision SHA to dataset/manifest_header.json
# This is also done automatically by run_pilot.sh on first run.
```

The pin is recorded in `manifest_header.json` and cannot be silently overwritten; if you
re-run this command on a different day, it refuses to overwrite an existing pin without
`--force-repin` (which would invalidate the prior manifest).

---

## 3. Run the pilot (US1)

```bash
bash scripts/run_pilot.sh
```

This script does (driven by `src/phi3geom/dataset/generation.py` and
`src/phi3geom/extraction/pipeline.py`):

1. Generates 600 events (50 fail + 50 control × 6 bins), writing
   `dataset/manifest.jsonl` and `dataset/events.jsonl`.
2. For each event, runs one Phi-3 forward pass; extracts QKᵀ, AVWO, attention graph per
   atomic unit; writes `cache/{event_id_prefix}/{event_id}/F.npy` + headers.
3. Computes pairwise head-head Grassmannian distances; writes `D.npy`.
4. Fits a per-regime composite logistic on the spectral-only features (no Ricci yet) per bin;
   writes `reports/pilot/per_bin_auroc.json`.
5. Runs the `k_attn ∈ {8, 16, 32}` sweep on a 100-event subset; writes
   `reports/pilot/k_attn_sweep.json`. The winning `k_attn` is recorded in `manifest_header.json`.
6. Hand-verification setup: writes `reports/pilot/handcheck_sample.jsonl` with 50 events for
   you to manually mark correct/incorrect; compare to the automated `is_fail`.

**Expected outputs after a successful pilot**:
- `reports/pilot/per_bin_auroc.json` — 6 bin entries, each with `auroc`, `auroc_ci_lower`,
  `auroc_ci_upper`, and `n_events`.
- `reports/pilot/cem_yield.json` — per-bin CEM match yield.
- `reports/pilot/k_attn_sweep.json` — chosen `k_attn` + per-bin marginal AUROC gain.
- `reports/pilot/runtime.json` — end-to-end wall time and GPU-hours.

**Pilot pass criteria** (Spec SC-004):
- End-to-end runtime ≤ 72 GPU-hours.
- ≥5 of 6 bins achieve ≥50% CEM yield at ≤1.5× oversample.
- Hand-verification on the 50-event sample: 100% agreement with automated labels.
- B6 baseline does not appear discontinuous vs B5 in a way suggesting RoPE-wrap.

---

## 4. Integrate Forman-Ricci (US2)

After the pilot passes, the `k_attn` value is pinned. Run:

```bash
bash scripts/run_pilot.sh --with-ricci
```

This re-fits the per-regime composite with Forman-Ricci-token features added. Outputs:
`reports/pilot/per_bin_auroc_with_ricci.json` and `reports/pilot/ricci_marginal_gain.json`.

Decision point: the Forman-Ricci marginal AUROC gain is reported per bin. If marginal gain
is below 0.02 in ≥4 of 6 bins, downstream interpretation MUST be cautious; the writeup flags
this in §SC-001.

---

## 5. Run the full study (US3 + US4)

After both pilots pass:

```bash
bash scripts/run_full_study.sh
```

This generates 4800 events, caches all F/D tensors, fits per-regime composites and functional
logistic regressions per bin, and writes:

- `reports/full/per_bin_auroc.json` (headline FR-014 table).
- `reports/full/beta_layer_functions/{bin_id}_{edge_type}.json` (β(ℓ) per bin per head-graph).
- `reports/full/pooled_negative_control.json` (SC-003 evidence).
- `reports/full/discriminative_depths.md` (writeup of which layers carry signal per bin).

---

## 6. Reproducibility check (SC-005)

After the full study completes, verify on a SECOND machine:

```bash
git checkout <code_commit_sha_from_manifest_header>
bash scripts/regenerate_dataset.sh --manifest dataset/manifest_header.json
# This should produce identical event_ids and identical is_fail labels for ≥99% of events.
```

If the agreement is below 99%, halt and investigate; do not include the headline numbers in
any writeup until reproducibility is established.

---

## 7. Common failure modes

| Symptom | Likely cause | Resolution |
|---|---|---|
| `CacheStaleError` on `read_F` | Manifest changed since cache was written | Regenerate from current manifest or rewind manifest |
| `TypeError: expected float64` from spectral functions | Float32 input made it to the seam | Find the upstream `.astype(np.float32)` that's too early; fix it |
| `B1` failure rate < 5% with default policy | No adversarial distractors yet | Switch `adversariality_policy` for B1 in the manifest (research.md §11) and regenerate |
| Pilot runtime > 72 GPU-hours | Likely Forman-Ricci computation in the inner loop | Profile; possibly replace `GraphRicciCurvature` call with the hand-coded primitive (research.md §4) |
| `ImportError: cannot import pooled_negative_control from phi3geom.analysis.composite` | Working as intended (Constitution Principle III) | Import from `phi3geom.analysis.pooled_negative_control` |
| `ValueError: bin_id must be a single bin enum` | A pooled fit attempted through the per-regime API | Use `pooled_negative_control.fit` for SC-003 only; per-regime fits must be one bin at a time |

---

## 8. What to do when something is surprising

Per Constitution Principle V (Specification-Driven Research Workflow): any deviation from this
quickstart that is more than a typo fix or a single-file edit goes through the Spec Kit flow.
Open a brainstorm note in `docs/superpowers/specs/`, then `/speckit-specify` a new feature.
This includes: changing `k_grass` or `J`, expanding to >4096 token bins, adding GQA models,
adding head-graph Ricci.
