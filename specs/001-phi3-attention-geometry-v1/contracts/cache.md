# Contract: F/D Tensor Cache

**Scope**: On-disk layout and read/write API for the cached `F` (per-atomic-unit features) and
`D` (pairwise head-head distances) tensors. Implemented in `src/phi3geom/storage/cache.py`.

---

## File layout per event

```
cache/
└── {event_id_prefix}/                # First 2 hex of event_id, for filesystem balance
    └── {event_id}/
        ├── F.npy                     # Per-atomic-unit features, dense over lookback
        ├── F.header.json             # Provenance header for F
        ├── D.npy                     # Pairwise head-head distances, log-spaced lookback
        ├── D.header.json             # Provenance header for D
        ├── F_summary.npy             # Out-of-lookback F summaries
        └── F_summary.header.json
```

- `event_id_prefix` is `event_id[:2]` — gives 256 first-level directories for filesystem balance
  on millions-of-files filesystems.
- A new event's directory is created with all 6 files atomically (using `os.rename` semantics).

---

## `F.npy` schema

- Shape: `(J=256, num_layers=32, num_heads=32, num_features=7)` = `(256, 32, 32, 7)`.
- Dtype: `float32` (downcast from float64 at the cache boundary; Constitution Principle IV).
- Axis semantics:
  - Axis 0: relative_token_position, ordered `-255, -254, …, 0`.
  - Axis 1: layer_idx, ordered `0, 1, …, 31`.
  - Axis 2: head_idx, ordered `0, 1, …, 31`.
  - Axis 3: feature, ordered per `FEATURE_NAMES` (research.md §12; contract atomic_unit.md).

---

## `D.npy` schema

- Shape: `(L=10, num_layers=32, num_heads=32, num_heads=32, num_edge_types=2)` =
  `(10, 32, 32, 32, 2)`.
- Dtype: `float32`.
- Axis semantics:
  - Axis 0: log-spaced lookback index. Positions: `j ∈ {0, 1, 2, 4, 8, 16, 32, 64, 128, 256}`
    (the lookback offset in tokens before `t_answer_commit`; index 0 = j=0 = the answer-commit
    token itself, index 9 = j=256).
  - Axis 1: layer_idx.
  - Axes 2, 3: head pair `(i, j)` with `i < j`. The lower-triangle entries (`i > j`) MUST be 0.
  - Axis 4: edge_type, `0 = qkt_grassmannian`, `1 = avwo_grassmannian`.

---

## `F_summary.npy` schema

- Shape: `(num_layers=32, num_heads=32, num_features=7, num_statistics=5)` = `(32, 32, 7, 5)`.
- Dtype: `float32`.
- Axis 3 (statistics): `[mean, p10, p50, p90, std]` over the full token-axis range outside the
  lookback window.

This tensor summarizes per-(ℓ, h, feature) distributions over the prefill before the lookback
window, so analysis code can contextualize a lookback excursion against its own pre-lookback
baseline without loading the full prefill `F`.

---

## `*.header.json` schema

```jsonc
{
  "schema_version": "1.0.0",
  "manifest_sha256": "<64 hex>",          // Manifest at write time
  "code_commit_sha": "<40 hex>",
  "tensor_shape": [256, 32, 32, 7],       // Matches the .npy shape exactly
  "tensor_dtype": "float32",
  "feature_layout": [...],                 // For F and F_summary only; redundant with manifest
                                          // but included for standalone audit
  "lookback_window_length": 256,
  "lookback_indices": [0, 1, 2, 4, 8, 16, 32, 64, 128, 256],  // For D only
  "k_grass": 8,
  "k_attn": <int>,
  "forman_ricci_convention": "nan_with_median_imputation_and_indicator",
  "write_timestamp_utc": "2026-MM-DDTHH:MM:SSZ",
  "host": "<hostname>"
}
```

Three constraints:
1. `manifest_sha256` MUST match the current manifest at read time, OR the read MUST raise
   `CacheStaleError` (no silent fallback). This is Constitution Principle I's
   "directory-name-rename-detection" defense.
2. `tensor_shape` and `tensor_dtype` MUST exactly match the `.npy` header. Read code asserts
   both and raises `CacheSchemaError` on mismatch.
3. `k_grass`, `k_attn`, `lookback_window_length`, and `feature_layout` MUST agree with the
   manifest's pins. Disagreement raises `CacheConfigDriftError`.

---

## I/O API

```python
# src/phi3geom/storage/cache.py

def write_F(
    event_id: str,
    F: np.ndarray[float64],     # Input must be float64; downcast happens here
    *,
    manifest_sha256: str,
    code_commit_sha: str,
    k_attn: int,
    cache_root: pathlib.Path,
) -> pathlib.Path:
    """Write F.npy + F.header.json atomically. Returns the directory path.

    Asserts: F.shape == (256, 32, 32, 7); F.dtype == float64.
    Downcasts F to float32 before writing.
    """

def read_F(
    event_id: str,
    *,
    expected_manifest_sha256: str,
    cache_root: pathlib.Path,
) -> np.ndarray[float32]:
    """Read F.npy after verifying header.manifest_sha256 == expected.

    Raises CacheStaleError if the SHA mismatches.
    """

def write_D(...): ...
def read_D(...): ...
def write_F_summary(...): ...
def read_F_summary(...): ...
```

**Test obligations** (TDD scope, Constitution Principle II):
- `tests/unit/test_manifest.py` (shared with manifest tests) covers cache header round-trip.
- `tests/unit/test_cache.py::test_write_read_F_round_trip` — write float64 F, read float32,
  verify lossy-but-bounded round trip (max_abs_diff ≤ 1e-6 due to float32 precision; this is
  the EXPECTED cache-boundary downcast tolerance, distinct from the 1e-7 spectral parity).
- `tests/unit/test_cache.py::test_stale_sha_raises` — write F with SHA `A`, attempt read with
  expected SHA `B`, verify `CacheStaleError` raised.
- `tests/unit/test_cache.py::test_shape_mismatch_raises` — write F with valid shape, corrupt
  header.tensor_shape, verify `CacheSchemaError` raised.
- `tests/unit/test_cache.py::test_dtype_rejection` — calling `write_F(F=float32_array)` raises
  `TypeError` (no auto-upcast; explicit float64 in = float32 cached out).
