"""Model-agnostic capture adapters (SP-0).

Per-architecture resolvers for Q/K/V, attention weights, the output projection,
and per-layer hidden states, plus the shared ``ModelDescriptor`` and GQA/MQA
head-expansion helpers. Import-safe without ``torch`` installed: the helpers and
descriptor are pure-Python/NumPy; ``torch`` is imported lazily inside the live
capture path (the v1 ``hooks.py`` pattern).
"""

from phi3geom.extraction.adapters.base import (
    ModelAdapter,
    ModelDescriptor,
    expand_kv_heads,
    kv_head_for_query,
    n_rep_for,
)

__all__ = [
    "ModelAdapter",
    "ModelDescriptor",
    "expand_kv_heads",
    "kv_head_for_query",
    "n_rep_for",
]
