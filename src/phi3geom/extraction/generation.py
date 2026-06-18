"""K+1 generation for semantic entropy + the scored answer (SP-0, T018).

Greedy (T=0) generation is the answer SCORED for correctness; K sampled generations
(T=1.0, top-p 0.9) feed offline semantic entropy (research.md R3.1). Stores, per
generation, the minimal sufficient statistic: text, token ids, chosen-token logprobs,
sequence logprob, length, the greedy flag, and the seed.

⚠ UNVALIDATED on this CPU box (no torch/model). torch is imported lazily; validate on
the pod. Drafted, pod-validation-pending.
"""

from __future__ import annotations

from typing import Any

STOP_STRINGS: tuple[str, ...] = ("\n", "Question:", "<|end|>")
DEFAULT_K = 10
DEFAULT_TEMPERATURE = 1.0
DEFAULT_TOP_P = 0.9
DEFAULT_MAX_NEW_TOKENS = 64


def _trim_at_stop(text: str) -> str:
    for stop in STOP_STRINGS:
        if stop in text:
            return text.split(stop, 1)[0]
    return text


def _decode_one(tokenizer: Any, out: Any, prompt_len: int, is_greedy: bool, seed: int) -> dict:
    """Build a GenerationSample dict from a single return_dict_in_generate output."""
    import torch

    seq = out.sequences[0]
    gen_ids = seq[prompt_len:]
    # Per-step chosen-token logprobs from the scores (one logits tensor per new token).
    logprobs: list[float] = []
    for step, logits in enumerate(out.scores):
        if step >= gen_ids.shape[0]:
            break
        lp = torch.log_softmax(logits[0].float(), dim=-1)
        logprobs.append(float(lp[int(gen_ids[step])]))
    text = _trim_at_stop(tokenizer.decode(gen_ids, skip_special_tokens=True))
    return {
        "text": text,
        "token_ids": [int(t) for t in gen_ids.tolist()],
        "token_logprobs": logprobs,
        "seq_logprob": float(sum(logprobs)),
        "length": int(gen_ids.shape[0]),
        "is_greedy": is_greedy,
        "seed": seed,
    }


def generate_samples(
    model: Any,
    tokenizer: Any,
    input_ids: Any,
    *,
    k: int = DEFAULT_K,
    temperature: float = DEFAULT_TEMPERATURE,
    top_p: float = DEFAULT_TOP_P,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    base_seed: int = 0,
) -> list[dict]:
    """Return ``K+1`` GenerationSample dicts (1 greedy scored + K sampled).

    The greedy sample carries ``is_greedy=True`` and is the one scored for
    correctness; the K sampled (seed = ``base_seed + i``) feed semantic entropy.
    """
    import torch

    prompt_len = int(input_ids.shape[1])
    gen_kwargs = dict(
        max_new_tokens=max_new_tokens,
        output_scores=True,
        return_dict_in_generate=True,
    )
    samples: list[dict] = []
    with torch.no_grad():
        greedy = model.generate(input_ids, do_sample=False, **gen_kwargs)
        samples.append(_decode_one(tokenizer, greedy, prompt_len, True, base_seed))
        for i in range(k):
            torch.manual_seed(base_seed + 1 + i)
            out = model.generate(
                input_ids,
                do_sample=True,
                temperature=temperature,
                top_p=top_p,
                **gen_kwargs,
            )
            samples.append(_decode_one(tokenizer, out, prompt_len, False, base_seed + 1 + i))
    return samples
