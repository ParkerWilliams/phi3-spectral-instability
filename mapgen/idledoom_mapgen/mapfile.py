"""Quake ``.map`` text emission (research R3).

``emit_map(model)`` renders the standard (non-Valve-220) ``.map`` format:

* ``worldspawn`` first, with ``"classname" "worldspawn"`` and
  ``"wad" "librequake.wad"``, followed by every world brush;
* then each point entity ``{ "classname" ... "origin" "x y z" ... }``.

Each :class:`Brush` is an axis-aligned box rendered as 6 planes. The per-plane
format is::

    ( x y z ) ( x y z ) ( x y z ) TEX 0 0 0 1 1

with integer coordinates and outward-facing normals (standard box winding).

# NOTE: plane winding to be confirmed on first local qbsp compile (T015)
"""

from __future__ import annotations

from idledoom_mapgen.model import Brush, MapEntity, MapModel, Vec3

WAD_NAME = "librequake.wad"


def emit_map(model: MapModel) -> str:
    """Render the full ``.map`` text for ``model`` (deterministic)."""
    lines: list[str] = []
    _emit_worldspawn(lines, model.brushes)
    for ent in model.entities:
        _emit_point_entity(lines, ent)
    # Trailing newline for a clean POSIX text file.
    return "\n".join(lines) + "\n"


def _emit_worldspawn(lines: list[str], brushes: list[Brush]) -> None:
    lines.append("{")
    lines.append('"classname" "worldspawn"')
    lines.append(f'"wad" "{WAD_NAME}"')
    for brush in brushes:
        _emit_brush(lines, brush)
    lines.append("}")


def _emit_point_entity(lines: list[str], ent: MapEntity) -> None:
    lines.append("{")
    lines.append(f'"classname" "{ent.classname}"')
    ox, oy, oz = ent.origin
    lines.append(f'"origin" "{ox} {oy} {oz}"')
    # Deterministic key order for byte-identical output.
    for key in sorted(ent.extras):
        lines.append(f'"{key}" "{ent.extras[key]}"')
    lines.append("}")


def _emit_brush(lines: list[str], brush: Brush) -> None:
    lines.append("{")
    for p0, p1, p2 in _box_planes(brush.mins, brush.maxs):
        lines.append(
            f"{_pt(p0)} {_pt(p1)} {_pt(p2)} {brush.tex} 0 0 0 1 1"
        )
    lines.append("}")


def _box_planes(mins: Vec3, maxs: Vec3) -> list[tuple[Vec3, Vec3, Vec3]]:
    """Six planes for an axis-aligned box, normals pointing outward.

    Each triple of points winds clockwise when viewed from outside the brush,
    which is the convention qbsp expects for the face normal (research R3).

    # NOTE: plane winding to be confirmed on first local qbsp compile (T015)
    """
    x0, y0, z0 = mins
    x1, y1, z1 = maxs
    return [
        # Top (+Z): normal up.
        ((x0, y1, z1), (x1, y1, z1), (x1, y0, z1)),
        # Bottom (-Z): normal down.
        ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0)),
        # Front (-Y): normal toward -Y.
        ((x0, y0, z0), (x0, y0, z1), (x1, y0, z1)),
        # Back (+Y): normal toward +Y.
        ((x1, y1, z0), (x1, y1, z1), (x0, y1, z1)),
        # Left (-X): normal toward -X.
        ((x0, y1, z0), (x0, y1, z1), (x0, y0, z1)),
        # Right (+X): normal toward +X.
        ((x1, y0, z0), (x1, y0, z1), (x1, y1, z1)),
    ]


def _pt(p: Vec3) -> str:
    return f"( {p[0]} {p[1]} {p[2]} )"
