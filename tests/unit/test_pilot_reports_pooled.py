# tests/unit/test_pilot_reports_pooled.py
from __future__ import annotations

import json

import numpy as np

from phi3geom.analysis.pooled_detector import fit_pooled_detector
from phi3geom.reporting.pilot_reports import (
    write_pooled_auroc,
    write_distance_diagnostic,
    write_confound_audit,
)


def _data(n=240, seed=0):
    rng = np.random.default_rng(seed)
    labels = np.zeros(n, dtype=bool); labels[::2] = True
    feats = rng.standard_normal((n, 7)).astype(np.float64)
    feats[labels, 0] += 3.0
    distances = rng.integers(20, 3000, size=n)
    doc_lengths = rng.integers(100, 2000, size=n)
    return feats, labels, distances, doc_lengths


def test_pooled_auroc_report(tmp_path):
    feats, labels, *_ = _data()
    fit = fit_pooled_detector(feats, labels, random_state=0, n_bootstrap=100)
    p = write_pooled_auroc(fit, out_dir=tmp_path)
    payload = json.loads(p.read_text())
    assert payload["auroc"] == fit.auroc
    assert payload["beats_chance"] is fit.beats_chance
    assert "auroc_ci_lower" in payload


def test_distance_diagnostic_report(tmp_path):
    feats, labels, distances, _ = _data()
    fit = fit_pooled_detector(feats, labels, random_state=0, n_bootstrap=50)
    p = write_distance_diagnostic(
        coefficients=fit.coefficients, intercept=fit.intercept,
        feature_matrix=feats, distances=distances, labels=labels, out_dir=tmp_path,
    )
    payload = json.loads(p.read_text())
    # keys are diagnostic bin labels; each carries an auroc + n
    assert all("auroc" in v and "n" in v for v in payload.values())


def test_confound_audit_report(tmp_path):
    feats, labels, distances, doc_lengths = _data()
    fit = fit_pooled_detector(feats, labels, random_state=0, n_bootstrap=50)
    p = write_confound_audit(
        geometry_auroc=fit.auroc, labels=labels,
        doc_lengths=doc_lengths, distances=distances,
        random_state=0, out_dir=tmp_path,
    )
    payload = json.loads(p.read_text())
    assert "geometry_auroc" in payload
    assert "confound_only_auroc" in payload
    assert isinstance(payload["is_suspicious"], bool)
