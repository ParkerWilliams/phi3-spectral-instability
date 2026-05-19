"""Per-atomic-unit feature computation: spectral primitives + Forman-Ricci.

The canonical feature ordering used in every F tensor and in
``manifest_header.json``'s ``feature_layout`` field.
"""

FEATURE_NAMES: tuple[str, ...] = (
    "stable_rank_qkt",
    "grassmannian_qkt",
    "spectral_entropy_qkt",
    "stable_rank_avwo",
    "grassmannian_avwo",
    "spectral_entropy_avwo",
    "forman_ricci_attention_graph",
)
"""7-scalar atomic-unit feature axis order. Pinned for v1; changing is a
breaking change requiring a constitution bump on Principle IV.
"""

N_FEATURES = len(FEATURE_NAMES)
