"""RULER long-context adapter (SP-0, T040) — UNVALIDATED (pod).

RULER is a GENERATOR (NVIDIA, Apache-2.0), not a plain HF split: generate with YOUR
model's tokenizer so `token_position_answer` is in the model's tokens (research R2).
This adapter reads RULER-format records (a `.jsonl` of generated examples) with fields
`{input, outputs, token_position_answer, length, answer_prefix}` → DocQAEventRecord,
mapping the needle token position to `evidence_spans`. Point `--data` at generated
RULER output on the pod.

⚠ Generation needs the NVIDIA RULER repo + the model tokenizer; verify the `qa`-task
generator emits `token_position_answer` like `niah.py` (research R2 to-do).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from phi3geom.dataset.adapters._common import event_id
from phi3geom.dataset.types import DocQAEventRecord


def iter_events(
    *,
    data_path: str,
    limit: int | None = None,
    needle_token_len: int = 8,
    **_ignored,
) -> Iterator[DocQAEventRecord]:
    """Yield events from a RULER-generated `.jsonl` file."""
    path = Path(data_path)
    with path.open() as fh:
        for i, line in enumerate(fh):
            if limit is not None and i >= limit:
                break
            row = json.loads(line)
            outputs = row["outputs"]
            gold = outputs[0] if isinstance(outputs, list) else outputs
            pos = row.get("token_position_answer")
            spans = ((pos, pos + needle_token_len - 1),) if pos is not None else None
            question = row.get("answer_prefix", "Answer:")
            yield DocQAEventRecord(
                event_id=event_id(row["input"], question, str(gold)),
                corpus_id="ruler",
                document=row["input"],
                question=question,
                gold_aliases=(str(gold),),
                is_answerable=True,
                evidence_spans=spans,
                provenance={"source": "ruler", "source_index": i, "length": row.get("length")},
            )
