"""idledoom headless simulation harness (feature 001-headless-sim-telemetry).

Owns everything awkward in QuakeC: UUIDs, sha256 config hashing, ISO-8601
wall-clock timing, clamping bot_* against documented ranges, JSON Schema
validation, exit codes, and the time-limit watchdog. The QuakeC layer only
emits tagged stdout event lines; this package turns them into the per-run
summary + event stream. See specs/001-headless-sim-telemetry/.
"""
