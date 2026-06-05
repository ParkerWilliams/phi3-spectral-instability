"""In-memory data structures the generator builds (data-model.md "Entities").

All coordinates are Quake units unless a field is documented as *cells*. The
grid is indexed ``grid[x][y]``; world units are ``cell * C``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from idledoom_mapgen.params import GenParams

Vec3 = tuple[int, int, int]
Cell = tuple[int, int]
Edge = tuple[int, int]


@dataclass(frozen=True)
class Room:
    """A non-overlapping axis-aligned rectangle on the grid (cell coords)."""

    id: int
    x: int
    y: int
    w: int
    h: int

    @property
    def center(self) -> Cell:
        """The room's center cell (used as the graph node)."""
        return (self.x + self.w // 2, self.y + self.h // 2)

    def cells(self) -> list[Cell]:
        """Every grid cell this room occupies."""
        return [
            (cx, cy)
            for cx in range(self.x, self.x + self.w)
            for cy in range(self.y, self.y + self.h)
        ]

    def contains(self, cell: Cell) -> bool:
        cx, cy = cell
        return self.x <= cx < self.x + self.w and self.y <= cy < self.y + self.h


@dataclass
class Grid:
    """A ``w``x``h`` lattice of open/solid cells, indexed ``[x][y]``."""

    w: int
    h: int
    open: list[list[bool]]

    @classmethod
    def solid(cls, w: int, h: int) -> Grid:
        """A fully-solid grid (nothing open yet)."""
        return cls(w=w, h=h, open=[[False] * h for _ in range(w)])

    def in_bounds(self, cell: Cell) -> bool:
        cx, cy = cell
        return 0 <= cx < self.w and 0 <= cy < self.h

    def is_open(self, cell: Cell) -> bool:
        cx, cy = cell
        if not (0 <= cx < self.w and 0 <= cy < self.h):
            return False
        return self.open[cx][cy]

    def set_open(self, cell: Cell) -> None:
        cx, cy = cell
        self.open[cx][cy] = True

    @property
    def open_cells(self) -> list[Cell]:
        """All open cells, in deterministic (x, then y) order."""
        return [(x, y) for x in range(self.w) for y in range(self.h) if self.open[x][y]]


@dataclass(frozen=True)
class Brush:
    """An axis-aligned box, emitted as 6 planes (world units)."""

    mins: Vec3
    maxs: Vec3
    tex: str


@dataclass(frozen=True)
class MapEntity:
    """A point entity (spawn / monster / item / light) at a world origin."""

    classname: str
    origin: Vec3
    extras: dict[str, int] = field(default_factory=dict)


@dataclass
class MapModel:
    """The complete, verifiable, emittable level (data-model.md "MapModel")."""

    params: GenParams
    rooms: list[Room]
    edges: list[Edge]
    grid: Grid
    brushes: list[Brush]
    entities: list[MapEntity]
