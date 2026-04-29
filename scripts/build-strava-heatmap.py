#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / ".strava-work/activities.json"
OUT = ROOT / "public/data/strava-heatmap.geojson"

ALLOWED_TYPES = {
    "Run",
    "TrailRun",
    "VirtualRun",
    "Ride",
    "GravelRide",
    "MountainBikeRide",
    "VirtualRide",
    "Hike",
    "Walk",
}


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


def sampled_public_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) < 12:
        return []
    # Remove the start/end of each route before publishing to reduce home/work leakage.
    trim = max(6, int(len(points) * 0.08))
    trimmed = points[trim:-trim]
    if not trimmed:
        return []
    stride = max(1, len(trimmed) // 60)
    return trimmed[::stride]


def main() -> None:
    if not IN.exists():
        raise SystemExit(f"Missing {IN}. Run fetch-strava-activities.py first.")

    activities = json.loads(IN.read_text())
    cells: dict[tuple[float, float], float] = {}
    for activity in activities:
        if activity.get("type") not in ALLOWED_TYPES:
            continue
        polyline = (activity.get("map") or {}).get("summary_polyline")
        if not polyline:
            continue
        try:
            points = sampled_public_points(decode_polyline(polyline))
        except (IndexError, TypeError, ValueError):
            continue
        weight = 1.0 if activity.get("type") in {"Run", "TrailRun", "VirtualRun"} else 0.75
        for lat, lon in points:
            key = (round(lon, 4), round(lat, 4))
            cells[key] = cells.get(key, 0) + weight

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"weight": min(round(weight, 2), 6)},
        }
        for (lon, lat), weight in sorted(cells.items())
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")))
    print(f"Wrote {OUT}")
    print(f"Activities read: {len(activities)}")
    print(f"Heatmap points: {len(features)}")


if __name__ == "__main__":
    main()
