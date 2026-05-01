#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "public/data/strava-line-heatmap.geojson"
OUT_DIR = ROOT / "public/data/route-tiles/strava-heat"
MAX_MERCATOR_LAT = 85.05112878


def clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def tile_for_lng_lat(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    tiles = 2**zoom
    safe_lat = clamp(lat, -MAX_MERCATOR_LAT, MAX_MERCATOR_LAT)
    x = int((lon + 180.0) / 360.0 * tiles)
    lat_rad = math.radians(safe_lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * tiles)
    return int(clamp(x, 0, tiles - 1)), int(clamp(y, 0, tiles - 1))


def line_coordinates(feature: dict[str, Any]) -> list[list[float]]:
    geometry = feature.get("geometry") or {}
    if geometry.get("type") != "LineString":
        return []
    coordinates = geometry.get("coordinates") or []
    return [
        coordinate
        for coordinate in coordinates
        if isinstance(coordinate, list)
        and len(coordinate) >= 2
        and isinstance(coordinate[0], (int, float))
        and isinstance(coordinate[1], (int, float))
    ]


def tile_keys_for_feature(feature: dict[str, Any], zoom: int) -> list[tuple[int, int]]:
    coordinates = line_coordinates(feature)
    if len(coordinates) < 2:
        return []
    lons = [float(coordinate[0]) for coordinate in coordinates]
    lats = [float(coordinate[1]) for coordinate in coordinates]
    min_x, max_y = tile_for_lng_lat(min(lons), min(lats), zoom)
    max_x, min_y = tile_for_lng_lat(max(lons), max(lats), zoom)
    if max_x < min_x:
        min_x, max_x = max_x, min_x
    if max_y < min_y:
        min_y, max_y = max_y, min_y
    return [(x, y) for x in range(min_x, max_x + 1) for y in range(min_y, max_y + 1)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Split route-shaped heatmap GeoJSON into static Web Mercator tiles.")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--zoom", type=int, default=4)
    args = parser.parse_args()

    if args.zoom < 0:
        raise SystemExit("--zoom must be non-negative.")
    source_path = args.source if args.source.is_absolute() else ROOT / args.source
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    if not source_path.exists():
        raise SystemExit(f"Missing {source_path}.")

    source = json.loads(source_path.read_text())
    tile_features: dict[tuple[int, int], list[dict[str, Any]]] = {}
    source_features = 0
    tiled_features = 0

    for feature in source.get("features", []):
        keys = tile_keys_for_feature(feature, args.zoom)
        if not keys:
            continue
        source_features += 1
        for key in keys:
            tile_features.setdefault(key, []).append(feature)
            tiled_features += 1

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tile_paths = []
    for (x, y), features in sorted(tile_features.items()):
        tile_path = out_dir / str(args.zoom) / str(x) / f"{y}.geojson"
        tile_path.parent.mkdir(parents=True, exist_ok=True)
        tile_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")))
        tile_paths.append(f"{args.zoom}/{x}/{y}")

    manifest = {
        "source": str(source_path.relative_to(ROOT)),
        "zoom": args.zoom,
        "tileCount": len(tile_paths),
        "tiles": tile_paths,
        "featureCount": source_features,
        "tiledFeatureCount": tiled_features,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")))
    print(f"Wrote {len(tile_paths)} tiles to {out_dir}")
    print(f"Source features: {source_features}")
    print(f"Tiled feature references: {tiled_features}")


if __name__ == "__main__":
    main()
