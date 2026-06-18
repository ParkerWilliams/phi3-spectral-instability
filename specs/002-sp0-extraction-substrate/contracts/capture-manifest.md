# Contract: Capture Manifest (metric → raw material)

**Feature**: `002-sp0-extraction-substrate` | **Primary deliverable of SP-0**

The manifest is the authoritative mapping from every metric in the program catalog
(`docs/superpowers/specs/2026-06-17-v2-correctness-geometry-program-design.md` §5) to a
stored `CaptureBundle` field. A **completeness check** (contract test) MUST assert 100%
coverage before any full run (SC-001). `[raw]` = stored as captured; `[in-pass]` = reduced
on-GPU because the raw form is too large.

## Mapping

| Program metric (§) | Source tensor | Bundle field | Mode | Shape / dtype |
|---|---|---|---|---|
| Trajectory curvature, local-ID (5.1) | per-layer residual @ answer pos | `hidden_answer_pos` | `[raw]` | `(L+1, d_model)` fp16 |
| Logit-lens convergence (5.1) | `hidden_answer_pos` + `lm_head.weight` + `model.model.norm` | `hidden_answer_pos` + ModelDescriptor | `[raw]` | offline `lm_head(norm(h_i))`; re-apply Gemma-2 final softcap |
| Per-token dynamics (5.5) | residual over ±W window | `hidden_window` | `[raw]` | `(2W+1, L+1, d_model)` fp16 |
| Linear probe / SEP (5.0) | `hidden_answer_pos` (greedy) | `hidden_answer_pos` | `[raw]` | — |
| Attention-to-evidence, routing entropy (5.2) | answer-position attention row | `attn_rows_answer_pos` | `[raw]` | `(L, n_heads, T)` fp16 |
| DLA per head (5.2) | `attn_rows` + V + `o_proj` slice + `lm_head` | `attn_rows_answer_pos` + Q/K/V capture | `[raw]` | per-head OV = `o_proj[:, h·hd:(h+1)·hd]` |
| Retrieval-head signature (5.2) | attention mass on `evidence_spans` | `attn_rows_answer_pos` + `evidence_spans` | `[raw]` | — |
| Attention rollout/flow (5.2) | full `T×T`, layer subset S | `attn_full_subset` | `[raw]`/`[in-pass]` | `(|S|, n_heads, T, T)` fp16 |
| Markov-operator spectra (5.2) | full `T×T`, subset S | `attn_full_subset` | `[raw]` | — |
| MP-deviation / spikes, eigenspacing, effective rank (5.3) | per-layer token-cloud covariance eigenspectrum + MP fit | `token_cloud_spectra` | `[in-pass]` | `(L, k_eig)` + fit stats; **float64 in-pass** (Const. IV) |
| Ollivier-Ricci, Cheeger/Laplacian (5.4) | full `T×T`, subset S | `attn_full_subset` | `[raw]` | graph built offline |
| v1-repaired norms + dynamics + W_O fix (5.5) | per-head Q/K/V + `o_proj` | Q/K/V capture + ModelDescriptor | `[raw]` | per-head `(head_dim, head_dim)` operators offline |
| Confidence baselines (5.0) | answer-token logits + per-token logprobs | `answer_logits` + `samples` | `[raw]` | `(vocab,)` or top-k fp16 |
| Semantic entropy (5.0) | K+1 generations | `samples` | `[raw]` | text + token_ids + token_logprobs (R3.1) |

## Per-model "once" artifacts (not per-event)

- `lm_head.weight` `(vocab, d_model)`, `model.model.norm` params, full `ModelDescriptor`
  (incl. `attention_profile`, softcap params, `n_rep`). Captured once per model, referenced
  by every bundle.

## In-pass reduction rules

- **Token-cloud spectra** (`[in-pass]`): the raw `T×d_model` per-layer activation cloud is
  too large to store (~300 MB/event). Compute the covariance eigenspectrum (top `k_eig`)
  + Marchenko–Pastur fit (bulk edge, spike count, λ_max) **in float64 on-GPU** and store
  only those. Property-tested against the closed-form MP bulk edge on a Gaussian
  (Constitution II/IV).
- **Full `T×T` attention** (`attn_full_subset`): stored only for layer subset `S` (from the
  benchmark gate); captured **layer-by-layer with CPU offload** to bound peak memory
  (R1.1). If even S exceeds the budget, compute the rollout-to-evidence scalar in-pass.
- **Inter-head drift surface** (`interhead_drift_surface`, `[in-pass]`): the raw `H×T`
  attention blocks across many query positions × all layers are ~3+ GB/event — too large.
  Compute the per-cell head-configuration summary `S(t, ℓ)` **in float64 on-GPU**, off the
  attention tensor eager already materializes, over the log-spaced query set
  `{answer − offset: 0,1,2,4,…,256} ∪ {gold-evidence positions}` × all layers, and store
  **only** the surface (≈ `n_t × L × K_summary`). Each cell carries the corpus-agnostic
  inter-head **JS/Hellinger dispersion** and the overlap-matrix **effective rank / Fiedler
  gap / top eigenvalue**, plus an evidence-coverage scalar where a gold span exists. Feeds
  the §5.6 inter-head attention-drift family. Property-tested on CPU (Constitution II/IV).

### Added §5.6 mapping rows

| Program metric (§) | Source | Bundle field | Mode |
|---|---|---|---|
| Inter-head dispersion drift (5.6) | per-cell JS/Hellinger over `{A_h}` | `interhead_drift_surface` | `[in-pass]` |
| Overlap-matrix spectrum drift (5.6) | per-cell head-head similarity eigen-stats | `interhead_drift_surface` | `[in-pass]` |
| Evidence-coverage drift (5.6, with-context) | head-set mass on the gold span | `interhead_drift_surface` | `[in-pass]` |

## Capture configuration (R1)

`from_pretrained(..., attn_implementation="eager", torch_dtype=bfloat16)`;
`model(input_ids, output_attentions=True, output_hidden_states=True, use_cache=False)`.
Hidden tuple: index 0 = embeddings, 1..L-1 pre-final-norm, **last = post-final-norm** —
do not double-norm in the logit-lens. GQA: query head `q` → KV head `q // n_rep`. Gemma-2:
eager mandatory; record `layer_types` + both softcaps. Pre-RoPE Q/K/V at projection;
`outputs.attentions` is post-RoPE.

## Completeness rule (gate)

Before any full run, the completeness check walks program-catalog §5 and asserts each
metric resolves to a bundle field above. A missing row ⇒ a future re-extraction ⇒ the run
is **blocked** (SC-001).
