"""v2 rich-capture pass (SP-0, T017/T016/T018/T063) — UNVALIDATED (pod).

One forward pass per ``(model, corpus, event)`` → the ``CaptureBundle``:
- reuses the v1 ``Phi3ExtractionHook`` for per-head Q/K/V + ``o_proj`` capture and
  adds ``output_hidden_states`` / ``output_attentions`` (eager) for the residual
  stream and post-softmax attention;
- computes the in-pass reductions with the *tested* CPU primitives
  (``geometry.spectral.token_cloud_spectrum`` and
  ``geometry.interhead.cell_summary``) — store the reduction, never the raw cloud /
  ``H×T`` blocks;
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
from phi3geom.extraction.generation import generate_samples
from phi3geom.extraction.hooks import Phi3ExtractionHook
from phi3geom.extraction.pipeline import build_prompt
from phi3geom.geometry.interhead import CELL_FEATURES, cell_summary
from phi3geom.geometry.spectral import token_cloud_spectrum
from phi3geom.storage import bundle_cache

# Log-spaced query offsets back from the answer position (design §4/§5).
SAMPLED_QUERY_OFFSETS: tuple[int, ...] = (0, 1, 2, 4, 8, 16, 32, 64, 128, 256)
HIDDEN_WINDOW: int = 16  # backward token window stored around the answer position
K_EIG: int = 32  # token-cloud eigenvalues kept per layer
_SPECTRA_STATS = ("gamma", "sigma_sq", "mp_edge_lower", "mp_edge_upper", "n_spikes", "lambda_max")


def _interhead_surface(attentions: list[np.ndarray], answer_pos: int, span) -> np.ndarray:
    """In-pass S(t,ℓ): cell_summary at each sampled query × layer → (n_t, L, K)."""
    L = len(attentions)
    queries = sorted({max(0, answer_pos - off) for off in SAMPLED_QUERY_OFFSETS})
    if span is not None:
        queries = sorted(set(queries) | {span[0], span[1]})
    K = len(CELL_FEATURES) + 1  # + evidence_coverage slot (NaN when no span)
    surface = np.full((len(queries), L, K), np.nan, dtype=np.float64)
    for ti, t in enumerate(queries):
        for ell in range(L):
            A = attentions[ell][:, t, :].astype(np.float64)  # (H, T)
            s = cell_summary(A, evidence_span=span)
            for fi, name in enumerate(CELL_FEATURES):
                surface[ti, ell, fi] = s[name]
            surface[ti, ell, len(CELL_FEATURES)] = s.get("evidence_coverage", np.nan)
    return surface


def _token_cloud_surface(hidden_states: list[np.ndarray]) -> np.ndarray:
    """Per-layer token-cloud spectrum + MP-fit stats → (L, K_EIG + len(stats))."""
    rows = []
    for h in hidden_states:
        out = token_cloud_spectrum(h.astype(np.float64), k=K_EIG)
        ev = np.zeros(K_EIG, dtype=np.float64)
        ev[: out["eigenvalues"].size] = out["eigenvalues"][:K_EIG]
        stats = np.array([out[s] for s in _SPECTRA_STATS], dtype=np.float64)
        rows.append(np.concatenate([ev, stats]))
    return np.stack(rows)


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

    handles = []
    if intervention is not None:
        inner = getattr(model, "model", model)
        for li, layer in enumerate(getattr(inner, "layers", [])):
            handles.append(
                layer.register_forward_hook(
                    lambda _m, _i, out, _li=li: intervention(_li, out)
                )
            )
    try:
        with Phi3ExtractionHook(model) as hook, torch.no_grad():
            outputs = model(
                input_ids,
                output_hidden_states=True,
                output_attentions=True,
                use_cache=False,
            )
        hidden = [h[0].float().cpu().numpy() for h in outputs.hidden_states]  # (L+1)×(T,d)
        attn = [a[0].float().cpu().numpy() for a in outputs.attentions]  # (L)×(H,T,T)
        answer_logits = outputs.logits[0, answer_pos].float().cpu().numpy()
        del outputs
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    finally:
        for hd in handles:
            hd.remove()

    span = record.evidence_spans[0] if record.evidence_spans else None

    # Bundle arrays (in-pass reductions via the tested CPU primitives).
    hidden_answer_pos = np.stack([h[answer_pos] for h in hidden]).astype(np.float16)
    lo = max(0, answer_pos - HIDDEN_WINDOW)
    hidden_window = np.stack([h[lo : answer_pos + 1] for h in hidden], axis=1).astype(np.float16)
    attn_rows = np.stack([a[:, answer_pos, :] for a in attn]).astype(np.float16)  # (L,H,T)
    token_cloud = _token_cloud_surface(hidden).astype(np.float32)
    interhead = _interhead_surface(attn, answer_pos, span).astype(np.float32)

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
             "event_id": record.event_id, "capture_version": capture_version}, **kw,
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
