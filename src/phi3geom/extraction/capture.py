"""v2 rich-capture pass (SP-0, T017/T016/T018/T063) — UNVALIDATED (pod).

One forward pass per ``(model, corpus, event)`` → the ``CaptureBundle``:
- reuses the v1 ``Phi3ExtractionHook`` for per-head Q/K/V + ``o_proj`` capture and
  adds ``output_hidden_states`` / ``output_attentions`` (eager) for the residual
  stream and post-softmax attention;
- computes the in-pass reductions ON DEVICE (``extraction.gpu_reductions``, which
  mirror the tested CPU primitives) — store the reduction, never the raw cloud /
  ``H×T`` blocks, and never transfer the multi-GB attention to host;
- generates K+1 samples (``extraction.generation``) and writes the bundle via
  ``storage.bundle_cache``.

⚠ NOT runnable on a CPU-only box (no torch/model/eager attention). torch is imported
lazily; the package still imports without it. Validate on the pod —
``tests/integration/test_capture_pipeline_v2.py`` is skip-guarded. The Phi-3 MVP path
is wired here; the GQA/Gemma-2 adapters (research.md R1.2/R1.3) are the documented
fan-out before a multi-model run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import numpy as np

from phi3geom.dataset.labeling import make_label
from phi3geom.dataset.types import DocQAEventRecord
from phi3geom.extraction.adapters.registry import resolve_adapter
from phi3geom.extraction.generation import generate_samples
from phi3geom.extraction.hooks import Phi3ExtractionHook
from phi3geom.extraction.pipeline import build_prompt
from phi3geom.extraction.gpu_reductions import (
    HIDDEN_WINDOW,
    interhead_surface_gpu,
    token_cloud_surface_gpu,
)
from phi3geom.storage import bundle_cache


def run_capture(
    model: Any,
    tokenizer: Any,
    record: DocQAEventRecord,
    *,
    cache_root: str | Path,
    capture_version: str,
    model_id: str,
    revision_sha: str,
    manifest_sha256: str,
    code_commit_sha: str,
    k_samples: int = 10,
    intervention: Callable[[int, Any], Any] | None = None,
) -> dict:
    """Capture one event end-to-end and write its bundle. Returns the label dict.

    ``intervention`` is the SP-3 reusable surface: if given, it is invoked per decoder
    layer as ``intervention(layer_idx, layer_output)`` via a forward hook (SP-0 ships
    the surface; SP-3 supplies the patching logic).
    """
    import torch

    device = next(model.parameters()).device
    prompt = build_prompt(record.document, record.question)
    enc = tokenizer(prompt, return_tensors="pt").to(device)
    input_ids = enc["input_ids"]
    prompt_len = int(input_ids.shape[1])
    answer_pos = prompt_len - 1
    adapter = resolve_adapter(model, model_id=model_id, revision_sha=revision_sha, tokenizer_id=model_id)
    descriptor = adapter.describe()

    handles = []
    if intervention is not None:
        inner = getattr(model, "model", model)
        for li, layer in enumerate(getattr(inner, "layers", [])):
            handles.append(
                layer.register_forward_hook(
                    lambda _m, _i, out, _li=li: intervention(_li, out)
                )
            )
    span = record.evidence_spans[0] if record.evidence_spans else None
    try:
        with Phi3ExtractionHook(model) as hook, torch.no_grad():
            outputs = model(
                input_ids,
                output_hidden_states=True,
                output_attentions=True,
                use_cache=False,
            )
            # Keep hidden states / attention ON DEVICE; reduce on the GPU and move
            # only the small slices + reduced surfaces to host (avoids the multi-GB
            # full-attention transfer and the CPU SVD/eigen bottleneck).
            hs = [h[0] for h in outputs.hidden_states]   # (L+1) × (T, d) on device
            at = [a[0] for a in outputs.attentions]       # (L)   × (H, T, T) on device
            win_lo = max(0, answer_pos - HIDDEN_WINDOW)
            hidden_answer_pos = (
                torch.stack([h[answer_pos] for h in hs]).float().cpu().numpy().astype(np.float16)
            )
            hidden_window = (
                torch.stack([h[win_lo : answer_pos + 1] for h in hs], dim=1)
                .float().cpu().numpy().astype(np.float16)
            )
            attn_rows = (
                torch.stack([a[:, answer_pos, :] for a in at]).float().cpu().numpy().astype(np.float16)
            )
            answer_logits = outputs.logits[0, answer_pos].float().cpu().numpy().astype(np.float16)
            qkv_per_head = adapter.capture_qkv(hook.captures, answer_pos)  # (3, L, H, d_head)
            token_cloud = token_cloud_surface_gpu(hs)          # on-device SVD → (L+1, k+6) fp32
            interhead = interhead_surface_gpu(at, answer_pos, span)  # on-device → (n_t, L, K) fp32
        del outputs
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    finally:
        for hd in handles:
            hd.remove()

    # Generation + label.
    samples = generate_samples(model, tokenizer, input_ids, k=k_samples)
    greedy = next(s for s in samples if s["is_greedy"])
    label = make_label(greedy["text"], list(record.gold_aliases), record.is_answerable)

    # Persist.
    kw = dict(
        capture_version=capture_version, model_id=model_id, corpus_id=record.corpus_id,
        event_id=record.event_id,
    )
    wk = dict(revision_sha=revision_sha, manifest_sha256=manifest_sha256, code_commit_sha=code_commit_sha)
    for name, arr in (
        ("hidden_answer_pos", hidden_answer_pos),
        ("hidden_window", hidden_window),
        ("attn_rows_answer_pos", attn_rows),
        ("token_cloud_spectra", token_cloud),
        ("interhead_drift_surface", interhead),
        ("qkv_per_head", qkv_per_head),
        ("answer_logits", answer_logits.astype(np.float16)),
    ):
        bundle_cache.write_array(cache_root, name=name, array=arr, **kw, **wk)
    label_d = {
        "class_4way": label.class_4way, "is_hallucination": label.is_hallucination,
        "em_match": label.em_match, "token_f1": label.token_f1,
        "abstained": label.abstained, "abstention_evidence": label.abstention_evidence,
    }
    bundle_cache.write_json(cache_root, name="label", obj=label_d, **kw)
    bundle_cache.write_json(cache_root, name="samples", obj=samples, **kw)
    bundle_cache.write_json(
        cache_root, name="meta",
        obj={"model_id": model_id, "corpus_id": record.corpus_id,
             "event_id": record.event_id, "capture_version": capture_version,
             "descriptor": {
                 "d_model": descriptor.d_model, "n_layers": descriptor.n_layers,
                 "n_heads": descriptor.n_heads, "n_kv_heads": descriptor.n_kv_heads,
                 "head_dim": descriptor.head_dim, "n_rep": descriptor.n_rep,
                 "tied_embeddings": descriptor.tied_embeddings,
                 "revision_sha": revision_sha,
             }}, **kw,
    )
    bundle_cache.write_json(
        cache_root, name="event",
        obj={"event_id": record.event_id, "corpus_id": record.corpus_id,
             "question": record.question, "is_answerable": record.is_answerable,
             "gold_aliases": list(record.gold_aliases),
             "evidence_spans": [list(s) for s in (record.evidence_spans or [])],
             "provenance": record.provenance}, **kw,
    )
    return label_d
