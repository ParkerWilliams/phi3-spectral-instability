"""Benchmark gate (SP-0, T051) — UNVALIDATED (pod).

Measures REAL per-event time, peak GPU memory, and on-disk bundle size per
``(model, context-bucket)`` under full rich capture, and derives the run scale, the
stored-attention layer subset `S`, and the long-context N. Replaces all estimates
(the project's measure-don't-estimate rule). torch + a model + a corpus required.

⚠ Not runnable on a CPU-only box. Validate on the pod; watch ``nvidia-smi`` (the v1
OOM fix is reasoned, not GPU-validated).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


def _dir_size_mb(path: Path) -> float:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return total / 1e6


def benchmark_model(
    model: Any, tokenizer: Any, records: list, *, model_id: str, cache_root: Path,
    attn_mode: str = "eager",
) -> dict:
    """Time ``run_capture`` over a handful of events; report time/mem/disk."""
    import torch

    from phi3geom.extraction.capture import run_capture

    per_event = []
    for rec in records:
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        t0 = time.perf_counter()
        run_capture(
            model, tokenizer, rec, cache_root=cache_root, capture_version="2.0.0",
            model_id=model_id, revision_sha="bench", manifest_sha256="bench",
            code_commit_sha="bench", k_samples=2, attn_mode=attn_mode,
        )
        dt = time.perf_counter() - t0
        peak = (torch.cuda.max_memory_allocated() / 1e9) if torch.cuda.is_available() else 0.0
        per_event.append({"sec": dt, "peak_gb": peak})
    n = max(1, len(per_event))
    return {
        "model_id": model_id,
        "n_events": len(per_event),
        "sec_per_event": sum(e["sec"] for e in per_event) / n,
        "peak_mem_gb": max((e["peak_gb"] for e in per_event), default=0.0),
        "disk_mb_per_event": _dir_size_mb(Path(cache_root)) / n,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SP-0 benchmark gate")
    ap.add_argument("--model", required=True)
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--attn-mode", choices=("eager", "sdpa_selective"), default="eager")
    ap.add_argument("--cache-root", default="cache/benchmark")
    ap.add_argument("--out", default="reports/sp0/benchmark.json")
    args = ap.parse_args(argv)

    import torch  # noqa: F401  (fail fast off-pod)
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from phi3geom.dataset.adapters import hotpotqa

    attn_impl = "sdpa" if args.attn_mode == "sdpa_selective" else "eager"
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, attn_implementation=attn_impl, torch_dtype="bfloat16", device_map="auto"
    )
    records = list(hotpotqa.iter_events(limit=args.n, tokenizer=tok))
    report = benchmark_model(
        model, tok, records, model_id=args.model, cache_root=Path(args.cache_root),
        attn_mode=args.attn_mode,
    )
    report["attn_mode"] = args.attn_mode

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
