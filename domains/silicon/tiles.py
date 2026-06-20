# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Gates-to-tiles left Kan extension and SPEF telemetry validation."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from categorical.kan_extensions import Functor, LeftKanExtension
from core.category import Category
from core.types import Object


TILE_PREDICTORS = ("gate_count", "cell_area_um2", "fanout", "wirelength_um")


@dataclass
class TileAggregate:
    tile: str
    x_index: int
    y_index: int
    contributors: int
    confidence: float
    gate_count: float = 0.0
    cell_area_um2: float = 0.0
    fanout: float = 0.0
    wirelength_um: float = 0.0
    spef_cap_pf: float = 0.0


@dataclass
class TileCrosswalk:
    nx: int
    ny: int
    tiles: List[TileAggregate]
    skipped_unplaced: List[str] = field(default_factory=list)
    construction: str = "LeftKanExtension(gates->tiles)"

    def to_dict(self) -> Dict[str, object]:
        return {
            "grid": [self.nx, self.ny],
            "construction": self.construction,
            "skipped_unplaced": self.skipped_unplaced,
            "tiles": [tile.__dict__ for tile in self.tiles],
        }


@dataclass
class TileScore:
    n_tiles: int
    target: str
    spearman: Dict[str, float]
    precision_at_k: Dict[str, float]
    control_rho: float

    @property
    def best(self) -> Tuple[str, float]:
        return max(self.spearman.items(), key=lambda item: item[1]) if self.spearman else (
            "none", 0.0)

    def to_dict(self) -> Dict[str, object]:
        return {"n_tiles": self.n_tiles, "target": self.target,
                "best_predictor": self.best[0], "best_spearman": self.best[1],
                "shuffle_control": self.control_rho,
                "spearman": self.spearman, "precision_at_k": self.precision_at_k}


def _sum_colimit(values, weights):
    keys = {key for value in values for key in value}
    return {key: sum(float(value.get(key, 0.0)) * weight
                     for value, weight in zip(values, weights))
            for key in keys}


def _gate_metrics(bridge) -> Dict[str, Dict[str, float]]:
    metrics = {name: {"gate_count": 1.0,
                      "cell_area_um2": bridge.cell_area(name),
                      "fanout": 0.0, "wirelength_um": 0.0, "spef_cap_pf": 0.0}
               for name in bridge.components}
    charged_nets = set()
    for morphism in bridge.category.morphisms():
        if morphism.source not in metrics:
            continue
        row = metrics[morphism.source]
        row["fanout"] += 1.0
        row["wirelength_um"] += float(morphism.metadata.get("wirelength") or 0.0)
        net = morphism.metadata.get("net")
        key = (morphism.source, net)
        if key not in charged_nets:
            row["spef_cap_pf"] += float(morphism.metadata.get("cap_pf") or 0.0)
            charged_nets.add(key)
    return metrics


def build_tile_crosswalk(bridge, nx: int = 8, ny: int = 8) -> TileCrosswalk:
    if nx <= 0 or ny <= 0:
        raise ValueError("tile grid dimensions must be positive")
    placed = [component for component in bridge.components.values()
              if component.x is not None and component.y is not None]
    skipped = sorted(name for name, component in bridge.components.items()
                     if component.x is None or component.y is None)
    if not placed:
        return TileCrosswalk(nx, ny, [], skipped)

    min_x, max_x = min(c.x for c in placed), max(c.x for c in placed)
    min_y, max_y = min(c.y for c in placed), max(c.y for c in placed)
    span_x, span_y = max(max_x - min_x, 1.0), max(max_y - min_y, 1.0)

    gate_cat = Category(name="gates", db_path=":memory:")
    spatial_cat = Category(name="gate_tile_embedding", db_path=":memory:")
    value_cat = Category(name="tile_values", db_path=":memory:")
    F = Functor("gate_metrics", gate_cat, value_cat)
    K = Functor("gate_to_tile", gate_cat, spatial_cat)
    metrics = _gate_metrics(bridge)
    contributors: Dict[str, int] = {}

    for component in placed:
        gate = gate_cat.add(component.inst, type_name="gate")
        spatial_cat.add(component.inst, type_name="gate")
        x_index = min(nx - 1, int((component.x - min_x) / span_x * nx))
        y_index = min(ny - 1, int((component.y - min_y) / span_y * ny))
        tile_name = f"tile_{x_index}_{y_index}"
        spatial_cat.add(tile_name, type_name="physical_tile",
                        metadata={"x_index": x_index, "y_index": y_index})
        spatial_cat.connect(component.inst, tile_name, name="occupies", weight=1.0)
        F.add_object_mapping(gate, metrics[component.inst])
        K.add_object_mapping(gate, component.inst)
        contributors[tile_name] = contributors.get(tile_name, 0) + 1

    lan = LeftKanExtension(F, K, colimit=_sum_colimit)
    aggregates = []
    for tile_name in sorted(contributors):
        x_index, y_index = (int(value) for value in tile_name.split("_")[1:])
        values, confidence = lan.extend(Object(tile_name))
        values = values or {}
        aggregates.append(TileAggregate(
            tile=tile_name, x_index=x_index, y_index=y_index,
            contributors=contributors[tile_name], confidence=confidence,
            **{key: float(values.get(key, 0.0))
               for key in ("gate_count", "cell_area_um2", "fanout",
                           "wirelength_um", "spef_cap_pf")}))
    return TileCrosswalk(nx, ny, aggregates, skipped)


def score_tiles(crosswalk: TileCrosswalk, seed: int = 0) -> TileScore:
    from .scoreboard import precision_at_k, spearman

    tiles = sorted(crosswalk.tiles, key=lambda tile: tile.tile)
    target = [tile.spef_cap_pf for tile in tiles]
    if len(tiles) < 3 or not any(target):
        return TileScore(len(tiles), "spef_cap_pf", {}, {}, 0.0)
    correlations = {name: spearman([getattr(tile, name) for tile in tiles], target)
                    for name in TILE_PREDICTORS}
    k = max(1, min(10, len(tiles) // 3))
    precisions = {name: precision_at_k(
        [getattr(tile, name) for tile in tiles], target, k)
        for name in TILE_PREDICTORS}
    best_values = [getattr(tile, max(correlations, key=correlations.get)) for tile in tiles]
    shuffled = list(target); random.Random(seed).shuffle(shuffled)
    return TileScore(len(tiles), "spef_cap_pf", correlations, precisions,
                     spearman(best_values, shuffled))
