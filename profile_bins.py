"""Per-bin extraction timing on real Phi-3, to size the pilot GPU-hour budget.

Loads the model once, times ``run_event_extraction`` on one toy event per bin
(B1 short .. B6 long), and projects the 600-event pilot cost against the
SC-004 budget of 72 GPU-hr. Streams one line per bin; Ctrl-C any time.

    PHI3_RUN_GPU_TESTS not required -- just run it on the GPU box:
    python profile_bins.py
"""

import random
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from phi3geom.dataset.generation import FACTS, TEMPLATES, generate_event
from phi3geom.dataset.types import BIN_IDS, BIN_RANGES
from phi3geom.extraction.pipeline import PROMPT_TEMPLATE_SHA256, run_event_extraction
from phi3geom.scripts.pin_model_revision import DEFAULT_MODEL_ID, fetch_revision_sha

PER_BIN = 100  # pilot = 600 events / 6 bins

rev = fetch_revision_sha(DEFAULT_MODEL_ID)
tok = AutoTokenizer.from_pretrained(DEFAULT_MODEL_ID, revision=rev)
model = AutoModelForCausalLM.from_pretrained(
    DEFAULT_MODEL_ID,
    revision=rev,
    torch_dtype=torch.float16,
    device_map="auto",
    attn_implementation="eager",
).eval()

rng = random.Random(0)
tmpl = TEMPLATES[0]
fact = FACTS[tmpl.template_id][0]
total = 0.0

print(f"{'bin':4} {'tok-range':11} {'s/event':>9} {'pilot GPU-hr':>13}", flush=True)
for b in BIN_IDS:
    lo, hi = BIN_RANGES[b]
    ev = generate_event(
        template=tmpl,
        fact=fact,
        target_evidence_distance_words=max(20, lo // 8),
        distractor_density=0.3,
        prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
        bin_id=b,
        rng=rng,
    )
    t0 = time.perf_counter()
    run_event_extraction(
        ev,
        model,
        tok,
        k_attn=16,
        manifest_sha256="a" * 64,
        code_commit_sha="b" * 40,
        cache_root=Path("/tmp/timing_cache"),
    )
    dt = time.perf_counter() - t0
    gpu_hr = dt * PER_BIN / 3600
    total += gpu_hr
    print(f"{b:4} {f'{lo}-{hi}':11} {dt:9.1f} {gpu_hr:13.1f}", flush=True)

print(
    f"\nProjected pilot (600 events): {total:.1f} GPU-hr  (SC-004 budget = 72)",
    flush=True,
)
