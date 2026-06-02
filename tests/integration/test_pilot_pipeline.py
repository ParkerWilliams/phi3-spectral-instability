"""End-to-end integration test for the US1 pilot pipeline (T047).

Marked ``@pytest.mark.gpu`` because it loads real Phi-3-mini-128k-instruct
and runs a forward pass on each of 6 toy events. To run:

    PHI3_RUN_GPU_TESTS=1 pytest tests/integration/test_pilot_pipeline.py

Without ``PHI3_RUN_GPU_TESTS=1``, the GPU marker auto-skips (see
``tests/conftest.py::pytest_collection_modifyitems``).
"""

from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

import pytest

# Light imports first (no torch/transformers); heavy imports inside tests
# so collection works even when those packages aren't installed.
from phi3geom.dataset.generation import FACTS, TEMPLATES, generate_event
from phi3geom.dataset.types import BIN_IDS, BIN_RANGES, BinId, DocQAEvent
from phi3geom.extraction.pipeline import PROMPT_TEMPLATE_SHA256


def _toy_event(bin_id: BinId, rng: random.Random) -> DocQAEvent:
    template = TEMPLATES[0]  # birthplace
    fact = FACTS[template.template_id][0]
    lo, _ = BIN_RANGES[bin_id]
    return generate_event(
        template=template,
        fact=fact,
        target_evidence_distance_words=max(20, lo // 8),
        distractor_density=0.3,
        prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
        bin_id=bin_id,
        rng=rng,
    )


@pytest.mark.gpu
def test_pilot_pipeline_end_to_end(tmp_path: Path) -> None:
    """Run the full extraction pipeline on a 6-event toy dataset (1 per bin).

    Verifies:

    - Real Phi-3-mini-128k-instruct loads.
    - Forward passes complete without raising.
    - F.npy + D.npy + F_summary.npy + headers are written for each event.
    - The event gains a non-empty ``model_generation`` and a determined
      ``is_fail`` after the pipeline.
    """
    import torch  # noqa: F401  (asserts torch is available)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from phi3geom.extraction.pipeline import run_event_extraction
    from phi3geom.scripts.pin_model_revision import (
        DEFAULT_MODEL_ID,
        fetch_revision_sha,
    )
    from phi3geom.storage.cache import read_F

    model_id = DEFAULT_MODEL_ID
    revision = fetch_revision_sha(model_id)
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, revision=revision,
        torch_dtype=torch.float16, device_map="auto",
        attn_implementation="eager",
    )
    model.eval()

    rng = random.Random(0)
    cache_root = tmp_path / "cache"
    manifest_sha = "a" * 64
    code_sha = "b" * 40

    for bin_id in BIN_IDS:
        event = _toy_event(bin_id, rng)
        result = run_event_extraction(
            event, model, tokenizer,
            k_attn=16,
            manifest_sha256=manifest_sha,
            code_commit_sha=code_sha,
            cache_root=cache_root,
        )
        # Cache files written
        cache_dir = cache_root / event.event_id[:2] / event.event_id
        assert (cache_dir / "F.npy").is_file()
        assert (cache_dir / "F.header.json").is_file()
        assert (cache_dir / "D.npy").is_file()
        assert (cache_dir / "F_summary.npy").is_file()
        assert (cache_dir / "event.json").is_file()
        # Model output populated
        assert result.event.model_generation != ""
        assert isinstance(result.event.is_fail, bool)
        # SHA-verified read works
        F = read_F(
            event.event_id, expected_manifest_sha256=manifest_sha, cache_root=cache_root
        )
        assert F.shape == (256, 32, 32, 7)
        assert isinstance(result.event.evidence_distance_tokens, int)
        assert result.event.evidence_distance_tokens > 0

    # Cleanup (tmp_path is automatic, but explicitly ensure no leaks)
    shutil.rmtree(cache_root, ignore_errors=True)


def test_pilot_reports_writeable(tmp_path):
    """Report writers run end-to-end on a synthetic pooled fit (no GPU)."""
    import numpy as np
    from phi3geom.analysis.pooled_detector import fit_pooled_detector
    from phi3geom.dataset.types import CEMStratum
    from phi3geom.reporting.pilot_reports import write_pilot_summary

    rng = random.Random(0)
    events = [_toy_event(b, rng) for b in BIN_IDS]
    from dataclasses import replace
    events = [replace(e, model_generation="x", is_fail=(i % 2 == 0),
                      evidence_distance_tokens=200 + 100 * i)
              for i, e in enumerate(events)]

    n = 240
    gen = np.random.default_rng(0)
    labels = np.zeros(n, dtype=bool); labels[::2] = True
    feats = gen.standard_normal((n, 7)).astype(np.float64); feats[labels, 0] += 3.0
    distances = gen.integers(20, 3000, size=n)
    doc_lengths = gen.integers(100, 2000, size=n)
    fit = fit_pooled_detector(feats, labels, random_state=0, n_bootstrap=50)

    strata_by_bin = {b: [CEMStratum(b, "birthplace", "low", "1", 60, 60, 50)] for b in BIN_IDS}
    paths = write_pilot_summary(
        detector_fit=fit, feature_matrix=feats, labels=labels,
        distances=distances, doc_lengths=doc_lengths,
        strata_by_bin=strata_by_bin, wall_time_sec=3600.0 * 8,
        gpu_hours_estimate=8.0, n_events=n, matched_events=events,
        random_state=0, out_dir=tmp_path,
    )
    for name, p in paths.items():
        assert p.is_file(), f"{name} not written"
    headline = json.loads((tmp_path / "pooled_auroc.json").read_text())
    assert headline["auroc"] == fit.auroc
