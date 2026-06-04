"""US2 / SC-003: summary stats are a pure, exact aggregate of the event stream.

Each assertion pins a stat to an independent fold over the same events, so any
drift between `aggregate()` and the raw stream fails here (zero-discrepancy bar).
"""

from __future__ import annotations

from idledoom_sim.telemetry import ParsedEvent, aggregate, stream_invariant_ok


def _sample_stream() -> list[ParsedEvent]:
    """A representative run: shots/hits across weapons, kills, pickups, secret, death."""
    return [
        ParsedEvent(0.0, "level_start", {"map": "lq_e1m1", "seed": 1, "secrets_total": 3}),
        ParsedEvent(1.0, "shot", {"weapon": "shotgun", "target": "monster_army"}),
        ParsedEvent(1.1, "hit", {"weapon": "shotgun", "target": "monster_army", "damage": 10}),
        ParsedEvent(2.0, "shot", {"weapon": "shotgun", "target": None}),  # missed
        ParsedEvent(3.0, "shot", {"weapon": "super_shotgun", "target": "monster_dog"}),
        ParsedEvent(3.1, "hit", {"weapon": "super_shotgun", "target": "monster_dog", "damage": 24}),
        ParsedEvent(
            3.2, "kill",
            {"victim": "monster_dog", "weapon": "super_shotgun", "distance": 128.0},
        ),
        ParsedEvent(4.0, "pickup", {"item": "item_health", "value": 25}),
        ParsedEvent(4.5, "pickup", {"item": "weapon_nailgun", "value": 1}),
        ParsedEvent(5.0, "secret", {"secret_id": 1}),
        ParsedEvent(6.0, "kill", {"victim": "monster_army", "weapon": "shotgun", "distance": 64.0}),
        ParsedEvent(7.0, "death", {"cause": "monster_army", "killer": "monster_army"}),
        ParsedEvent(8.0, "level_end", {"outcome": "died", "time_sec": 8.0}),
    ]


def test_counts_reconcile_with_events() -> None:
    events = _sample_stream()
    stats = aggregate(events)
    assert stats["kills"] == sum(1 for e in events if e.type == "kill")            # 2
    assert stats["deaths"] == sum(1 for e in events if e.type == "death")          # 1
    assert stats["shots_fired"] == sum(1 for e in events if e.type == "shot")      # 3
    assert stats["shots_hit"] == sum(1 for e in events if e.type == "hit")         # 2
    assert stats["items_collected"] == sum(1 for e in events if e.type == "pickup")  # 2
    assert stats["secrets_found"] == sum(1 for e in events if e.type == "secret")    # 1


def test_accuracy_is_hits_over_shots_4dp() -> None:
    assert aggregate(_sample_stream())["accuracy"] == round(2 / 3, 4)  # 0.6667


def test_accuracy_zero_when_no_shots() -> None:
    events = [
        ParsedEvent(0.0, "level_start", {"map": "m", "seed": 1, "secrets_total": 0}),
        ParsedEvent(1.0, "level_end", {"outcome": "timeout", "time_sec": 1.0}),
    ]
    assert aggregate(events)["accuracy"] == 0.0  # zero denominator -> 0, not error


def test_damage_dealt_sums_hit_damage() -> None:
    assert aggregate(_sample_stream())["damage_dealt"] == 10 + 24


def test_damage_taken_fixed_zero_this_slice() -> None:  # G1
    assert aggregate(_sample_stream())["damage_taken"] == 0


def test_weapon_usage_groups_shots_hits_damage() -> None:
    wu = aggregate(_sample_stream())["weapon_usage"]
    assert wu["shotgun"] == {"shots": 2, "hits": 1, "damage": 10}
    assert wu["super_shotgun"] == {"shots": 1, "hits": 1, "damage": 24}


def test_deaths_by_cause_grouped() -> None:
    assert aggregate(_sample_stream())["deaths_by_cause"] == {"monster_army": 1}


def test_secrets_total_from_level_start_secrets_found_from_events() -> None:  # G2
    stats = aggregate(_sample_stream())
    assert stats["secrets_total"] == 3  # map-static, from level_start payload
    assert stats["secrets_found"] == 1  # from secret events


def test_stream_invariant_first_start_last_end() -> None:  # US2 sc.1
    assert stream_invariant_ok(_sample_stream()) is True
    assert stream_invariant_ok([]) is False
    only_kill = [ParsedEvent(1.0, "kill", {"victim": "x", "weapon": "y", "distance": 0.0})]
    assert stream_invariant_ok(only_kill) is False
