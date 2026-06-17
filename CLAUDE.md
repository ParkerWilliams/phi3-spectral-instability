<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan at
`specs/002-sp0-extraction-substrate/plan.md`. Supporting artifacts:
- Spec: `specs/002-sp0-extraction-substrate/spec.md`
- Research decisions: `specs/002-sp0-extraction-substrate/research.md`
- Data model: `specs/002-sp0-extraction-substrate/data-model.md`
- Contracts: `specs/002-sp0-extraction-substrate/contracts/`
- Quickstart: `specs/002-sp0-extraction-substrate/quickstart.md`
- Program design (umbrella): `docs/superpowers/specs/2026-06-17-v2-correctness-geometry-program-design.md`
- Predecessor v1 study (null result, extended by SP-0): `specs/001-phi3-attention-geometry-v1/`
- Constitution (governs all features): `.specify/memory/constitution.md`
  NOTE: ratified **v3.0.0** (2026-06-17) — governs the v2 program: multi-model
  roster, sampled generations for semantic entropy, EM-headline + F1/abstention
  labeling, reproducible raw-tensor caching, cross-corpus/cross-model transfer.
  The `/speckit-implement` gate the SP-0 plan flagged is now satisfied.
<!-- SPECKIT END -->

## Governing analysis methodology (v2.0.0 — supersedes the spec/tasks in part)

As of 2026-05-28 (constitution v2.0.0), the headline analysis is a **single pooled,
distance-blind failure detector** evaluated on the balanced CEM set; per-regime/per-bin
analysis is demoted to a **post-hoc diagnostic**. The speckit `spec.md` / `tasks.md`
above still describe the original per-regime methodology and are **partly superseded** —
read these as the governing source for the analysis/evaluation layer:

- Design (reframe rationale + scope delta): `docs/superpowers/specs/2026-05-28-distance-blind-failure-detector-design.md`
- Implementation plan (task-by-task): `docs/superpowers/plans/2026-05-28-distance-blind-failure-detector.md`

The extraction pipeline (forward pass + geometry features) is unchanged. B5/B6
long-context + RoPE-wrap are explicit v1 non-goals (the 201-fact corpus reaches only
B1–B4). The full-study scripts (`run_analysis.py`, `full_study_main.py`) still use the
per-bin path; reconciling them to the pooled detector is deferred future work.
