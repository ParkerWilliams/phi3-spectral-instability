"""idledoom_mapgen — seeded procedural Quake .map generator (feature 004).

A pure, deterministic generator: ``generate(seed, params)`` lays out box rooms
and corridors on a grid, seals them into brush geometry, populates the level
with spawn/monsters/items/lights, statically verifies the result, and
``emit_map`` renders a Quake ``.map`` text. Standard library only.
"""

from idledoom_mapgen.generate import generate
from idledoom_mapgen.mapfile import emit_map
from idledoom_mapgen.model import Brush, Grid, MapEntity, MapModel, Room
from idledoom_mapgen.params import GenParams
from idledoom_mapgen.verify import verify

__all__ = [
    "Brush",
    "GenParams",
    "Grid",
    "MapEntity",
    "MapModel",
    "Room",
    "emit_map",
    "generate",
    "verify",
]
