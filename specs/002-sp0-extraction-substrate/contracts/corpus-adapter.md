# Contract: Corpus Adapter

**Feature**: `002-sp0-extraction-substrate`

Every corpus adapter is a function `iter_events(split, sampling) -> Iterator[DocQAEventRecord]`
emitting the common record (`data-model.md`). The substrate is corpus-agnostic below this
seam: one capture path serves all regimes.

## Required behavior

- Emit `DocQAEventRecord` with all fields populated per the table below.
- Compute `event_id` via the Constitution-I content hash.
- Carry `provenance` (source split, sampling seed, corpus version, generator params).
- Sample toward a **balanced fail/hallucination rate** (target band 25–75%, SC-005) from
  natural difficulty + the unanswerable split — **no synthetic distractor inflation**
  (the v1 "too accurate on synthetic" lesson, [[project_001_phi3_too_accurate_for_cem_matching]]).

## Per-corpus field population

| Corpus | `document` | `is_answerable` | `gold_aliases` | `evidence_spans` |
|---|---|---|---|---|
| **HotpotQA** | concatenated context | True | gold answer (+ normalized variants) | from gold **supporting sentences** → token ranges |
| **SQuAD2 (answerable)** | passage | True | gold answer spans | gold span → token range |
| **SQuAD2 (unanswerable)** | passage | **False** | `[]` | null |
| **TriviaQA / NQ (closed-book)** | `""` | True | `NormalizedAliases` / NQ short-answer set | **null** (no context) |
| **RULER** (primary long-ctx) | haystack | True (or unanswerable variant) | needle answer string | from native **`token_position_answer`** + needle token length (R2) |
| **NoLiMa** (secondary) | book haystack | True | character name | needle-sentence offset (answer↔span decoupled; R2) |

## Validation

- Closed-book ⇒ `document == ""` and `evidence_spans is null`; routing/evidence metrics
  mark not-applicable rather than fabricate (spec Edge Cases).
- `evidence_spans` indices MUST fall within the tokenized prompt length.
- RULER: pass the **model's own tokenizer** to the generator so `token_position_answer` and
  the length buckets are in the model's tokens (R2). Verification to-do: confirm the
  `qa`-task generator emits an answer-position field equivalent to `niah.py`.
- Unanswerable items still receive a `gold_aliases=[]` and an answerability flag so the
  4-way labeler can route them.

## Labeling hand-off

The adapter does **not** label; it emits the record. Labeling (`dataset/labeling.py` +
`dataset/abstention.py`) consumes the captured greedy generation + `gold_aliases` +
`is_answerable` and produces the `Label` per `data-model.md` and R3.2.
