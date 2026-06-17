"""Contract test for the capture-manifest completeness gate (SP-0, T010/T013, SC-001)."""

from phi3geom.extraction.manifest import (
    BUNDLE_FIELDS,
    METRIC_TO_FIELD,
    PROGRAM_CATALOG_METRICS,
    US1_METRIC_SUBSET,
    check_completeness,
)
from phi3geom.scripts.check_manifest_completeness import main as cli_main


def test_full_catalog_is_complete():
    res = check_completeness(PROGRAM_CATALOG_METRICS)
    assert res.complete
    assert res.missing_metrics == ()
    assert res.unknown_fields == ()


def test_us1_subset_is_complete():
    res = check_completeness(US1_METRIC_SUBSET)
    assert res.complete


def test_every_mapping_targets_a_known_bundle_field():
    for metric, field in METRIC_TO_FIELD.items():
        assert field in BUNDLE_FIELDS, f"{metric} -> unknown field {field}"


def test_missing_metric_is_flagged():
    res = check_completeness(PROGRAM_CATALOG_METRICS | {"a_new_unmapped_metric"})
    assert not res.complete
    assert "a_new_unmapped_metric" in res.missing_metrics


def test_unknown_field_is_flagged():
    res = check_completeness(
        {"x"}, metric_to_field={"x": "not_a_real_bundle_field"}
    )
    assert not res.complete
    assert "not_a_real_bundle_field" in res.unknown_fields


def test_cli_exit_codes():
    assert cli_main(["--subset", "full"]) == 0
    assert cli_main(["--subset", "us1"]) == 0
