"""Per-atomic-unit feature computation: spectral primitives + Forman-Ricci.

The canonical feature ordering used in every F tensor and in
``manifest_header.json``'s ``feature_layout`` field.
"""

FEATURE_NAMES: tuple[str, ...] = (
    # --- v1 scale-free spectral-shape features (indices 0..6, UNCHANGED) ---
    "stable_rank_qkt",
    "grassmannian_qkt",
    "spectral_entropy_qkt",
    "stable_rank_avwo",
    "grassmannian_avwo",
    "spectral_entropy_avwo",
    "forman_ricci_attention_graph",
    # --- v2 magnitude norms, appended AFTER ricci so 0..6 indices are stable ---
    "spectral_norm_qkt",
    "frobenius_norm_qkt",
    "nuclear_norm_qkt",
    "spectral_norm_avwo",
    "frobenius_norm_avwo",
    "nuclear_norm_avwo",
)
"""13-scalar atomic-unit feature axis order.

v1 (indices 0..6) is the scale-free spectral-shape set + Forman-Ricci. v2
appends 3 magnitude norms per operator (indices 7..12) — the operator scale
that the v1 features discard by construction. The norms are appended AFTER
the Ricci slot so the v1 indices (and every consumer that hard-codes them,
e.g. ``lattice.spine`` reading the Ricci slot at index 6) are unchanged.

Changing this axis is a breaking change to the extracted feature set
(Principle IV); the manifest's ``feature_layout`` records which version a
cache was extracted under, so v1 and v2 caches remain distinguishable.
"""

N_FEATURES = len(FEATURE_NAMES)
