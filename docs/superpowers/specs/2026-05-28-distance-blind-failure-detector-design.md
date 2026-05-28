# Design: Phi-3 Attention-Geometry as a Distance-Blind Failure Detector

**Date**: 2026-05-28
**Status**: Approved (brainstorming) — pending implementation plan
**Revises**: `specs/001-phi3-attention-geometry-v1/` (analysis & evaluation methodology only)
**Branch**: `001-phi3-attention-geometry-v1`

## 1. Background — why this revision exists

The original feature 001 spec was generated verbatim from a one-paragraph seed
(preserved as the `Input` field in `spec.md`, 2026-05-18). That seed baked in a
specific methodology: **4800 events stratified across 6 evidence-distance bins**,
**CEM-matched**, analyzed with **per-regime composite logistic regression — no
pooling across bins** — plus an FDA β(ℓ) depth analysis and a B6 "RoPE-wrap"
long-context headline.

While validating the extraction pipeline on RunPod, two findings forced a rethink:

1. **The synthetic generator cannot build the long-distance bins.** The fact
   corpus is **201 facts** (~20 per template × 10 templates). At any fixed
   `distractor_density` every bin produces the *same* document length — ~330
   words at density 0.3, ~1105 words (~1450 tokens) at density 1.0 — because
   `_build_document` stops when it runs out of distractors instead of padding to
   the target. **B5 (2048–3072 tok) and B6 (3072–4096 tok) are physically
   unreachable** (~6× too little source material). Worse, `generate_event`
   stamps the caller's `bin_id` blindly and sets `evidence_distance_tokens` to
   the *target*, not a measurement — so a pilot would have produced short
   documents wearing "far" labels, silently violating the `data-model.md`
   invariant that *"`evidence_distance_tokens` MUST fall within the interval of
   its `bin_id`."* The flat ~345 s/event timing observed on the GPU box was the
   tell: all six "bins" were the same short document.

2. **Per-regime stratification flatters a weak detector.** Slicing events into
   narrow distance bands controls confounds and shrinks the problem, inflating
   apparent performance relative to a single detector facing the full
   distribution. If the real question is field-usability, the headline must not
   lean on that crutch.

### The reframed question

> Not *"does geometry separate fail from control inside matched distance bins"* —
> but **"would a geometry-based failure detector be useful if you pointed it at
> real Phi-3 DocQA traffic?"**

Distance is kept only as a coarse, post-hoc **diagnostic** axis (where does the
detector work?), so **bin fidelity can be low** — which dissolves the
4096-token generation blocker. DCSBM gives the prior that geometry is
informative; this study asks whether that survives a distance-blind setting.

### Decision: balanced evaluation (Approach A)

We evaluate on a **balanced (CEM-matched 50/50) set**. Rationale (user): a
balanced testbed is how you discover whether the signal exists at all and build
a detector against it — analogous to gathering a balanced set of hardware
failures to develop a field detector, even though the field failure rate is low.
**Natural base-rate / calibration is a deployment concern, explicitly deferred.**

## 2. Scope of change (the delta)

| Layer | Disposition |
|---|---|
| Synthetic Wikidata events | **Keep** (with a contained generator fix, §4) |
| Forward pass + geometry extraction (atomic units, 7 features) | **Keep** — validated on RunPod, unchanged |
| CEM confound-matching, 50/50 balance | **Keep** (Approach A) |
| Per-regime composite logistic (separate model per bin) | **Replace** with one pooled, distance-blind model |
| Evidence-distance bins as feature / stratifier | **Remove** as input; **demote** to post-hoc diagnostic labels |
| Ricci marginal-gain, FDA β(ℓ) depth analysis | **Retain as secondary**, reframed against the pooled model |
| B5/B6 long-context + RoPE-wrap headline | **Defer** (out of reach with current corpus) |

This is an analysis/evaluation reframe on top of the existing, already-validated
pipeline — not a rebuild.

## 3. Research question & success criteria

- **Primary:** A single classifier, fed **only attention-geometry features** and
  **never told the evidence distance**, separates failures from successes on the
  balanced set. **Success = pooled AUROC whose 95% CI lower bound is > 0.5**
  (significantly better than chance), with the DCSBM AUROC as the aspirational
  comparison. (A concrete target above 0.5 is set in the plan once the DCSBM
  baseline number is pulled in.)
- **Attribution:** Identify *where* the discriminative signal lives — which heads
  and which depths — for the pooled detector.
- **Diagnostic:** Report AUROC as a function of measured evidence distance, to
  show where the blind detector degrades (reported, never used to assist it).

## 4. Data & the distance diagnostic

- Keep synthetic events and CEM matching (template / distractor-density /
  gold-answer-length coarsenings → balanced 50 fail + 50 control per group).
- **Generator/pipeline fix (contained):**
  - The pipeline records the **true, tokenizer-measured** evidence distance per
    event (the field the current code claims is "set precisely by pipeline" — to
    be verified and made authoritative).
  - **Bins become post-hoc labels derived from the measured distance**, not
    generation targets. Keep the B1–B6 thresholds as diagnostic labels for
    continuity, but assign them from measurement.
- **Achievable range:** expect **B1–B4 to populate; B5/B6 sparse-to-empty** with
  the 201-fact corpus. This is acknowledged, not hidden — the distance diagnostic
  covers the achievable range, and far-distance is named future work.

## 5. Detector & evaluation

- **Model:** one pooled classifier over all matched events; **logistic
  regression to start** (matches the DCSBM analysis and keeps it interpretable).
  Features = the geometry features only; **no distance/bin input.**
- **Per-event feature vector:** inherited unchanged from the existing composite
  feature assembly (the step that reduces each event's atomic-unit tensor —
  256 positions × 32 layers × 32 heads × 7 features — to a per-event vector).
  The only change is that the resulting matrix is fit **once, pooled**, instead
  of split per bin.
- **Headline metric:** pooled AUROC + 95% CI on the balanced set.
- **Distance diagnostic:** AUROC (or score distribution) sliced by
  measured-distance bin.
- **Confound audit (check, not a filter):** CEM already balances template,
  distractor-density, and gold-answer-length between fail and control, so the
  detector cannot separate classes on those by construction. The audit therefore
  targets **residual, unmatched** artifacts — chiefly raw document length and
  measured evidence distance — confirming the detector tracks geometry rather
  than a length/position proxy. Reported as robustness, never used to drop events.

## 6. Retained as secondary (post-MVP)

- **Ricci marginal-gain:** does adding Forman-Ricci-token features improve the
  *pooled* detector's AUROC? (Was US2.)
- **Depth attribution / β(ℓ):** which raw layers carry the discriminative signal
  for the pooled detector. The FDA-on-spine-curves machinery can be retained but
  is reframed from "per-regime" to "pooled," and is not in the first deliverable.

## 7. Non-goals (v1)

- Natural base-rate evaluation and probability calibration.
- Real (non-synthetic) DocQA corpora.
- B5/B6 long-context regimes and the RoPE-wrap question.

All three are named as explicit future work, not silently dropped.

## 8. Open questions / risks

- **Distance spread within the cap:** confirm the (fixed) generator actually
  yields a usable spread of *measured* distances across B1–B4, so the diagnostic
  is meaningful. If placement is degenerate, the generator fix must also vary
  evidence position, not just measure it.
- **Pilot re-scope:** the existing `run_pilot.sh` / `pilot_main.py` assume
  per-bin fits and CEM-per-bin yield criteria (SC-004). These reporting paths
  need to be re-pointed at the pooled detector; the pass criteria from spec 001
  (≥5/6 bins ≥50% CEM yield, B6 RoPE check) no longer all apply.
- **Spec 001 reconciliation:** `spec.md` / `tasks.md` still describe the
  per-regime methodology. They should be annotated to point at this design as the
  governing analysis approach, to avoid drift.

## 9. Payoff

The RunPod blocker is dissolved: with distance demoted to a loose diagnostic, the
re-scoped pilot (balanced set, one distance-blind detector) runs inside the
extraction pipeline's already-validated budget (~58 GPU-hr projected; well under
the 72 GPU-hr ceiling), with no new data machinery required.
