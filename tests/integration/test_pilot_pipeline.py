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
        # Model output populated
        assert result.event.model_generation != ""
        assert isinstance(result.event.is_fail, bool)
        # SHA-verified read works
        F = read_F(
            event.event_id, expected_manifest_sha256=manifest_sha, cache_root=cache_root
        )
        assert F.shape == (256, 32, 32, 7)

    # Cleanup (tmp_path is automatic, but explicitly ensure no leaks)
    shutil.rmtree(cache_root, ignore_errors=True)


@pytest.mark.gpu
def test_pilot_reports_writeable(tmp_path: Path) -> None:
    """Pilot report writers don't require a forward pass — just data structures.

    This test exercises the report-writing code path without invoking Phi-3,
    so it can be useful for catching JSON-schema regressions early. Still
    marked @pytest.mark.gpu to keep it grouped with the other integration
    test for run ordering.
    """
    from phi3geom.analysis.types import PerRegimeCompositeFit
    from phi3geom.dataset.types import CEMStratum
    from phi3geom.geometry import FEATURE_NAMES
    from phi3geom.reporting.pilot_reports import write_pilot_summary
    import numpy as np

    rng = random.Random(0)
    events = [_toy_event(b, rng) for b in BIN_IDS]
    # Fill in placeholder model output so handcheck_sample can serialize.
    from dataclasses import replace
    events = [replace(e, model_generation="x", is_fail=False) for e in events]

    fits = {
        b: PerRegimeCompositeFit(
            bin_id=b,
            feature_names=FEATURE_NAMES,
            coefficients=np.zeros(7, dtype=np.float64),
            intercept=0.0,
            auroc=0.82,
            auroc_ci_lower=0.78,
            auroc_ci_upper=0.86,
            n_events_train=80,
            n_events_held_out=20,
        )
        for b in BIN_IDS
    }
    strata_by_bin: dict[BinId, list[CEMStratum]] = {
        b: [CEMStratum(b, "birthplace", "low", "1", 60, 60, 50)] for b in BIN_IDS
    }
    paths = write_pilot_summary(
        fits=fits,
        strata_by_bin=strata_by_bin,
        wall_time_sec=3600.0 * 50,
        gpu_hours_estimate=50.0,
        n_events=600,
        matched_events=events,
        out_dir=tmp_path,
    )
    for name, p in paths.items():
        assert p.is_file(), f"{name} not written"
    auroc = json.loads((tmp_path / "per_bin_auroc.json").read_text())
    assert set(auroc.keys()) == set(BIN_IDS)
    for bin_id in BIN_IDS:
        assert auroc[bin_id]["auroc"] == 0.82
