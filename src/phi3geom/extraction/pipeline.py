"""End-to-end extraction: prompt → forward pass → atomic features → cache write.

Wires together the spectral primitives, hooks, atomic-unit assembly,
crossbar, spine, lookback indexing, and cache writers into one
event-at-a-time function: ``run_event_extraction``.

The pilot driver (``scripts/pilot_main.py``) calls this for each event;
the full-study driver does the same at 8× scale.

Requires ``torch`` and ``transformers`` at runtime. Module imports
``transformers`` lazily inside the function so static analysis tools that
don't have transformers installed can still inspect this file.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from phi3geom.dataset.normalization import normalize_em
from phi3geom.dataset.types import DocQAEvent
from phi3geom.extraction.hooks import Phi3ExtractionHook, recover_qkt_avwo
from phi3geom.extraction.lookback import (
    LookbackOutOfBoundsError,
    d_lookback_absolute_indices,
    f_lookback_absolute_indices,
)
from phi3geom.geometry.atomic_unit import compute_atomic_unit_features
from phi3geom.geometry.ricci import build_attention_graph
from phi3geom.lattice.crossbar import (
    N_HEADS_DEFAULT,
    compute_pairwise_grassmannian,
    edges_to_dense,
)
from phi3geom.lattice.spine import compute_spine_curve
from phi3geom.storage.cache import (
    D_LOOKBACK_INDICES,
    F_SHAPE,
    F_SUMMARY_SHAPE,
    write_D,
    write_event_metadata,
    write_F,
    write_F_summary,
)

if TYPE_CHECKING:
    import torch

N_LAYERS_DEFAULT = 32

# Pinned prompt template (SHA256 recorded in the manifest header).
PROMPT_TEMPLATE = """<|system|>You are answering questions about the document below. Answer with only the answer, no preamble.<|end|>
<|user|>{document}

Question: {question}
Answer:<|end|>
<|assistant|>"""

PROMPT_TEMPLATE_SHA256 = hashlib.sha256(PROMPT_TEMPLATE.encode("utf-8")).hexdigest()

# Pinned generation config (SHA256 recorded in the manifest header).
GENERATION_CONFIG = {
    "temperature": 0,
    "do_sample": False,
    "max_new_tokens": 32,
    "stop_strings": ["\n", "<|end|>"],
}

GENERATION_CONFIG_SHA256 = hashlib.sha256(
    json.dumps(GENERATION_CONFIG, sort_keys=True).encode("utf-8")
).hexdigest()


@dataclass
class ExtractionResult:
    """Per-event output of ``run_event_extraction``."""

    event: DocQAEvent  # with model_generation, is_fail filled in
    cache_dir: Path
    n_tokens_total: int
    t_answer_commit: int


def build_prompt(document: str, question: str) -> str:
    """Construct the constrained ``Answer:``-prompted template."""
    return PROMPT_TEMPLATE.format(document=document, question=question)


def _token_len(tokenizer: "object", text: str) -> int:
    """Token length of ``text``. Handles HF's flat ``input_ids`` list (single
    string, no return_tensors), a nested ``[[...]]`` batch, or a tensor."""
    out = tokenizer(text)["input_ids"]
    if hasattr(out, "shape"):
        return int(out.shape[-1])
    if out and isinstance(out[0], (list, tuple)):
        return len(out[0])
    return len(out)


def measure_evidence_distance_tokens(event: DocQAEvent, tokenizer: "object") -> int:
    """Measure tokens from end-of-evidence to the answer-commit position.

    ``event.evidence_position_token_idx`` is a *word* index into the document
    (set at generation). We render the prompt preamble plus the document
    truncated at end-of-evidence, tokenize it, and subtract that length from
    the full prompt's token length. The shared preamble (and any BOS) cancels,
    so the result is the true evidence->answer token distance. Approximate to
    within tokenizer boundary effects — acceptable for a diagnostic (Principle
    III, v2.0.0: bin fidelity may be low).
    """
    words = event.document.split()
    n_words = max(0, min(event.evidence_position_token_idx, len(words)))
    doc_prefix = " ".join(words[:n_words])
    preamble = PROMPT_TEMPLATE.split("{document}")[0]
    prefix_len = _token_len(tokenizer, preamble + doc_prefix)
    full_len = _token_len(tokenizer, build_prompt(event.document, event.question))
    return full_len - prefix_len


def run_event_extraction(
    event: DocQAEvent,
    model: "torch.nn.Module",
    tokenizer: "object",
    *,
    k_attn: int,
    manifest_sha256: str,
    code_commit_sha: str,
    cache_root: Path,
    compute_ricci: bool = False,
    device: "str | torch.device | None" = None,
) -> ExtractionResult:
    """Run one event end-to-end: prompt → forward → features → cache.

    Args:
        event: A ``DocQAEvent`` from dataset generation. Fields
            ``model_generation``, ``model_generation_normalized``, ``is_fail``
            are populated by this function.
        model: Loaded ``transformers.Phi3ForCausalLM`` (or compatible).
        tokenizer: Loaded HuggingFace tokenizer.
        k_attn: Attention-graph sparsification cutoff.
        manifest_sha256: Recorded in cache headers.
        code_commit_sha: Recorded in cache headers.
        cache_root: Where to write F.npy/D.npy/F_summary.npy.
        compute_ricci: US1 baseline=False, US2+=True.
        device: torch device. Defaults to ``model``'s device.

    Returns:
        ``ExtractionResult`` with the labeled event and cache directory.
    """
    import torch

    if device is None:
        try:
            device = next(model.parameters()).device
        except StopIteration:
            device = "cpu"

    # 1. Build prompt + tokenize.
    prompt = build_prompt(event.document, event.question)
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    input_ids = inputs["input_ids"]
    prompt_len = input_ids.shape[1]

    # 2. Forward pass with hooks attached + output_attentions=True.
    with Phi3ExtractionHook(model) as hook:
        with torch.no_grad():
            generated = model.generate(
                **inputs,
                max_new_tokens=GENERATION_CONFIG["max_new_tokens"],
                do_sample=GENERATION_CONFIG["do_sample"],
                temperature=GENERATION_CONFIG["temperature"],
                output_attentions=True,
                return_dict_in_generate=True,
            )

    generated_ids = generated.sequences[0, prompt_len:]
    model_generation_raw = tokenizer.decode(generated_ids, skip_special_tokens=True)
    # Trim at first stop string.
    for stop in GENERATION_CONFIG["stop_strings"]:
        if stop in model_generation_raw:
            model_generation_raw = model_generation_raw.split(stop, 1)[0]
            break

    # 3. Classify is_fail via EM normalization.
    gen_norm = normalize_em(model_generation_raw)
    is_fail = gen_norm != event.gold_answer_normalized

    # 4. Update the event with model output + label + MEASURED distance.
    from dataclasses import replace
    measured_distance = measure_evidence_distance_tokens(event, tokenizer)
    event = replace(
        event,
        model_generation=model_generation_raw,
        model_generation_normalized=gen_norm,
        is_fail=is_fail,
        evidence_distance_tokens=measured_distance,
    )

    # 5. Determine t_answer_commit (the absolute token index of the first
    # generated token in the full sequence).
    t_answer_commit = prompt_len  # 0-indexed; generated_ids[0] is at position prompt_len
    total_tokens = prompt_len + generated_ids.shape[0]

    # 5b. Free the GPU-resident generate() outputs BEFORE the long CPU-side
    # feature loop. ``generated.attentions`` is large and unused (the hook
    # already captured what we need to CPU), and the KV cache is multi-GB on
    # long documents. Leaving them live through feature computation — and never
    # freeing across events — is what drove the 2026-06-14 OOM cascade (no
    # del/empty_cache existed anywhere). See run_pilot_resilient.sh for the
    # companion PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True setting.
    del generated, generated_ids, inputs, input_ids
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    # 6. Compute atomic-unit features over the lookback window.
    try:
        f_idx = f_lookback_absolute_indices(t_answer_commit)
        d_idx = d_lookback_absolute_indices(t_answer_commit)
    except LookbackOutOfBoundsError as exc:
        raise RuntimeError(
            f"Event {event.event_id} has prompt_len={prompt_len}; "
            f"lookback window cannot be populated. {exc}"
        ) from exc

    F_tensor = np.empty(F_SHAPE, dtype=np.float64)  # (256, 32, 32, N_FEATURES)
    D_tensor = np.empty(
        (len(D_LOOKBACK_INDICES), N_LAYERS_DEFAULT, N_HEADS_DEFAULT, N_HEADS_DEFAULT, 2),
        dtype=np.float64,
    )

    # 7. Recover each head's pass-level QKᵀ/AVWO operator EXACTLY ONCE per
    # (layer, head) and reuse it for both the F (atomic) and D (crossbar)
    # tensors. These operators are layer-internal and do not vary token-by-
    # token within the lookback window at v1 granularity, so the atomic
    # features are computed once per (ℓ, h) and broadcast across all J
    # positions. The attention graph is built and discarded inline (it feeds
    # only the Ricci slot) to avoid holding 1024 graphs in memory at once.
    qkt_by_layer: dict[int, np.ndarray] = {}
    avwo_by_layer: dict[int, np.ndarray] = {}
    for ell, cap in hook.captures.items():
        qkt_list: list[np.ndarray] = []
        avwo_list: list[np.ndarray] = []
        for h in range(N_HEADS_DEFAULT):
            qkt_h, avwo_h = recover_qkt_avwo(cap, head_idx=h, token_idx=t_answer_commit)
            qkt_np = qkt_h.cpu().numpy().astype(np.float64)
            avwo_np = avwo_h.cpu().numpy().astype(np.float64)
            qkt_list.append(qkt_np)
            avwo_list.append(avwo_np)

            # Build the attention graph ONLY when Ricci is being computed —
            # it is ~90% of per-event cost (O(T^2) per (layer, head)) and is
            # otherwise discarded. The US1 baseline (compute_ricci=False) skips
            # it entirely.
            if compute_ricci:
                a_h = cap.attention_weights[0, h].cpu().numpy().astype(np.float64)
                attn_graph = build_attention_graph(a_h, k_attn=k_attn)
            else:
                attn_graph = None
            features = compute_atomic_unit_features(
                qkt_np, avwo_np, attn_graph,
                k_grass=8, k_attn=k_attn, compute_ricci=compute_ricci,
            )
            # Broadcast the (7,) feature vector across all J lookback positions.
            F_tensor[:, ell, h, :] = features

        qkt_by_layer[ell] = np.stack(qkt_list, axis=0)
        avwo_by_layer[ell] = np.stack(avwo_list, axis=0)

    # 8. Crossbar pairwise Grassmannian: computed ONCE per (layer, edge-type)
    # from the pass-level head operators above. The 10 log-spaced D positions
    # all share the same pass-level crossbar at v1 (per-token-position
    # variation across the lookback is a v2 enhancement), so we fill them by
    # copy rather than recomputing.
    for ell in qkt_by_layer:
        qkt_dense = edges_to_dense(
            compute_pairwise_grassmannian(qkt_by_layer[ell], k_grass=8)
        )
        avwo_dense = edges_to_dense(
            compute_pairwise_grassmannian(avwo_by_layer[ell], k_grass=8)
        )
        for d_idx_pos in range(len(D_LOOKBACK_INDICES)):
            D_tensor[d_idx_pos, ell, :, :, 0] = qkt_dense
            D_tensor[d_idx_pos, ell, :, :, 1] = avwo_dense

    # 9. F summary: mean/p10/p50/p90/std along the F axis-0 (token-position).
    F_summary = np.stack([
        np.mean(F_tensor, axis=0),
        np.percentile(F_tensor, 10, axis=0),
        np.percentile(F_tensor, 50, axis=0),
        np.percentile(F_tensor, 90, axis=0),
        np.std(F_tensor, axis=0),
    ], axis=-1)  # shape (32, 32, N_FEATURES, 5)
    assert F_summary.shape == F_SUMMARY_SHAPE

    # 10. Cache writes.
    cache_dir = write_F(
        event.event_id, F_tensor,
        manifest_sha256=manifest_sha256, code_commit_sha=code_commit_sha,
        k_attn=k_attn, cache_root=cache_root,
    )
    write_D(
        event.event_id, D_tensor,
        manifest_sha256=manifest_sha256, code_commit_sha=code_commit_sha,
        k_attn=k_attn, cache_root=cache_root,
    )
    write_F_summary(
        event.event_id, F_summary,
        manifest_sha256=manifest_sha256, code_commit_sha=code_commit_sha,
        k_attn=k_attn, cache_root=cache_root,
    )
    # Per-event labeled metadata for resume-from-cache (small JSON, ~1 KB).
    write_event_metadata(event.event_id, event, cache_root=cache_root)

    _ = math.isnan  # quiet unused-import warning when not on the Ricci path
    _ = f_idx  # quiet unused-variable warning
    _ = d_idx
    return ExtractionResult(
        event=event,
        cache_dir=cache_dir,
        n_tokens_total=total_tokens,
        t_answer_commit=t_answer_commit,
    )
