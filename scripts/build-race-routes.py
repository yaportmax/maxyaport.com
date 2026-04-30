#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "src/data/travel-map.json"
STRAVA_GPX_DIR = ROOT / ".strava-work/gpx"
PUBLIC_GPX_DIR = ROOT / "public/data/race-activities"
RACE_ROUTES_PATH = ROOT / "public/data/race-routes.geojson"

RACE_ACTIVITY_IDS: dict[str, list[int]] = {
    "2025-ironman-70-3-santa-cruz-relay-santa-cruz-ca-relay-bib-4073-t-m-men": [
        15733788504,
    ],
    "2025-tamalpa-headlands-50k-muir-beach-ca-50k": [15483221463],
    "2025-broken-arrow-skyrace-olympic-valley-ca-23k": [14884393748],
    "2025-ironman-70-3-st-george-st-george-ut-70-3": [
        14439034441,
        14439034437,
        14439034476,
        14439034430,
        14439034498,
    ],
    "2024-ironman-70-3-world-championship-taupo-new-zealand-70-3": [
        13123181635,
        13123181653,
        13123181735,
    ],
    "2024-golden-gate-trail-classic-san-francisco-ca-50k": [12967767052],
    "2024-ironman-70-3-santa-cruz-santa-cruz-ca-70-3": [
        12362277662,
        12362277606,
        12362264554,
        12362277639,
        12362277778,
    ],
    "2024-hood-to-coast-oregon-relay-run-for-days-mixed-open": [
        12224508183,
        12226486820,
        12230813715,
    ],
    "2024-twilight-5000-san-francisco-ca-5k": [11915847751],
    "2024-broken-arrow-skyrace-olympic-valley-ca-18k": [11707457039],
    "2024-escape-from-alcatraz-triathlon-san-francisco-ca-triathlon": [
        11614861238,
        11614861199,
        11614861296,
        11614861262,
        11614861381,
    ],
    "2024-ironman-70-3-morro-bay-morro-bay-ca-70-3": [
        11451209964,
        11451210000,
        11451210039,
    ],
    "2024-napa-valley-marathon-napa-ca-marathon": [10885303193],
    "2023-santa-cruz-triathlon-santa-cruz-ca-olympic": [
        9913988164,
        9913988024,
        9913988113,
    ],
}

STATIC_RACE_GPX: dict[str, list[str]] = {
    "2026-canyons-100k-auburn-ca-100k": ["/routes/canyons-2026.gpx"],
}


def gpx_coordinates(path: Path) -> list[list[float]]:
    tree = ET.parse(path)
    root = tree.getroot()
    coordinates: list[list[float]] = []

    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag not in {"trkpt", "rtept"}:
            continue
        try:
            lat = float(element.attrib["lat"])
            lon = float(element.attrib["lon"])
        except (KeyError, ValueError):
            continue
        coordinates.append([round(lon, 6), round(lat, 6)])

    return coordinates


def find_activity_gpx(activity_id: int) -> Path:
    matches = sorted(STRAVA_GPX_DIR.glob(f"*{activity_id}*.gpx"))
    if not matches:
        raise FileNotFoundError(f"Missing Strava GPX for activity {activity_id}")
    return matches[0]


def activity_lookup() -> dict[int, dict[str, Any]]:
    path = ROOT / ".strava-work/activities.json"
    if not path.exists():
        return {}
    activities = json.loads(path.read_text())
    return {int(activity["id"]): activity for activity in activities if activity.get("id")}


def main() -> None:
    data = json.loads(DATA_PATH.read_text())
    activities = activity_lookup()
    route_features: list[dict[str, Any]] = []

    if PUBLIC_GPX_DIR.exists():
        shutil.rmtree(PUBLIC_GPX_DIR)
    PUBLIC_GPX_DIR.mkdir(parents=True, exist_ok=True)

    for race in data.get("races", []):
        slug = race.get("slug")
        race["stravaActivityIds"] = RACE_ACTIVITY_IDS.get(slug, [])
        race["gpxPaths"] = []
        race["raceRouteSource"] = None

        public_paths: list[str] = []
        source_paths: list[Path] = []

        for activity_id in race["stravaActivityIds"]:
            source_path = find_activity_gpx(activity_id)
            public_path = PUBLIC_GPX_DIR / source_path.name
            shutil.copyfile(source_path, public_path)
            public_paths.append(f"/data/race-activities/{public_path.name}")
            source_paths.append(public_path)

        for static_path in STATIC_RACE_GPX.get(slug, []):
            public_paths.append(static_path)
            source_paths.append(ROOT / "public" / static_path.lstrip("/"))

        if public_paths:
            race["gpxPaths"] = public_paths
            race["raceRouteSource"] = "strava" if race["stravaActivityIds"] else "static-gpx"

        for segment_index, (public_path, source_path) in enumerate(zip(public_paths, source_paths)):
            coordinates = gpx_coordinates(source_path)
            if len(coordinates) < 2:
                continue

            activity_id = None
            sport_type = None
            if public_path.startswith("/data/race-activities/"):
                activity_id = race["stravaActivityIds"][segment_index]
                sport_type = activities.get(activity_id, {}).get("sport_type") or activities.get(activity_id, {}).get("type")

            route_features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "raceSlug": slug,
                        "raceTitle": race.get("title"),
                        "activityId": activity_id,
                        "sportType": sport_type,
                        "sourcePath": public_path,
                        "segmentIndex": segment_index,
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coordinates,
                    },
                }
            )

    RACE_ROUTES_PATH.write_text(
        json.dumps({"type": "FeatureCollection", "features": route_features}, indent=2) + "\n"
    )
    DATA_PATH.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Wrote {len(route_features)} race route segments")
    print(f"Copied {len(list(PUBLIC_GPX_DIR.glob('*.gpx')))} Strava GPX files")


if __name__ == "__main__":
    main()
