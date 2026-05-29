# Contract: Engine→harness event line (stdout)

The QuakeC telemetry layer emits one **tagged, newline-delimited line per
observable event** to the dedicated server's stdout/console (R4). The harness
matches the tag, parses the line, and maps it to a per-event JSONL record + the
aggregated summary. This is the boundary between what the running game knows
(sim-time `t`, payloads) and what the harness owns (identity, wall-clock,
hashing, files).

## Line format

```
@EVT|<t>|<type>|<k1>=<v1>|<k2>=<v2>|...
```

- Prefix `@EVT|` identifies a telemetry line; the harness ignores any stdout line
  without it (engine log noise is tolerated — R4 robustness).
- `<t>` — sim seconds since `level_start`, float (QuakeC `time - level_start_time`).
  Emitted as-is; the harness does **not** invent timestamps.
- `<type>` — one of `level_start｜level_end｜kill｜death｜shot｜hit｜pickup｜secret`.
- Remaining `|`-separated `key=value` pairs are the type-specific payload. Values
  are bare (numbers) or token strings (no `|` or newline); the harness coerces
  per the event schema. `null` is the literal token `null`.

## Required payload keys per type

| `type` | keys (→ `event.data`) |
|---|---|
| `level_start` | `map`, `seed`, `secrets_total` |
| `level_end` | `outcome`, `time_sec` |
| `kill` | `victim`, `weapon`, `distance` |
| `death` | `cause`, `killer` |
| `shot` | `weapon`, `target` (`null` if none) |
| `hit` | `weapon`, `target`, `damage` |
| `pickup` | `item`, `value` |
| `secret` | `secret_id` |

Naming follows `docs/telemetry.md` conventions (FR-011): `map` = BSP stem;
`weapon` = `IT_*` flag stem lowercased (`shotgun`, `super_shotgun`,
`rocket_launcher`); `victim`/monster = QuakeC classname (`monster_army`).

This-slice scoping:
- `level_start.secrets_total` = count of `trigger_secret` entities in the map
  (0 if none); it sources the summary's `stats.secrets_total` (G2), since no
  per-event channel otherwise carries the map-static total.
- `hit` events record the **agent's outgoing** damage only (→ `damage_dealt`,
  `shots_hit`); incoming damage to the agent is **not** emitted this slice, so
  `stats.damage_taken` is fixed at `0` (G1).

## Sequencing invariants

- First emitted event is `level_start`; last is `level_end` (US2 sc.1).
- A run with no terminal `level_end` line is treated as interrupted/partial —
  never `completed` (FR-010, edge case).
- Emit-on-occurrence: a `shot` precedes its `hit`; `kill`/`secret`/`pickup` fire
  at the moment the game logic detects them.

## Why stdout, not files

The harness needs UUIDs, sha256, ISO-8601, path control, schema validation, and
exit codes — all trivial in Python, painful in QuakeC. QuakeC's FRIK_FILE
builtins (`fopen`/`fputs`, already used by FrikBot for waypoints) remain a
documented fallback if stdout capture proves lossy, but stdout keeps the engine
side to "print a line" and the summary a clean function of the event stream.
