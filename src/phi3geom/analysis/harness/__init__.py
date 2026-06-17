"""Evaluation-harness interfaces (SP-0).

The contracts SP-1/SP-2/SP-3 consume — frozen-cache loader, feature-width-generic
null-evidence pack, incremental-over-baseline, cross-corpus/cross-model transfer
splitters, redundancy. Interfaces only; the metrics live in SP-1/SP-2. See
contracts/harness-interface.md.
"""

from phi3geom.analysis.harness.incremental import incremental_auroc
from phi3geom.analysis.harness.loader import HarnessDataset, load
from phi3geom.analysis.harness.null_evidence import null_evidence
from phi3geom.analysis.harness.redundancy import redundancy
from phi3geom.analysis.harness.transfer import (
    cross_corpus_split,
    cross_model_split,
    leave_one_group_out,
)

__all__ = [
    "HarnessDataset",
    "load",
    "null_evidence",
    "incremental_auroc",
    "redundancy",
    "cross_corpus_split",
    "cross_model_split",
    "leave_one_group_out",
]
