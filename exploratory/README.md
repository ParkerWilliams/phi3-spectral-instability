# exploratory/

This directory is the **TDD carve-out** required by Constitution Principle II.

Anything under `exploratory/` is:

- **Exempt from TDD discipline** — write code freely without test-first ceremony.
- **Forbidden as an upstream dependency** of `src/phi3geom/` — imports of the form
  `from exploratory.* import ...` from inside `src/phi3geom/` are a code-review red flag.
- **Excluded from the production cache pipeline** — exploratory probes may read from `cache/`
  but MUST NOT write into the production `cache/` or `dataset/` directories.

Two subdirectories:

- `notebooks/` — Jupyter notebooks for ad-hoc analysis.
- `probes/` — small scripts for one-off geometry probing.

Anything that turns out to be load-bearing for a reported result MUST be promoted into
`src/phi3geom/` with full TDD coverage (Principle II) before its output is included in any
writeup (Principle V).
