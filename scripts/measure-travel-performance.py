#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSET_PATHS = [
    "dist/travel/index.html",
    "public/data/trip-routes.geojson",
    "public/data/race-routes.geojson",
    "public/data/strava-routes.geojson",
    "public/data/strava-line-heatmap.geojson",
    "public/data/strava-line-heatmap-overview.geojson",
    "public/data/strava-heatmap.geojson",
    "public/data/trip-photos/manifest.json",
]
GEOJSON_PATHS = [
    "public/data/trip-routes.geojson",
    "public/data/race-routes.geojson",
    "public/data/strava-routes.geojson",
    "public/data/strava-line-heatmap.geojson",
    "public/data/strava-line-heatmap-overview.geojson",
    "public/data/strava-heatmap.geojson",
]


def mb(byte_count: int) -> str:
    return f"{byte_count / 1024 / 1024:.2f}MB"


def gzip_size(path: Path) -> int:
    return len(gzip.compress(path.read_bytes()))


def coordinate_count(feature: dict) -> int:
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") or []
    geometry_type = geometry.get("type")
    if geometry_type == "Point":
        return 1
    if geometry_type == "LineString":
        return len(coordinates)
    if geometry_type == "MultiLineString":
        return sum(len(line) for line in coordinates)
    return 0


def print_asset_sizes() -> None:
    print("asset sizes")
    for rel_path in ASSET_PATHS:
        path = ROOT / rel_path
        if not path.exists():
            continue
        raw = path.stat().st_size
        print(f"{rel_path} raw={mb(raw)} gzip={mb(gzip_size(path))}")


def print_geojson_counts() -> None:
    print("geojson counts")
    for rel_path in GEOJSON_PATHS:
        path = ROOT / rel_path
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        features = data.get("features") or []
        coords = sum(coordinate_count(feature) for feature in features)
        print(f"{rel_path} features={len(features)} coords={coords}")


def print_tile_stats() -> None:
    tile_root = ROOT / "public/data/route-tiles/strava-heat"
    manifest_path = tile_root / "manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text())
    tile_paths = [path for path in tile_root.rglob("*.geojson") if path.name != "manifest.json"]
    raw = sum(path.stat().st_size for path in tile_paths)
    gzipped = sum(gzip_size(path) for path in tile_paths)
    print("route tiles")
    print(
        "public/data/route-tiles/strava-heat "
        f"tiles={len(tile_paths)} raw={mb(raw)} gzip-total={mb(gzipped)} "
        f"features={manifest.get('featureCount', 0)} tiledFeatures={manifest.get('tiledFeatureCount', 0)}"
    )


def print_cache_bypass_count() -> None:
    travel_page = ROOT / "src/pages/travel.astro"
    count = travel_page.read_text().count('cache: "no-store"')
    print(f"static no-store occurrences in travel.astro={count}")


def main() -> None:
    print_asset_sizes()
    print_geojson_counts()
    print_tile_stats()
    print_cache_bypass_count()


if __name__ == "__main__":
    main()
