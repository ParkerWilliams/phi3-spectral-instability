# Research: SP-0 — Multi-Model Geometry Extraction Substrate

**Date**: 2026-06-17 | **Feature**: `002-sp0-extraction-substrate`

Three research threads were resolved against primary sources (transformers source at
tag v4.53.0, RULER/NoLiMa generators, the semantic-entropy + abstention literature).
All `NEEDS CLARIFICATION` from the Technical Context are resolved here; two
implementation-time verification to-dos are flagged explicitly.

---

## R1 — Model-agnostic forward-pass capture (transformers 4.x)

### R1.1 Post-softmax attention weights

**Decision**: Load every roster model with `attn_implementation="eager"` and call
`model(input_ids, output_attentions=True, output_hidden_states=True, use_cache=False)`.
Read `outputs.attentions` — a length-`num_hidden_layers` tuple of
`(batch, n_heads, q_len, kv_len)` tensors, **post-softmax, post-mask, post-softcap**.
Capture **layer-by-layer with immediate CPU offload + downcast** rather than holding
the whole tuple.

**Rationale**: Verified in `eager_attention_forward` (llama/phi3/gemma2):
`softmax(QKᵀ·scaling + mask)` is returned alongside the output only under eager.
sdpa/flash fuse the softmax and return `None`. Eager materializes a full `(B,H,T,T)`
fp32 tensor per layer (softmax computed in fp32): for Llama-3-8B at T=8192 that is
~8.6 GB/layer transiently and ~275 GB if all 32 are retained — **the binding memory
constraint** at long context / 70B. Layer-by-layer offload bounds it.

**Alternatives**: (a) sdpa + recompute `QKᵀ`/softmax from captured Q/K — memory-cheaper
but must replicate mask + scaling + Gemma-2 softcap exactly (error-prone); reserve as
an OOM fallback. (b) Forward hooks for weights — fragile across the 4.48 refactor and
unnecessary.

### R1.2 GQA/MQA head pairing

**Decision**: `n_rep = num_attention_heads // num_key_value_heads`; query head `q` is
served by KV head `q // n_rep` (contiguous/block grouping — **not** interleaved).
Always read `config.head_dim` (never compute `hidden/n_heads`).

**Rationale**: `repeat_kv` does `expand(..., n_rep, ...)` then reshape →
`[kv0×n_rep, kv1×n_rep, …]`, i.e. `repeat_interleave(dim=1, repeats=n_rep)`. Verified
head configs:

| Model | n_heads | n_kv | head_dim | n_rep | layers | notes |
|---|---|---|---|---|---|---|
| Phi-3-mini | 32 | **32** | 96 | 1 | 32 | **MHA (no GQA)**, fused `qkv_proj` |
| Llama-3-8B (base+inst) | 32 | 8 | 128 | 4 | 32 | GQA |
| Mistral-7B | 32 | 8 | 128 | 4 | 32 | GQA |
| Qwen2.5-0.5B | 14 | 2 | 64 | 7 | 24 | GQA, **tied embeddings** |
| Qwen2.5-1.5B | 12 | 2 | 128 | 6 | 28 | GQA, **tied embeddings** |
| Qwen2.5-7B | 28 | 4 | 128 | 7 | 28 | GQA |
| Qwen2.5-72B | 64 | 8 | 128 | 8 | 80 | GQA |
| Gemma-2-9B | 16 | 8 | **256** | 2 | 42 | GQA + SWA-alt + softcap |
| Llama-3-70B (anchor) | 64 | 8 | 128 | 8 | 80 | GQA |

**Gotchas**: `outputs.attentions` is **already expanded** to `n_heads` (grouping only
bites when re-pairing separately-captured KV); wrong grouping silently corrupts every
`QKᵀ`. `head_dim ≠ hidden/n_heads` for Gemma-2-9B (256≠224) and Qwen2.5 — read the config.

### R1.3 Gemma-2 specifics

**Decision**: Eager is **mandatory**. Record per layer: `layer_types` (even→`full`,
odd→`sliding_attention` with `sliding_window=4096`), `query_pre_attn_scalar=256`
(scaling `=256^-0.5`, **not** `head_dim^-0.5` in general), `attn_logit_softcapping=50`
(reshapes the pre-softmax logits), and `final_logit_softcapping=30` (**must be
re-applied in the offline logit-lens** or distributions won't match the model).

**Rationale**: Verified in `modeling_gemma2.py`. Sliding layers zero the post-softmax
matrix outside the window past T=4096 → do not compute geometry against a full-causal
mask there. sdpa/flash silently drop the softcap → a different matrix than the model's
reference path.

### R1.4 Per-head Q/K/V capture + RoPE timing

**Decision**: Capture Q/K/V at the projection output (fused `qkv_proj` for Phi-3 with
contiguous `[all-Q | all-K | all-V]` slices; split `q/k/v_proj` for the rest). This is
**pre-RoPE**. `outputs.attentions` already reflects **post-RoPE** geometry. So: take the
post-softmax matrix from `outputs.attentions` for routing metrics, and capture pre-RoPE
Q/K/V for operator reconstruction (or re-apply `apply_rotary_pos_emb` offline if a
post-RoPE `QKᵀ` operator is wanted). `W_O = o_proj.weight`; per-head OV slices columns
`[h·head_dim:(h+1)·head_dim]`.

**Rationale/Gotchas**: pre- vs post-RoPE is the single biggest correctness trap (a
logit-lens or `QKᵀ` from pre-RoPE Q/K won't match the model). The 4.48 refactor moved
`cos/sin` to model level — another reason to pin one version ≥4.48. Phi-3's fused MLP is
`gate_up_proj` (don't confuse with attention `qkv_proj`).

### R1.5 Hidden states + unembedding (logit-lens)

**Decision**: `output_hidden_states=True` → tuple length **L+1**: index 0 = embeddings;
`1..L-1` = **pre-final-norm** residual; **last entry is POST-final-norm** (= `last_hidden_state`).
Offline logit-lens: `lm_head(model.model.norm(h_i))` for raw `h_i`, **not double-norming**
the last. Capture `lm_head.weight` and `model.model.norm` **once per model**.

**Gotchas**: tied embeddings (Qwen2.5-0.5/1.5B, Gemma-2) → capture `lm_head.weight`
directly. Gemma-2 needs the final tanh softcap re-applied; it also scales embeddings by
`√hidden` at input (matters only for lensing layer 0).

### R1.6 Version pin

**Decision**: Pin a **single `transformers` version ≥4.48** (e.g. 4.51–4.53) for the
whole study; tighten the v1 `pyproject` pin accordingly. Always pass
`attn_implementation="eager"` explicitly (newer 4.x hard-errors on attentions under
non-eager rather than silently falling back). Move captured tensors to CPU inside the
hook for the 70B anchor under `device_map="auto"`.

**Source**: transformers v4.53.0 `modeling_{llama,phi3,gemma2}.py`; PR #35235 (4.48
refactor); issues #35896, #41924.

---

## R2 — Long-context corpus

**Decision**: **Primary = RULER** (NVIDIA synthetic generator, Apache-2.0), NIAH task
family + the `qa` tasks (SQuAD/HotpotQA repackaged into long context). **Secondary =
NoLiMa** (Adobe, latent-retrieval needle) as a lexical-overlap-confound control.
Generate at lengths **{4K, 8K, 16K, 32K}** (optionally 64K/128K to probe past the v1
B5/B6 cap).

**Rationale**: The dependent variable is "does attention concentrate on the gold
evidence span," so controllable position + known span + automatic scoring outweigh
naturalness. The decisive verified fact: **RULER's `niah.py` emits `token_position_answer`
natively** — the exact token index of the gold needle — alongside exact tokenizer-driven
lengths (pass the Phi-3 tokenizer so positions are in the model's tokens), a distractor
dimension (multi-key NIAH), and pure substring EM scoring (no judge). This is exactly
the setup of Retrieval-Head (Wu et al. 2024, arXiv:2404.15574), which scores per-head
retrieval mass on the needle. NoLiMa's needle requires *latent* retrieval (minimal
lexical overlap with the question), directly stress-testing the surface-overlap confound
behind the v1 null.

**Alternatives** (comparison): LongBench v1/v2, ZeroSCROLLS, LooGLE are natural-DocQA —
gold answer but **no controllable, position-labeled span**. HELMET ships no offset field
(must instrument assembly) and uses a GPT-4o judge on some tasks. InfiniteBench positions
sit at ~100–200K (overshoots the 4–32K target). gkamradt NIAH has clean per-row positions
but is a live API *runner*, not an offline static corpus.

**Verification to-dos** (flagged, not resolved): (1) confirm RULER's `qa`-task generator
emits an answer-position field equivalent to `niah.py`'s; (2) read NoLiMa's
`data/haystack/LICENSES.md` to confirm redistribution terms (Adobe non-commercial).

**Loading/scoring**: RULER repo `github.com/NVIDIA/RULER`, generator
`scripts/data/synthetic/niah.py`, metrics `string_match_all`/`string_match_part`
(case-insensitive substring recall). Attention-to-evidence target = the span starting
at `token_position_answer` of length = needle token count.

---

## R3 — Semantic entropy storage + correctness/abstention labeling

### R3.1 What to store for semantic entropy

**Decision**: Per event, store **K=10 sampled generations (T=1.0, top-p 0.9) + 1 greedy
generation (T=0, the scored answer) = 11 short decodes** (`max_new_tokens`=32–64, stop on
EOS/newline/"Question:"). For **each** generation store: decoded text, token IDs,
**per-token chosen-token logprobs**, sequence logprob, length, a greedy-flag, and the RNG
seed. **Do not** store full-vocab logits. All clustering is **offline**.

**Rationale**: K=10/T=1.0/discrete-SE is the published Nature-2024 recipe; matching it
makes SE comparable to the literature and to semantic-entropy probes (SEPs). Texts +
chosen-token logprobs are the minimal sufficient statistic for discrete SE,
Rao-Blackwellized (likelihood-weighted) SE, and both length-normalized and unnormalized
predictive-entropy baselines — so nothing is ever re-decoded. Discrete SE (cluster
counts, no logprobs) is the headline; it sidesteps the length-normalization confound.

**Offline clustering**: bidirectional-entailment, greedy O(K²), with
`microsoft/deberta-large-mnli`, **question prepended to each answer** (mandatory, or
"Paris" vs "France" mis-cluster). Runs as an SP-1 batch job off the GPU capture path.

**SEP synergy** (flagged for SP-2): since hidden states are already captured, the greedy
generation's hidden states let SP-2 train a semantic-entropy *probe* offline against the
K-sample SE label — a cheap parallel signal.

**Cost**: ~×10 decode FLOPs/event (short decodes → low absolute cost); SE storage
~low-KB/event (negligible vs hidden-state tensors).

**Alternatives**: K=5 (defensible if decode cost dominates); Bayesian/budget-SE
(arXiv:2504.03579) for ~53% of samples; SEPs for zero extra decodes at test time (but the
K-sample SE is still needed as the probe's training label).

### R3.2 Correctness + abstention labeling

**Decision**: One shared **`normalize_answer`** (replace `_`→space; lowercase; strip
punctuation; strip articles a/an/the; collapse whitespace) applied to prediction and all
golds, then:
- **Answerable correctness** (HotpotQA, SQuAD2-answerable, TriviaQA, NQ): **EM =
  max-over-aliases** (TriviaQA `NormalizedAliases`; NQ short-answer set) — the headline;
  **SQuAD-style token-F1** as a reported robustness cross-check.
- **Abstention** (SQuAD2-unanswerable): two-stage — a **high-precision rule pre-filter**
  ("i don't know", "cannot answer", "not in the context", "unanswerable", empty, …) +
  a **classifier/judge backstop** for recall (a constrained 3-way SimpleQA-style judge,
  or a fine-tuned abstention classifier / NLI). Hand-label ~100–200 events; target
  **~95% accuracy / ~0.9 F1**.

**4-way label**: answerable+EM-match → correct-answer; answerable+mismatch (incl.
wrongful abstain) → wrong-answer; unanswerable+abstain → correct-abstention;
unanswerable+assert → hallucination. Keep abstention as its own class (never folded into
incorrect). Headline binary positive = {wrong-answer, hallucination-on-unanswerable}.

**Rationale**: `normalize_answer` is the de-facto SQuAD/TriviaQA/HotpotQA/NQ standard;
identical normalization across corpora makes labels comparable and matches every
leaderboard. EM+aliases is exact/reproducible; token-F1 catches partial matches.
Abstention is open-ended phrasing — the field (SimpleQA, HalluLens, Do-Not-Answer) has
converged on rules-for-precision + judge/classifier-for-recall.

**No LLM judge for answerable correctness** — alias-EM + token-F1 is clean, deterministic,
and sufficient for short factoids; a judge is reserved for abstention recall.

**Gotchas**: TriviaQA/NQ alias sets are non-exhaustive (EM false-negatives → the F1
cross-check + hand-audit mitigate). Article-stripping can collapse rare answers ("The
The"). A model that abstains on *everything* trivially passes unanswerables while tanking
answerables → always score abstention **jointly** with answerable accuracy. If a judge is
used, report its P/R against the hand-labeled sample (don't claim reliability unaudited).

**Constitution note**: token-F1, the abstention judge/NLI, and RULER substring scoring are
**currently forbidden by the v1 Failure-event contract** — the v3.0.0 amendment
(plan.md Constitution Check) must permit them (EM stays the headline; F1 is a *reported
cross-check*).

### Key sources
Farquhar et al., *Nature* 630 (2024) semantic entropy; Kuhn et al., ICLR 2023
(arXiv:2302.09664); SEPs (arXiv:2406.15927); TriviaQA `triviaqa_evaluation.py`; NQ-Open
`nq_eval.py`; *Know Your Limits* abstention survey (arXiv:2407.18418); SimpleQA;
HalluLens (arXiv:2504.17550); Retrieval-Head (arXiv:2404.15574); RULER (NVIDIA);
NoLiMa (`amodaresi/NoLiMa`).
