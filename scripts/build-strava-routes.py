#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / ".strava-work/activities.json"
OUT = ROOT / "public/data/strava-routes.geojson"

RUN_TYPES = {"Run", "TrailRun"}
RIDE_TYPES = {"Ride", "GravelRide", "MountainBikeRide"}
ALLOWED_TYPES = RUN_TYPES | RIDE_TYPES


def decode_polyline(polyline: str) -> list[tuple[float, float]]:
    index = 0
    lat = 0
    lon = 0
    points: list[tuple[float, float]] = []

    while index < len(polyline):
        result = 0
        shift = 0
        while True:
            value = ord(polyline[index]) - 63
            index += 1
            result |= (value & 0x1F) << shift
            shift += 5
            if value < 0x20:
                break
        lat += ~(result >> 1) if result & 1 else result >> 1

        result = 0
        shift = 0
        while True:
            value = ord(polyline[index]) - 63
            index += 1
            result |= (value & 0x1F) << shift
            shift += 5
            if value < 0x20:
                break
        lon += ~(result >> 1) if result & 1 else result >> 1
        points.append((lat / 1e5, lon / 1e5))

    return points


def public_route_points(points: list[tuple[float, float]], max_points: int) -> list[tuple[float, float]]:
    if len(points) < 12:
        return []

    # Keep public route lines useful while avoiding publishing exact starts/ends.
    trim = max(6, int(len(points) * 0.08))
    trimmed = points[trim:-trim]
    if len(trimmed) < 2:
        return []

    if len(trimmed) <= max_points:
        return trimmed

    stride = len(trimmed) / (max_points - 1)
    sampled = [trimmed[round(index * stride)] for index in range(max_points - 1)]
    sampled.append(trimmed[-1])
    return sampled


def activity_group(activity_type: str) -> str:
    return "Ride" if activity_type in RIDE_TYPES else "Run"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build public Strava run/ride route LineStrings.")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--max-points", type=int, default=220)
    args = parser.parse_args()

    if not IN.exists():
        raise SystemExit(f"Missing {IN}. Run fetch-strava-activities.py first.")
    if args.max_points < 2:
        raise SystemExit("--max-points must be at least 2.")

    activities = json.loads(IN.read_text())
    features = []

    for activity in activities:
        activity_type = activity.get("type")
        if activity_type not in ALLOWED_TYPES:
            continue

        polyline = (activity.get("map") or {}).get("summary_polyline")
        if not polyline:
            continue

        try:
            points = public_route_points(decode_polyline(polyline), args.max_points)
        except (IndexError, TypeError, ValueError):
            continue
        if len(points) < 2:
            continue

        coordinates = [[round(lon, 5), round(lat, 5)] for lat, lon in points]
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coordinates},
                "properties": {
                    "id": activity.get("id"),
                    "name": activity.get("name") or "Strava activity",
                    "type": activity_type,
                    "activityGroup": activity_group(activity_type),
                    "startDate": activity.get("start_date_local") or activity.get("start_date"),
                    "distanceMeters": round(float(activity.get("distance") or 0), 1),
                },
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")))
    print(f"Wrote {args.out}")
    print(f"Activities read: {len(activities)}")
    print(f"Routes written: {len(features)}")


if __name__ == "__main__":
    main()
