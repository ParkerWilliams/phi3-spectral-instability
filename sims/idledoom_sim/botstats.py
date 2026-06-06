"""Machine-readable catalogue of tunable cvars (mirror of ``docs/bot-stats.md``).

Single source of truth for the harness's clamping and defaults. Every ``bot_*``
value is clamped to its documented range **before** it is set on the engine
command line and **before** it is recorded in the summary's ``bot_config``
(FR-007/FR-008). Keep this in sync with ``docs/bot-stats.md`` — when a stat's
range or default changes there, change it here too.

Reference: specs/001-headless-sim-telemetry/contracts/cvars.md
"""

from __future__ import annotations

from dataclasses import dataclass

BotValue = float | int | bool
# Override inputs may arrive as strings (CLI --bot.<name> VALUE); clamp() coerces
# them to the stat's BotValue type.
BotInput = BotValue | str


@dataclass(frozen=True)
class BotStat:
    """One tunable ``bot_*`` cvar and its documented range."""

    name: str
    type: str  # "float" | "int" | "bool"
    default: BotValue
    minimum: float | None = None  # None for bool
    maximum: float | None = None  # None for bool

    def clamp(self, value: BotInput) -> BotValue:
        """Coerce ``value`` to this stat's type and clamp it to range (FR-008).

        Accepts CLI string values: for bool stats "false"/"0"/"no"/"off" are
        False (a plain ``bool("false")`` would wrongly be True); numeric strings
        parse for int/float.
        """
        if self.type == "bool":
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "on")
            return bool(value)
        if self.type == "int":
            ivalue = int(round(float(value)))
            assert self.minimum is not None and self.maximum is not None
            return max(int(self.minimum), min(int(self.maximum), ivalue))
        # float
        fvalue = float(value)
        assert self.minimum is not None and self.maximum is not None
        return max(self.minimum, min(self.maximum, fvalue))


# Catalogue — mirrors docs/bot-stats.md (Mechanical / Movement / Knowledge /
# Decision-making / Combat). Per-weapon bot_weapon_affinity_<wpn> is deferred
# (one row per weapon when finalized) and intentionally omitted here.
_STATS: tuple[BotStat, ...] = (
    # Mechanical skill
    BotStat("bot_accuracy", "float", 0.3, 0.0, 1.0),
    BotStat("bot_reaction_ms", "int", 500, 50, 1000),
    BotStat("bot_tracking_skill", "float", 0.2, 0.0, 1.0),
    BotStat("bot_prediction_skill", "float", 0.0, 0.0, 1.0),
    # Movement
    BotStat("bot_move_speed_mult", "float", 1.0, 0.5, 1.5),
    BotStat("bot_strafe_skill", "float", 0.0, 0.0, 1.0),
    BotStat("bot_rocket_jump", "bool", False),
    BotStat("bot_bunny_hop", "bool", False),
    BotStat("bot_circle_strafe", "float", 0.0, 0.0, 1.0),
    # Knowledge
    BotStat("bot_map_awareness", "float", 0.3, 0.0, 1.0),
    BotStat("bot_secret_knowledge", "float", 0.0, 0.0, 1.0),
    BotStat("bot_item_timing", "bool", False),
    BotStat("bot_weapon_priority_skill", "float", 0.5, 0.0, 1.0),
    # Decision-making
    BotStat("bot_aggression", "float", 0.5, 0.0, 1.0),
    BotStat("bot_retreat_threshold", "float", 0.3, 0.0, 1.0),
    BotStat("bot_target_priority_skill", "float", 0.5, 0.0, 1.0),
    BotStat("bot_resource_management", "float", 0.3, 0.0, 1.0),
    # Combat
    BotStat("bot_splash_awareness", "float", 0.0, 0.0, 1.0),
    # Progression (master dial — feature 003). THE leveling-up stat; drives
    # human-like motion feel (locomotion now; aim/tech later) and will fan out to
    # the per-axis stats above over time. Fresh-game default 0.0 (a tepid newbie);
    # sim configs pin it to 1.0 so nav/combat metrics aren't throttled.
    BotStat("bot_competence", "float", 0.0, 0.0, 1.0),
    # Debug/measurement toggle (feature 004 locomotion). 0 (default) = analog steering
    # on; 1 = legacy 8-way key quantization. Registered here so the wall-scrape A/B
    # (stats.traversal.wall_contact with analog on vs off) is runnable from a sim config.
    BotStat("bot_analog_off", "bool", False),
)

BOT_STATS: dict[str, BotStat] = {s.name: s for s in _STATS}

# sim_* control cvars (dev-only knobs; documented in cvars.md and bot-stats.md
# notes). Not clamped like bot_* — they are harness-set run controls.
SIM_CVARS: tuple[str, ...] = (
    "sim_mode",
    "sim_seed",
    "sim_time_limit",
    "sim_nav_regen",  # feature 002 (T009): force nav-graph regeneration
)


def default_bot_config() -> dict[str, BotValue]:
    """The full ``bot_config`` with every catalogued stat at its default."""
    return {s.name: s.default for s in _STATS}


def clamp_bot_value(name: str, value: BotInput) -> BotValue:
    """Clamp a single ``bot_*`` value to its documented range (FR-008).

    Raises ``KeyError`` for an unknown stat name so typos in configs/CLI fail
    loudly rather than being silently accepted.
    """
    return BOT_STATS[name].clamp(value)
