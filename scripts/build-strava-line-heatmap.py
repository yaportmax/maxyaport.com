#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "public/data/strava-routes.geojson"
OUT = ROOT / "public/data/strava-line-heatmap.geojson"


def finite_coordinate(coordinate: Any) -> bool:
    return (
        isinstance(coordinate, list)
        and len(coordinate) >= 2
        and isinstance(coordinate[0], (int, float))
        and isinstance(coordinate[1], (int, float))
        and -180 <= coordinate[0] <= 180
        and -90 <= coordinate[1] <= 90
    )


def segment_key(start: list[float], end: list[float], precision: int) -> tuple[float, float]:
    mid_lon = (float(start[0]) + float(end[0])) / 2
    mid_lat = (float(start[1]) + float(end[1])) / 2
    return (round(mid_lon, precision), round(mid_lat, precision))


def route_weight(properties: dict[str, Any]) -> float:
    return 1.0 if properties.get("activityGroup") == "Run" else 0.82


def visual_weight(raw_weight: float, max_weight: float) -> float:
    return min(round(math.log2(1 + raw_weight), 2), max_weight)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Strava route-shaped overlap heatmap segments.")
    parser.add_argument("--in", dest="in_path", type=Path, default=IN)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--precision", type=int, default=4)
    parser.add_argument("--chunk-size", type=int, default=6)
    parser.add_argument("--max-weight", type=float, default=8.5)
    args = parser.parse_args()

    if args.chunk_size < 1:
        raise SystemExit("--chunk-size must be at least 1.")
    if not args.in_path.exists():
        raise SystemExit(f"Missing {args.in_path}. Run build-strava-routes.py first.")

    routes = json.loads(args.in_path.read_text())
    cell_weights: dict[tuple[float, float], float] = {}
    route_segments = []

    for route in routes.get("features", []):
        coordinates = [
            coordinate
            for coordinate in route.get("geometry", {}).get("coordinates", [])
            if finite_coordinate(coordinate)
        ]
        if len(coordinates) < 2:
            continue

        activity_weight = route_weight(route.get("properties", {}))
        segments = []
        for index in range(len(coordinates) - 1):
            start = coordinates[index]
            end = coordinates[index + 1]
            key = segment_key(start, end, args.precision)
            cell_weights[key] = cell_weights.get(key, 0) + activity_weight
            segments.append((start, end, key))
        route_segments.append(segments)

    features = []
    for segments in route_segments:
        for start_index in range(0, len(segments), args.chunk_size):
            chunk = segments[start_index : start_index + args.chunk_size]
            if not chunk:
                continue
            coordinates = [chunk[0][0], *[segment[1] for segment in chunk]]
            raw_weight = sum(cell_weights.get(segment[2], 1.0) for segment in chunk) / len(chunk)
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coordinates,
                    },
                    "properties": {
                        "weight": visual_weight(raw_weight, args.max_weight),
                    },
                }
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")))
    print(f"Wrote {args.out}")
    print(f"Heat line segments: {len(features)}")
    print(f"Overlap cells: {len(cell_weights)}")


if __name__ == "__main__":
    main()
