"""``mapgen`` CLI (contracts/mapgen.md §1).

Usage::

    mapgen --seed <int> [--out <path.map>] [--params <key=val> ...]

Pure function of ``(seed, params)``. Writes ``gen_<seed>.map`` (or ``--out``)
**only after** verification passes, then prints the resolved params and a
one-line summary (rooms / open_cells / monsters / items). Never writes an
invalid ``.map``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from idledoom_mapgen.entities import ITEM_CLASSES, MONSTER_CLASSES
from idledoom_mapgen.generate import GenerationError, generate
from idledoom_mapgen.mapfile import emit_map
from idledoom_mapgen.model import MapModel
from idledoom_mapgen.params import GenParams


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    overrides = _parse_params(args.params)
    try:
        params = GenParams.from_seed(args.seed, overrides)
    except (KeyError, ValueError) as exc:
        print(f"error: bad --params: {exc}", file=sys.stderr)
        return 2

    try:
        model = generate(args.seed, params)
    except GenerationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    out_path = Path(args.out) if args.out else Path(f"gen_{args.seed}.map")
    out_path.write_text(emit_map(model), encoding="utf-8")

    _print_summary(model, out_path)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mapgen",
        description="Seeded procedural Quake .map generator (idledoom feature 004).",
    )
    parser.add_argument("--seed", type=int, required=True, help="level seed (only entropy source)")
    parser.add_argument("--out", help="output .map path (default: gen_<seed>.map)")
    parser.add_argument(
        "--params",
        nargs="*",
        default=[],
        metavar="KEY=VAL",
        help="override GenParams fields (clamped), e.g. room_count=12 loopiness=0.3",
    )
    return parser


def _parse_params(raw: Sequence[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for item in raw:
        if "=" not in item:
            raise SystemExit(f"error: --params entry must be KEY=VAL, got {item!r}")
        key, value = item.split("=", 1)
        overrides[key.strip()] = value.strip()
    return overrides


def _print_summary(model: MapModel, out_path: Path) -> None:
    monsters = sum(1 for e in model.entities if e.classname in MONSTER_CLASSES)
    items = sum(
        1
        for e in model.entities
        if e.classname in ITEM_CLASSES or e.classname.startswith(("item_", "weapon_"))
    )
    open_cells = len(model.grid.open_cells)

    print(f"wrote {out_path}")
    print(
        f"summary: rooms={len(model.rooms)} open_cells={open_cells} "
        f"monsters={monsters} items={items}"
    )
    resolved = ", ".join(f"{k}={v}" for k, v in sorted(asdict(model.params).items()))
    print(f"params: {resolved}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
