# Contract: Atomic-Unit Feature Computation

**Scope**: Function signatures and invariants for the 7-scalar per-atomic-unit feature
extractor. Implemented in `src/phi3geom/geometry/spectral.py` and `src/phi3geom/geometry/ricci.py`.

---

## `compute_atomic_unit_features(qkt, avwo, attention_graph, k_grass, k_attn) -> np.ndarray[float64]`

**Inputs**:
- `qkt`: `np.ndarray[float64]` of shape `(d_head, d_head)` — the per-head `QKᵀ` matrix
  pre-softmax for one (t, ℓ, h). For Phi-3-mini, `d_head = 96`.
- `avwo`: `np.ndarray[float64]` of shape `(d_head, d_head)` — the per-head `A · V · W_O`
  matrix for the same (t, ℓ, h).
- `attention_graph`: `networkx.Graph` — the directed attention graph derived from
  `softmax(qkt / sqrt(d_head) + mask)`, sparsified to the top `k_attn` edges per node.
- `k_grass`: `int` — Grassmannian subspace dimension. Pinned to `8` for v1.
- `k_attn`: `int` — Pilot-pinned attention-graph sparsification cutoff.

**Output**:
- `features`: `np.ndarray[float64]` of shape `(7,)` in canonical order:
  ```
  [stable_rank(qkt),
   top_k_grassmannian(qkt, k_grass),
   spectral_entropy(qkt),
   stable_rank(avwo),
   top_k_grassmannian(avwo, k_grass),
   spectral_entropy(avwo),
   forman_ricci_token(attention_graph)]
  ```

**Invariants**:
- All inputs MUST be float64. Calling with float32 inputs is a programming error and MUST raise
  `TypeError`.
- Output is float64 (downcasting to float32 happens at the cache boundary, not here).
- Indices 0–5 are never NaN under non-degenerate inputs (a 96×96 matrix with rank > 0 has
  well-defined stable rank, Grassmannian distance, and spectral entropy).
- Index 6 MAY be NaN when the attention graph has isolated nodes after top-`k_attn` truncation
  (research.md §10). The convention `nan` is stable: production code returns `np.nan`, not 0.
- Two calls with bit-identical inputs MUST return bit-identical outputs (deterministic
  computation; no internal randomness).
- The DCSBM reference implementation, when called with the same `qkt` and `avwo`, MUST agree
  with this function on indices 0–5 to within `max_abs_diff ≤ 1e-7` (Constitution Principle IV,
  parity rule).

**Test obligations**:
- `tests/unit/test_spectral_parity.py`: parity vs DCSBM reference on 100 seeded random
  `(qkt, avwo)` pairs of shape `(96, 96)` (Hypothesis-driven; 100 examples per `@given`).
- `tests/unit/test_ricci_parity.py`: Forman-Ricci index 6 parity vs `GraphRicciCurvature` on
  3 explicit reference graphs + 100 random 16-node graphs with edge density in `[0.1, 0.8]`.
- `tests/unit/test_*` for each individual scalar primitive (`stable_rank`,
  `top_k_grassmannian`, `spectral_entropy`, `forman_ricci_token`).

---

## `stable_rank(matrix: np.ndarray[float64]) -> float64`

**Definition**: `‖matrix‖_F² / ‖matrix‖_2²`, where `‖·‖_F` is Frobenius norm and `‖·‖_2` is
spectral norm (largest singular value).

**Invariants**:
- Shape: takes any 2D matrix; for v1 the inputs are `(96, 96)`.
- Returns a positive scalar; always `≤ rank(matrix) ≤ min(matrix.shape)`.
- Numerically robust: returns the value computed via SVD in float64, not via a
  Frobenius/spectral-norm fraction in float32.

---

## `top_k_grassmannian(matrix: np.ndarray[float64], k: int) -> float64`

**Definition**: A canonical projection-distance summary for the top-`k` singular subspaces of
the matrix. Exact form: `||P_k - P_k_ref||_F`, where `P_k` is the projector onto the top-`k`
left-singular subspace and `P_k_ref` is a canonical reference (the identity-aligned projector
or the per-call paired matrix's projector, depending on call site).

**Invariants**:
- `k` is pinned to `k_grass = 8` for v1.
- For the per-atomic-unit feature, the "reference" projector is the identity-aligned projector
  (the singular-subspace-distance from the canonical basis); this matches the DCSBM prior-work
  scalar. The crossbar pairwise-head function uses the OTHER head's projector as reference —
  same primitive, different call site.

---

## `spectral_entropy(matrix: np.ndarray[float64]) -> float64`

**Definition**: Shannon entropy of the normalized singular-value-squared distribution.
`p_i = σ_i² / Σ_j σ_j²`; `H = -Σ p_i log(p_i)`.

**Invariants**:
- Returns a non-negative scalar.
- `H = 0` when one singular value dominates (rank-1 matrix); `H = log(min(matrix.shape))`
  when singular values are uniform.
- Uses natural log (`np.log`), matching the DCSBM reference.

---

## `forman_ricci_token(attention_graph: networkx.Graph) -> float64`

**Definition**: Mean Forman-Ricci curvature over edges of the per-(t,ℓ,h) attention graph,
sparsified to top-`k_attn` outgoing edges per node.

**Invariants**:
- Computes Forman-Ricci with the standard combinatorial formula:
  `F(e_{ij}) = w_{ij} * (w_i/w_{ij} + w_j/w_{ij} - Σ_{e' ~ e_{ij}} w_{ij}/√(w_{ij}·w_{e'}))`.
- For unweighted attention-graph edges (post-top-k binarization), this reduces to a function
  of node degrees.
- Returns `np.nan` when the graph has any isolated node (research.md §10).
- Otherwise returns the mean Forman-Ricci across all `(i, j)` edge pairs, in float64.

---

## Forbidden patterns

- **Float32 in the seam**: any of `stable_rank`, `top_k_grassmannian`, `spectral_entropy`, or
  `forman_ricci_token` called with float32 inputs MUST raise `TypeError`. The cache-boundary
  downcast is the responsibility of `src/phi3geom/storage/cache.py` only.
- **In-place mutation**: none of these functions modify their inputs.
- **Cross-call state**: no module-level mutable state. Repeated calls on identical inputs are
  bit-identical.
