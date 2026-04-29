#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVITIES = ROOT / ".strava-work/activities.json"
PRIVATE_OUT = ROOT / ".strava-work/gpx"
PUBLIC_OUT = ROOT / "public/data/strava-activities"


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


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "activity"


def gpx_for_activity(activity: dict, points: list[tuple[float, float]]) -> str:
    name = html.escape(str(activity.get("name") or "Strava activity"))
    activity_type = html.escape(str(activity.get("type") or "Activity"))
    time = html.escape(str(activity.get("start_date") or ""))
    track = "\n".join(f'      <trkpt lat="{lat:.6f}" lon="{lon:.6f}" />' for lat, lon in points)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="maxyaport.com Strava export" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>{name}</name>
    <time>{time}</time>
  </metadata>
  <trk>
    <name>{name}</name>
    <type>{activity_type}</type>
    <trkseg>
{track}
    </trkseg>
  </trk>
</gpx>
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Strava summary polylines as GPX files.")
    parser.add_argument(
        "--public",
        action="store_true",
        help="Write GPX files to public/data/strava-activities instead of the ignored private .strava-work folder.",
    )
    args = parser.parse_args()

    if not ACTIVITIES.exists():
        raise SystemExit(f"Missing {ACTIVITIES}. Run scripts/fetch-strava-activities.py first.")

    out_dir = PUBLIC_OUT if args.public else PRIVATE_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    activities = json.loads(ACTIVITIES.read_text())
    index = []
    exported = 0

    for activity in activities:
        polyline = (activity.get("map") or {}).get("summary_polyline")
        if not polyline:
            continue
        try:
            points = decode_polyline(polyline)
        except (IndexError, TypeError, ValueError):
            continue
        if len(points) < 2:
            continue

        start = str(activity.get("start_date_local") or activity.get("start_date") or "")[:10]
        activity_id = str(activity.get("id") or exported)
        name = str(activity.get("name") or "activity")
        filename = f"{start}-{slugify(activity.get('type') or 'activity')}-{activity_id}-{slugify(name)[:54]}.gpx"
        path = out_dir / filename
        path.write_text(gpx_for_activity(activity, points))
        exported += 1

        index.append(
            {
                "id": activity.get("id"),
                "name": activity.get("name"),
                "type": activity.get("type"),
                "startDate": activity.get("start_date_local") or activity.get("start_date"),
                "distanceMeters": activity.get("distance"),
                "movingTimeSeconds": activity.get("moving_time"),
                "summaryPolylinePoints": len(points),
                "gpxPath": f"/data/strava-activities/{filename}" if args.public else str(path),
            }
        )

    (out_dir / "index.json").write_text(json.dumps(index, indent=2))
    print(f"Wrote {exported} GPX files to {out_dir}")
    print(f"Wrote {out_dir / 'index.json'}")
    if not args.public:
        print("Private export only. Use --public for selected routes you intentionally want deployed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
