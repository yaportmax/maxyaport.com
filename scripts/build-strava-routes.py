#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / ".strava-work/activities.json"
OUT = ROOT / "public/data/strava-routes.geojson"
TRAVEL_DATA = ROOT / "src/data/travel-map.json"
RACE_ROUTES = ROOT / "public/data/race-routes.geojson"

FOOT_ACTIVITY_TERMS = ("run", "walk", "hike", "foot", "snowshoe")
BIKE_ACTIVITY_TERMS = (
    "ride",
    "bike",
    "cycling",
    "ski",
    "snowboard",
    "skate",
    "surf",
    "wheelchair",
    "handcycle",
)
SWIM_ACTIVITY_TERMS = ("swim",)
RACE_NAME_TERMS = (
    "70.3",
    "ironman",
    "triathlon",
    "marathon",
    "skyrace",
    "50k",
    "100k",
    "race",
)
MONTH_LOOKUP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
DAY_MS = 24 * 60 * 60 * 1000


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


def activity_group(activity_type: str, sport_type: str = "") -> str:
    normalized = f"{activity_type or ''} {sport_type or ''}".lower()
    if any(term in normalized for term in SWIM_ACTIVITY_TERMS):
        return "Swim"
    if any(term in normalized for term in FOOT_ACTIVITY_TERMS):
        return "Run"
    if any(term in normalized for term in BIKE_ACTIVITY_TERMS):
        return "Ride"
    return "Other"


def race_activity_ids() -> set[str]:
    if not TRAVEL_DATA.exists():
        return set()
    data = json.loads(TRAVEL_DATA.read_text())
    ids: set[str] = set()
    for race in data.get("races", []):
        ids.update(str(activity_id) for activity_id in race.get("stravaActivityIds", []))
    return ids


def parse_date_ms(value: object) -> int:
    normalized = str(value or "").strip()
    if not normalized:
        return 0

    iso_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", normalized)
    if iso_match:
        year, month, day = iso_match.groups()
        from datetime import datetime, timezone

        return round(datetime(int(year), int(month), int(day), tzinfo=timezone.utc).timestamp() * 1000)

    exact_match = re.match(r"^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$", normalized)
    if exact_match:
        month, day, year = exact_match.groups()
        month_index = MONTH_LOOKUP.get(month[:3].lower(), 1)
        from datetime import datetime, timezone

        return round(datetime(int(year), month_index, int(day), tzinfo=timezone.utc).timestamp() * 1000)

    return 0


def race_leg_signatures() -> list[dict]:
    if not TRAVEL_DATA.exists() or not RACE_ROUTES.exists():
        return []

    data = json.loads(TRAVEL_DATA.read_text())
    race_dates = {
        str(race.get("slug") or ""): parse_date_ms(race.get("date"))
        for race in data.get("races", [])
    }
    race_titles = {
        str(race.get("slug") or ""): str(race.get("title") or "")
        for race in data.get("races", [])
    }
    routes = json.loads(RACE_ROUTES.read_text())
    signatures: list[dict] = []

    for feature in routes.get("features", []):
        properties = feature.get("properties") or {}
        slug = str(properties.get("raceSlug") or "")
        distance = float(properties.get("distanceMeters") or 0)
        race_time = race_dates.get(slug, 0)
        if not slug or not race_time or distance <= 0:
            continue
        signatures.append(
            {
                "slug": slug,
                "title": race_titles.get(slug, ""),
                "time": race_time,
                "group": activity_group(
                    str(properties.get("sportType") or properties.get("activityGroup") or ""),
                    str(properties.get("activityGroup") or ""),
                ),
                "distanceMeters": distance,
            }
        )

    return signatures


def distance_tolerance(distance_meters: float) -> float:
    if distance_meters >= 10000:
        return max(350.0, distance_meters * 0.025)
    if distance_meters >= 1000:
        return max(120.0, distance_meters * 0.08)
    return max(80.0, distance_meters * 0.25)


def raceish_name(activity_name: str, race_title: str) -> bool:
    name = activity_name.lower()
    if any(term in name for term in RACE_NAME_TERMS):
        return True

    title_terms = {
        term
        for term in re.split(r"[^a-z0-9.]+", race_title.lower())
        if len(term) >= 4 and term not in {"from", "with", "championship"}
    }
    return bool(title_terms and sum(1 for term in title_terms if term in name) >= 2)


def is_probable_duplicate_race_leg(activity: dict, race_segments: list[dict]) -> bool:
    activity_time = parse_date_ms(activity.get("start_date_local") or activity.get("start_date"))
    activity_distance = float(activity.get("distance") or 0)
    if not activity_time or activity_distance <= 0:
        return False

    group = activity_group(str(activity.get("type") or ""), str(activity.get("sport_type") or ""))
    name = str(activity.get("name") or "")

    for segment in race_segments:
        if group != segment["group"]:
            continue
        time_delta = abs(activity_time - segment["time"])
        name_matches_race = raceish_name(name, segment["title"])
        if time_delta > 2 * DAY_MS:
            continue
        if time_delta > 0.75 * DAY_MS and not name_matches_race:
            continue

        segment_distance = float(segment["distanceMeters"])
        distance_delta = abs(activity_distance - segment_distance)
        if distance_delta > distance_tolerance(segment_distance):
            continue

        if name_matches_race or distance_delta <= max(120.0, segment_distance * 0.004):
            return True

    return False


def is_virtual_or_zwift(activity: dict) -> bool:
    name = str(activity.get("name") or "").lower()
    activity_type = str(activity.get("type") or "").lower()
    sport_type = str(activity.get("sport_type") or "").lower()
    return "zwift" in name or "virtual" in activity_type or "virtual" in sport_type


def main() -> None:
    parser = argparse.ArgumentParser(description="Build public Strava route LineStrings.")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--max-points", type=int, default=220)
    args = parser.parse_args()

    if not IN.exists():
        raise SystemExit(f"Missing {IN}. Run fetch-strava-activities.py first.")
    if args.max_points < 2:
        raise SystemExit("--max-points must be at least 2.")

    activities = json.loads(IN.read_text())
    excluded_race_ids = race_activity_ids()
    duplicate_race_legs = race_leg_signatures()
    features = []
    skipped_race_activities = 0
    skipped_duplicate_race_legs = 0
    skipped_virtual_activities = 0

    for activity in activities:
        activity_id = str(activity.get("id") or "")
        if activity_id in excluded_race_ids:
            skipped_race_activities += 1
            continue
        if is_probable_duplicate_race_leg(activity, duplicate_race_legs):
            skipped_duplicate_race_legs += 1
            continue
        if is_virtual_or_zwift(activity):
            skipped_virtual_activities += 1
            continue

        activity_type = activity.get("type") or "Activity"
        sport_type = activity.get("sport_type") or activity_type

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
                    "sportType": sport_type,
                    "activityGroup": activity_group(activity_type, sport_type),
                    "startDate": activity.get("start_date_local") or activity.get("start_date"),
                    "distanceMeters": round(float(activity.get("distance") or 0), 1),
                    "movingTimeSeconds": round(float(activity.get("moving_time") or 0), 1),
                    "elapsedTimeSeconds": round(float(activity.get("elapsed_time") or 0), 1),
                },
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")))
    print(f"Wrote {args.out}")
    print(f"Activities read: {len(activities)}")
    print(f"Routes written: {len(features)}")
    print(f"Race activities skipped: {skipped_race_activities}")
    print(f"Probable duplicate race legs skipped: {skipped_duplicate_race_legs}")
    print(f"Zwift/virtual activities skipped: {skipped_virtual_activities}")


if __name__ == "__main__":
    main()
