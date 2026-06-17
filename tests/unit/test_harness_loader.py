"""End-to-end test for the frozen-cache loader (SP-0, T044).

Builds a small synthetic cache (no GPU/model), then exercises load → targets →
groups → assemble → a cross-corpus transfer split.
"""

import numpy as np

from phi3geom.analysis.harness import (
    cross_corpus_split,
    load,
    null_evidence,
)
from phi3geom.storage.bundle_cache import write_array, write_json

CV = "2.0.0"
MODELS = ["org/m1", "org/m2"]
CORPORA = ["hotpotqa", "squad2"]


def _build_cache(root):
    rng = np.random.default_rng(0)
    n = 0
    for mi, model in enumerate(MODELS):
        for ci, corpus in enumerate(CORPORA):
            for e in range(3):
                eid = f"{mi}{ci}{e:06d}"
                arr = rng.standard_normal((4, 8)).astype(np.float16)
                write_array(
                    root, capture_version=CV, model_id=model, revision_sha="r",
                    corpus_id=corpus, event_id=eid, name="hidden_answer_pos",
                    array=arr, manifest_sha256="sha-A", code_commit_sha="c",
                )
                halluc = (e == 0)  # one positive per (model,corpus)
                kw = dict(capture_version=CV, model_id=model, corpus_id=corpus, event_id=eid)
                write_json(root, name="label", obj={
                    "class_4way": "hallucination" if halluc else "correct-answer",
                    "is_hallucination": halluc,
                }, **kw)
                write_json(root, name="meta", obj={
                    "model_id": model, "corpus_id": corpus, "event_id": eid,
                    "capture_version": CV,
                }, **kw)
                n += 1
    return n


def test_load_lists_all_events(tmp_path):
    n = _build_cache(tmp_path)
    ds = load(tmp_path, CV)
    assert len(ds) == n == 12


def test_filters_by_model_and_corpus(tmp_path):
    _build_cache(tmp_path)
    assert len(load(tmp_path, CV, models=["org/m1"])) == 6
    assert len(load(tmp_path, CV, corpora=["squad2"])) == 6
    assert len(load(tmp_path, CV, models=["org/m1"], corpora=["hotpotqa"])) == 3


def test_targets_and_groups(tmp_path):
    _build_cache(tmp_path)
    ds = load(tmp_path, CV)
    assert ds.targets.sum() == 4  # one hallucination per (model,corpus) cell
    assert set(ds.corpus_ids) == set(CORPORA)
    assert set(ds.model_ids) == set(MODELS)


def test_assemble_arbitrary_width(tmp_path):
    _build_cache(tmp_path)
    ds = load(tmp_path, CV)
    X = ds.assemble(lambda b: b["hidden_answer_pos"].mean())  # scalar -> width 1
    assert X.shape == (12, 1)
    X2 = ds.assemble(lambda b: b["hidden_answer_pos"].mean(axis=0))  # width 8
    assert X2.shape == (12, 8)


def test_cross_corpus_split_over_loaded_groups(tmp_path):
    _build_cache(tmp_path)
    ds = load(tmp_path, CV)
    splits = list(cross_corpus_split(ds.corpus_ids))
    assert len(splits) == 2  # leave-one-corpus-out
    for train, test in splits:
        assert set(ds.corpus_ids[test]) and set(ds.corpus_ids[train]).isdisjoint(
            set(ds.corpus_ids[test])
        )


def test_us5_end_to_end_no_reextraction(tmp_path):
    # T043: a stub consumer loads the frozen cache, plugs in an assembler, and
    # runs the null-evidence pack + a cross-corpus split — no model, no GPU.
    _build_cache(tmp_path)
    ds = load(tmp_path, CV)
    X = ds.assemble(lambda b: b["hidden_answer_pos"].mean(axis=0))  # (12, 8)
    res = null_evidence(X, ds.targets, n_repeats=2, n_folds=2, n_perm=10, seed=0)
    assert {"cv_auroc_mean", "permutation_p", "cohens_d", "split_luck_p975"} <= res.keys()
    assert len(res["cohens_d"]) == X.shape[1]
    assert len(list(cross_corpus_split(ds.corpus_ids))) == 2
