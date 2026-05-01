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


def activity_bucket(properties: dict[str, Any]) -> str:
    activity = str(properties.get("activityGroup") or properties.get("type") or "").lower()
    if "swim" in activity:
        return "swim"
    if any(term in activity for term in ("run", "walk", "hike", "foot", "snowshoe")):
        return "run"
    if any(term in activity for term in ("ride", "bike", "cycling", "ski", "snowboard", "skate", "surf", "wheelchair", "handcycle")):
        return "ride"
    return "other"


def route_weight(properties: dict[str, Any]) -> float:
    bucket = activity_bucket(properties)
    if bucket == "run":
        return 1.0
    if bucket == "swim":
        return 0.9
    if bucket == "ride":
        return 0.82
    return 0.78


def visual_weight(raw_weight: float, max_weight: float) -> float:
    return min(round(math.log2(1 + raw_weight), 2), max_weight)


def mixed_color(run_weight: float, swim_weight: float, ride_weight: float, other_weight: float) -> str:
    total = run_weight + swim_weight + ride_weight + other_weight
    if total <= 0:
        return "#d7ae45"
    colors = {
        "run": (216, 76, 72),
        "swim": (235, 190, 66),
        "ride": (22, 137, 238),
        "other": (215, 174, 69),
    }
    red = round(
        (
            colors["run"][0] * run_weight
            + colors["swim"][0] * swim_weight
            + colors["ride"][0] * ride_weight
            + colors["other"][0] * other_weight
        )
        / total
    )
    green = round(
        (
            colors["run"][1] * run_weight
            + colors["swim"][1] * swim_weight
            + colors["ride"][1] * ride_weight
            + colors["other"][1] * other_weight
        )
        / total
    )
    blue = round(
        (
            colors["run"][2] * run_weight
            + colors["swim"][2] * swim_weight
            + colors["ride"][2] * ride_weight
            + colors["other"][2] * other_weight
        )
        / total
    )
    return f"#{red:02x}{green:02x}{blue:02x}"


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
    cell_weights: dict[tuple[float, float], dict[str, float]] = {}
    route_segments = []

    for route in routes.get("features", []):
        coordinates = [
            coordinate
            for coordinate in route.get("geometry", {}).get("coordinates", [])
            if finite_coordinate(coordinate)
        ]
        if len(coordinates) < 2:
            continue

        properties = route.get("properties", {})
        activity_weight = route_weight(properties)
        bucket = activity_bucket(properties)
        segments = []
        for index in range(len(coordinates) - 1):
            start = coordinates[index]
            end = coordinates[index + 1]
            key = segment_key(start, end, args.precision)
            weights = cell_weights.setdefault(key, {"run": 0.0, "swim": 0.0, "ride": 0.0, "other": 0.0})
            weights[bucket] = weights.get(bucket, 0.0) + activity_weight
            segments.append((start, end, key))
        route_segments.append(segments)

    features = []
    for segments in route_segments:
        for start_index in range(0, len(segments), args.chunk_size):
            chunk = segments[start_index : start_index + args.chunk_size]
            if not chunk:
                continue
            coordinates = [chunk[0][0], *[segment[1] for segment in chunk]]
            raw_run_weight = sum(cell_weights.get(segment[2], {}).get("run", 0.0) for segment in chunk) / len(chunk)
            raw_swim_weight = sum(cell_weights.get(segment[2], {}).get("swim", 0.0) for segment in chunk) / len(chunk)
            raw_ride_weight = sum(cell_weights.get(segment[2], {}).get("ride", 0.0) for segment in chunk) / len(chunk)
            raw_other_weight = sum(cell_weights.get(segment[2], {}).get("other", 0.0) for segment in chunk) / len(chunk)
            raw_weight = raw_run_weight + raw_swim_weight + raw_ride_weight + raw_other_weight
            if raw_weight <= 0:
                continue
            run_weight = visual_weight(raw_run_weight, args.max_weight)
            swim_weight = visual_weight(raw_swim_weight, args.max_weight)
            ride_weight = visual_weight(raw_ride_weight, args.max_weight)
            other_weight = visual_weight(raw_other_weight, args.max_weight)
            total_weight = visual_weight(raw_weight, args.max_weight)
            active_total = raw_run_weight + raw_swim_weight + raw_ride_weight + raw_other_weight
            ride_mix = raw_ride_weight / active_total if active_total > 0 else 0.0
            swim_mix = raw_swim_weight / active_total if active_total > 0 else 0.0
            dominant = max(
                (("run", raw_run_weight), ("swim", raw_swim_weight), ("ride", raw_ride_weight), ("other", raw_other_weight)),
                key=lambda item: item[1],
            )[0]
            active_buckets = sum(1 for value in (raw_run_weight, raw_swim_weight, raw_ride_weight, raw_other_weight) if value > 0)
            if active_buckets > 1:
                activity_mix = "overlap"
            elif raw_swim_weight > 0:
                activity_mix = "swim"
            elif raw_ride_weight > 0:
                activity_mix = "ride"
            elif raw_run_weight > 0:
                activity_mix = "run"
            else:
                activity_mix = "other"
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coordinates,
                    },
                    "properties": {
                        "weight": total_weight,
                        "runWeight": run_weight,
                        "swimWeight": swim_weight,
                        "rideWeight": ride_weight,
                        "otherWeight": other_weight,
                        "rideMix": round(ride_mix, 3),
                        "swimMix": round(swim_mix, 3),
                        "dominantActivity": dominant,
                        "activityMix": activity_mix,
                        "heatColor": mixed_color(raw_run_weight, raw_swim_weight, raw_ride_weight, raw_other_weight),
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
