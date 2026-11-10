"""High-performance 2D spatial hash grid for O(1) proximity & collision queries."""

from __future__ import annotations

import math
from typing import Generic, Iterable, TypeVar

T = TypeVar("T")


class SpatialHashGrid(Generic[T]):
    """Fixed-cell spatial hash grid storing entities with `.x` and `.y` attributes."""

    __slots__ = ("cell_size", "inv_cell_size", "_cells")

    def __init__(self, cell_size: float = 96.0) -> None:
        self.cell_size = cell_size
        self.inv_cell_size = 1.0 / cell_size
        self._cells: dict[tuple[int, int], list[T]] = {}

    def clear(self) -> None:
        self._cells.clear()

    def _cell_coords(self, x: float, y: float) -> tuple[int, int]:
        return (int(math.floor(x * self.inv_cell_size)), int(math.floor(y * self.inv_cell_size)))

    def insert(self, entity: T) -> None:
        key = self._cell_coords(entity.x, entity.y)  # type: ignore[attr-defined]
        bucket = self._cells.get(key)
        if bucket is None:
            self._cells[key] = [entity]
        else:
            bucket.append(entity)

    def insert_all(self, entities: Iterable[T]) -> None:
        inv = self.inv_cell_size
        cells = self._cells
        floor = math.floor
        for e in entities:
            key = (int(floor(e.x * inv)), int(floor(e.y * inv)))  # type: ignore[attr-defined]
            bucket = cells.get(key)
            if bucket is None:
                cells[key] = [e]
            else:
                bucket.append(e)

    def query_radius(self, x: float, y: float, radius: float, pad_entity_radius: float = 32.0) -> list[T]:
        """Return candidate entities within `radius + pad_entity_radius` bounding cells."""
        search_r = radius + pad_entity_radius
        inv = self.inv_cell_size
        min_cx = int(math.floor((x - search_r) * inv))
        max_cx = int(math.floor((x + search_r) * inv))
        min_cy = int(math.floor((y - search_r) * inv))
        max_cy = int(math.floor((y + search_r) * inv))

        cells = self._cells
        out: list[T] = []
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                bucket = cells.get((cx, cy))
                if bucket:
                    out.extend(bucket)
        return out

    def query_nearest(
        self,
        x: float,
        y: float,
        max_radius: float,
        exclude_ids: set[int] | None = None,
    ) -> T | None:
        """Find the nearest entity within `max_radius` (center-to-center or including entity radius)."""
        candidates = self.query_radius(x, y, max_radius, pad_entity_radius=48.0)
        best: T | None = None
        best_d2 = max_radius * max_radius
        for ent in candidates:
            if exclude_ids is not None and ent.uid in exclude_ids:  # type: ignore[attr-defined]
                continue
            dx = ent.x - x  # type: ignore[attr-defined]
            dy = ent.y - y  # type: ignore[attr-defined]
            d2 = dx * dx + dy * dy
            eff_r = max_radius + getattr(ent, "radius", 0.0)
            if d2 <= eff_r * eff_r and d2 < best_d2:
                best_d2 = d2
                best = ent
        return best
