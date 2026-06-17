"""CLI: the SC-001 manifest-completeness gate.

Exits non-zero if any catalog metric is unmapped or points at an unknown bundle
field. Run before any full capture run (and as a CI check).

    python -m phi3geom.scripts.check_manifest_completeness            # full §5
    python -m phi3geom.scripts.check_manifest_completeness --subset us1
"""

from __future__ import annotations

import argparse
import sys

from phi3geom.extraction.manifest import (
    PROGRAM_CATALOG_METRICS,
    US1_METRIC_SUBSET,
    check_completeness,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture-manifest completeness gate")
    parser.add_argument("--subset", choices=("full", "us1"), default="full")
    args = parser.parse_args(argv)

    catalog = US1_METRIC_SUBSET if args.subset == "us1" else PROGRAM_CATALOG_METRICS
    result = check_completeness(catalog)

    if result.complete:
        print(f"[manifest] COMPLETE — {len(catalog)} metrics ({args.subset}) all mapped.")
        return 0
    print(f"[manifest] INCOMPLETE ({args.subset}):", file=sys.stderr)
    if result.missing_metrics:
        print(f"  unmapped metrics: {', '.join(result.missing_metrics)}", file=sys.stderr)
    if result.unknown_fields:
        print(f"  unknown bundle fields: {', '.join(result.unknown_fields)}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
