"""Multi-model pilot / capture driver (SP-0, T054/T021) — UNVALIDATED (pod).

Iterates a corpus through ``run_capture`` for each model, collecting labels, and
reports per-corpus fail/hallucination balance and OOM skips. Used both as the
multi-model pilot (small N, ≥2 architectures) and the first-allocation capture run.

⚠ Not runnable on a CPU-only box (torch + models + datasets). Validate on the pod.
The corpus registry currently wires HotpotQA; SQuAD2 / closed-book / RULER adapters
are the documented fan-out.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

# Uniform-signature corpora (split/limit/tokenizer). RULER is invoked separately —
# it needs a generated-data path (`--data`), not the limit/tokenizer signature.
CORPORA = {
    "hotpotqa": "phi3geom.dataset.adapters.hotpotqa",
    "squad2": "phi3geom.dataset.adapters.squad2",
    "triviaqa_nq": "phi3geom.dataset.adapters.triviaqa_nq",
}


def _corpus_iter(corpus_id: str, *, limit: int, tokenizer: Any) -> Iterator:
    mod = __import__(CORPORA[corpus_id], fromlist=["iter_events"])
    return mod.iter_events(limit=limit, tokenizer=tokenizer)


def run_pilot(
    model: Any, tokenizer: Any, *, model_id: str, corpora: list[str],
    n_per_corpus: int, cache_root: Path,
) -> dict:
    from phi3geom.extraction.capture import run_capture

    report: dict[str, Any] = {"model_id": model_id, "corpora": {}, "oom_skips": 0}
    for corpus_id in corpora:
        classes: Counter = Counter()
        for rec in _corpus_iter(corpus_id, limit=n_per_corpus, tokenizer=tokenizer):
            try:
                label = run_capture(
                    model, tokenizer, rec, cache_root=cache_root, capture_version="2.0.0",
                    model_id=model_id, revision_sha="pilot", manifest_sha256="pilot",
                    code_commit_sha="pilot",
                )
                classes[label["class_4way"]] += 1
            except Exception as exc:  # noqa: BLE001 — surface OOM/skip in the report
                if "out of memory" in str(exc).lower():
                    report["oom_skips"] += 1
                else:
                    raise
        total = sum(classes.values()) or 1
        pos = classes["wrong-answer"] + classes["hallucination"]
        report["corpora"][corpus_id] = {
            "n": total, "class_4way": dict(classes), "fail_hallucination_rate": pos / total,
        }
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SP-0 v2 pilot / capture driver")
    ap.add_argument("--model", required=True)
    ap.add_argument("--corpora", nargs="+", default=["hotpotqa"])
    ap.add_argument("--n-per-corpus", type=int, default=40)
    ap.add_argument("--cache-root", default="cache")
    ap.add_argument("--out", default="reports/sp0/pilot.json")
    args = ap.parse_args(argv)

    import torch  # noqa: F401
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, attn_implementation="eager", torch_dtype="bfloat16", device_map="auto"
    )
    report = run_pilot(
        model, tok, model_id=args.model, corpora=args.corpora,
        n_per_corpus=args.n_per_corpus, cache_root=Path(args.cache_root),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
