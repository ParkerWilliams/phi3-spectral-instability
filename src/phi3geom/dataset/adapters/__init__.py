"""Corpus adapters (SP-0).

Each adapter yields the common ``DocQAEventRecord`` for one regime (HotpotQA,
SQuAD2 ±answerable, closed-book TriviaQA/NQ, long-context RULER/NoLiMa) so the
capture path is corpus-agnostic. See contracts/corpus-adapter.md.
"""
