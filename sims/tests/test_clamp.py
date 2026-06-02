"""US3 / FR-007/FR-008: bot_* overrides are clamped, recorded, and hashed stably."""

from __future__ import annotations

import pytest

import harness
from idledoom_sim.botstats import clamp_bot_value
from idledoom_sim.config import build_bot_config, compute_config_hash

# --- clamping (FR-008) -----------------------------------------------------


def test_out_of_range_float_is_clamped_into_bot_config() -> None:
    assert build_bot_config({"bot_accuracy": 5})["bot_accuracy"] == 1.0   # -> max
    assert build_bot_config({"bot_accuracy": -2})["bot_accuracy"] == 0.0  # -> min


def test_out_of_range_int_is_clamped() -> None:
    assert clamp_bot_value("bot_reaction_ms", 9999) == 1000
    assert clamp_bot_value("bot_reaction_ms", 10) == 50


def test_unknown_stat_raises() -> None:
    with pytest.raises(KeyError):
        clamp_bot_value("bot_not_a_real_stat", 1)


def test_bool_string_values_coerce_correctly() -> None:
    # CLI passes strings; "false"/"0" must not silently become True.
    assert clamp_bot_value("bot_rocket_jump", "false") is False
    assert clamp_bot_value("bot_rocket_jump", "0") is False
    assert clamp_bot_value("bot_rocket_jump", "true") is True
    assert clamp_bot_value("bot_rocket_jump", "1") is True


# --- config_hash (FR-007, US3 sc.2) ----------------------------------------


def test_identical_configs_hash_equal_different_configs_differ() -> None:
    a = build_bot_config({"bot_accuracy": 0.5})
    b = build_bot_config({"bot_accuracy": 0.5})
    c = build_bot_config({"bot_accuracy": 0.9})
    assert compute_config_hash(a) == compute_config_hash(b)
    assert compute_config_hash(a) != compute_config_hash(c)
    assert len(compute_config_hash(a)) == 64


def test_clamped_equivalence_hashes_equal() -> None:
    # Two different out-of-range inputs that clamp to the same value hash equal.
    over = build_bot_config({"bot_accuracy": 5})
    at_max = build_bot_config({"bot_accuracy": 1.0})
    assert compute_config_hash(over) == compute_config_hash(at_max)


# --- CLI override extraction (T034) ----------------------------------------


def test_extract_bot_overrides_pulls_pairs() -> None:
    overrides, rest = harness.extract_bot_overrides(
        ["run", "--config", "c.toml", "--bot.bot_accuracy", "0.9"]
    )
    assert overrides == {"bot_accuracy": "0.9"}
    assert rest == ["run", "--config", "c.toml"]


def test_extract_bot_overrides_supports_equals_form() -> None:
    overrides, rest = harness.extract_bot_overrides(["run", "--bot.bot_accuracy=0.1"])
    assert overrides == {"bot_accuracy": "0.1"}
    assert rest == ["run"]


def test_extract_bot_overrides_missing_value_raises() -> None:
    with pytest.raises(ValueError):
        harness.extract_bot_overrides(["run", "--bot.bot_accuracy"])
