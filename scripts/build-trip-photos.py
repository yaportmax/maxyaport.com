#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TRAVEL_DATA = ROOT / "src/data/travel-map.json"
TRIP_ROUTES = ROOT / "public/data/trip-routes.geojson"
STRAVA_ROUTES = ROOT / "public/data/strava-routes.geojson"
PHOTOS_LIBRARY = Path.home() / "Pictures/Photos Library.photoslibrary"
PHOTOS_DB = PHOTOS_LIBRARY / "database/Photos.sqlite"
DERIVATIVES = PHOTOS_LIBRARY / "resources/derivatives"
OUT_DIR = ROOT / "public/data/trip-photos"
MANIFEST = OUT_DIR / "manifest.json"
APPLE_EPOCH_OFFSET = 978307200
DEFAULT_MAX_PER_TRIP = 5
DEFAULT_MAX_PER_ACTIVITY = 3

MONTHS = {
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


@dataclass
class PhotoCandidate:
    uuid: str
    original_name: str
    captured_at: str
    lat: float
    lon: float
    width: int
    height: int
    favorite: bool
    score: float
    distance_km: float
    progress: float
    source: Path


def parse_month_date(label: str) -> tuple[datetime, datetime]:
    normalized = " ".join(str(label or "").replace(",", "").split())
    match = re.search(r"\b([A-Za-z]{3,9})\s+(\d{4})\b", normalized)
    if not match:
        raise ValueError(f"Expected a month/year trip date, got {label!r}")
    month_name, year_text = match.groups()
    month = MONTHS[month_name[:3].lower()]
    year = int(year_text)
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if month == 12 else datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


def parse_iso_date(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).astimezone(timezone.utc)
    except ValueError:
        return None


def apple_timestamp(value: datetime) -> float:
    return value.timestamp() - APPLE_EPOCH_OFFSET


def finite_coordinate(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
        and -180 <= value[0] <= 180
        and -90 <= value[1] <= 90
    )


def valid_lat_lon(lat: Any, lon: Any) -> bool:
    return (
        isinstance(lat, (int, float))
        and isinstance(lon, (int, float))
        and -90 <= lat <= 90
        and -180 <= lon <= 180
        and not (lat == -180 or lon == -180)
        and not (lat == 0 and lon == 0)
    )


def haversine(first: list[float], second: list[float]) -> float:
    radius_km = 6371.0
    lon1, lat1 = math.radians(first[0]), math.radians(first[1])
    lon2, lat2 = math.radians(second[0]), math.radians(second[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def path_distance(coordinates: list[list[float]]) -> float:
    return sum(haversine(coordinates[index - 1], coordinates[index]) for index in range(1, len(coordinates)))


def nearest_route_progress(point: list[float], coordinates: list[list[float]]) -> tuple[float, float]:
    if not coordinates:
        return (0.0, float("inf"))
    if len(coordinates) == 1:
        return (0.0, haversine(point, coordinates[0]))

    total = max(path_distance(coordinates), 0.001)
    cursor = 0.0
    best_distance = float("inf")
    best_progress = 0.0

    for index in range(1, len(coordinates)):
        start = coordinates[index - 1]
        end = coordinates[index]
        segment_distance = haversine(start, end)
        # Good enough for ranking photos: use a local equirectangular projection per segment.
        mean_lat = math.radians((start[1] + end[1]) / 2)
        x1 = start[0] * math.cos(mean_lat)
        y1 = start[1]
        x2 = end[0] * math.cos(mean_lat)
        y2 = end[1]
        px = point[0] * math.cos(mean_lat)
        py = point[1]
        dx = x2 - x1
        dy = y2 - y1
        denom = dx * dx + dy * dy
        t = 0.0 if denom <= 0 else min(1.0, max(0.0, ((px - x1) * dx + (py - y1) * dy) / denom))
        projected = [start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t]
        distance = haversine(point, projected)
        if distance < best_distance:
            best_distance = distance
            best_progress = min(1.0, max(0.0, (cursor + segment_distance * t) / total))
        cursor += segment_distance

    return best_progress, best_distance


def route_coordinates_by_slug() -> dict[str, list[list[float]]]:
    coordinates_by_slug: dict[str, list[list[float]]] = {}
    if not TRIP_ROUTES.exists():
        return coordinates_by_slug
    data = json.loads(TRIP_ROUTES.read_text())
    for feature in sorted(data.get("features", []), key=lambda item: int(item.get("properties", {}).get("segmentIndex") or 0)):
        slug = feature.get("properties", {}).get("slug")
        coordinates = [coord for coord in feature.get("geometry", {}).get("coordinates", []) if finite_coordinate(coord)]
        if not slug or not coordinates:
            continue
        target = coordinates_by_slug.setdefault(slug, [])
        if target and target[-1] == coordinates[0]:
            target.extend(coordinates[1:])
        else:
            target.extend(coordinates)
    return coordinates_by_slug


def trip_route_coordinates(trip: dict[str, Any], route_lookup: dict[str, list[list[float]]]) -> list[list[float]]:
    routed = route_lookup.get(trip.get("slug", ""))
    if routed:
        return routed
    nodes = trip.get("routeNodes") or []
    return [
        [float(node["lon"]), float(node["lat"])]
        for node in nodes
        if valid_lat_lon(node.get("lat"), node.get("lon"))
    ]


def derivative_for_uuid(uuid: str) -> Path | None:
    if not uuid:
        return None
    bucket = uuid[0].upper()
    candidates = sorted((DERIVATIVES / bucket).glob(f"{uuid}_1_*_*.jpeg"))
    if candidates:
        preferred = [path for path in candidates if "_1_105_" in path.name]
        return preferred[0] if preferred else candidates[0]
    master_candidates = sorted((DERIVATIVES / "masters" / bucket).glob(f"{uuid}_*.jpeg"))
    return master_candidates[0] if master_candidates else None


def trip_bounds(coordinates: list[list[float]]) -> tuple[float, float, float, float]:
    lons = [coordinate[0] for coordinate in coordinates]
    lats = [coordinate[1] for coordinate in coordinates]
    return min(lats), max(lats), min(lons), max(lons)


def coordinate_in_trip_area(lat: float, lon: float, coordinates: list[list[float]]) -> bool:
    if not coordinates:
        return True
    min_lat, max_lat, min_lon, max_lon = trip_bounds(coordinates)
    span_lat = max_lat - min_lat
    span_lon = max_lon - min_lon
    padding = max(0.35, min(2.0, max(span_lat, span_lon) * 0.08))
    return min_lat - padding <= lat <= max_lat + padding and min_lon - padding <= lon <= max_lon + padding


def photos_for_month(conn: sqlite3.Connection, start: datetime, end: datetime) -> list[sqlite3.Row]:
    return photos_for_window(conn, start, end)


def photos_for_window(conn: sqlite3.Connection, start: datetime, end: datetime) -> list[sqlite3.Row]:
    return conn.execute(
        """
        select
          a.ZUUID,
          coalesce(aa.ZORIGINALFILENAME, a.ZFILENAME) as original_name,
          datetime(a.ZDATECREATED + 978307200, 'unixepoch') as captured_at,
          a.ZLATITUDE,
          a.ZLONGITUDE,
          a.ZWIDTH,
          a.ZHEIGHT,
          coalesce(a.ZOVERALLAESTHETICSCORE, 0) as aesthetic,
          coalesce(a.ZCURATIONSCORE, 0) as curation,
          coalesce(a.ZPROMOTIONSCORE, 0) as promotion,
          a.ZFAVORITE
        from ZASSET a
        left join ZADDITIONALASSETATTRIBUTES aa on aa.ZASSET = a.Z_PK
        where a.ZTRASHEDSTATE = 0
          and a.ZHIDDEN = 0
          and a.ZKIND = 0
          and coalesce(a.ZISDETECTEDSCREENSHOT, 0) = 0
          and a.ZDATECREATED >= ?
          and a.ZDATECREATED < ?
          and a.ZLATITUDE is not null
          and a.ZLONGITUDE is not null
        """,
        (apple_timestamp(start), apple_timestamp(end)),
    ).fetchall()


def candidate_for_trip(row: sqlite3.Row, coordinates: list[list[float]]) -> PhotoCandidate | None:
    lat = row["ZLATITUDE"]
    lon = row["ZLONGITUDE"]
    if not valid_lat_lon(lat, lon):
        return None
    if not coordinate_in_trip_area(float(lat), float(lon), coordinates):
        return None
    progress, distance_km = nearest_route_progress([float(lon), float(lat)], coordinates)
    source = derivative_for_uuid(row["ZUUID"])
    if not source:
        return None
    score = (
        float(row["aesthetic"] or 0) * 4.0
        + float(row["curation"] or 0) * 2.0
        + float(row["promotion"] or 0)
        + (0.7 if row["ZFAVORITE"] else 0.0)
        + max(0.0, 1.4 - min(distance_km, 70.0) / 50.0)
    )
    return PhotoCandidate(
        uuid=row["ZUUID"],
        original_name=row["original_name"] or row["ZUUID"],
        captured_at=row["captured_at"],
        lat=float(lat),
        lon=float(lon),
        width=int(row["ZWIDTH"] or 0),
        height=int(row["ZHEIGHT"] or 0),
        favorite=bool(row["ZFAVORITE"]),
        score=score,
        distance_km=distance_km,
        progress=progress,
        source=source,
    )


def candidate_for_activity(row: sqlite3.Row, coordinates: list[list[float]], max_distance_km: float) -> PhotoCandidate | None:
    lat = row["ZLATITUDE"]
    lon = row["ZLONGITUDE"]
    if not valid_lat_lon(lat, lon):
        return None
    progress, distance_km = nearest_route_progress([float(lon), float(lat)], coordinates)
    if distance_km > max_distance_km:
        return None
    source = derivative_for_uuid(row["ZUUID"])
    if not source:
        return None
    score = (
        float(row["aesthetic"] or 0) * 4.0
        + float(row["curation"] or 0) * 2.0
        + float(row["promotion"] or 0)
        + (0.7 if row["ZFAVORITE"] else 0.0)
        + max(0.0, 2.0 - distance_km / max(0.5, max_distance_km))
    )
    return PhotoCandidate(
        uuid=row["ZUUID"],
        original_name=row["original_name"] or row["ZUUID"],
        captured_at=row["captured_at"],
        lat=float(lat),
        lon=float(lon),
        width=int(row["ZWIDTH"] or 0),
        height=int(row["ZHEIGHT"] or 0),
        favorite=bool(row["ZFAVORITE"]),
        score=score,
        distance_km=distance_km,
        progress=progress,
        source=source,
    )


def safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")[:80] or "photo"


def write_public_photo(candidate: PhotoCandidate, folder: str, rank: int, max_size: int) -> tuple[str, int, int]:
    destination_dir = OUT_DIR / folder
    destination_dir.mkdir(parents=True, exist_ok=True)
    name = f"{rank:02d}-{candidate.uuid[:8]}-{safe_filename(candidate.original_name)}.jpg"
    destination = destination_dir / name

    sips = shutil.which("sips")
    if sips:
        subprocess.run(
            [sips, "-s", "format", "jpeg", "-Z", str(max_size), str(candidate.source), "--out", str(destination)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        shutil.copy2(candidate.source, destination)

    return f"/data/trip-photos/{folder}/{name}", candidate.width, candidate.height


def select_trip_photos(
    conn: sqlite3.Connection,
    trip: dict[str, Any],
    route_lookup: dict[str, list[list[float]]],
    max_per_trip: int,
    max_size: int,
) -> list[dict[str, Any]]:
    coordinates = trip_route_coordinates(trip, route_lookup)
    if len(coordinates) < 1:
        return []
    try:
        start, end = parse_month_date(str(trip.get("date") or ""))
    except ValueError:
        return []

    candidates: list[PhotoCandidate] = []
    seen_locations: list[list[float]] = []
    for row in photos_for_month(conn, start, end):
        candidate = candidate_for_trip(row, coordinates)
        if not candidate:
            continue
        if any(haversine([candidate.lon, candidate.lat], location) < 0.08 for location in seen_locations):
            continue
        candidates.append(candidate)
        seen_locations.append([candidate.lon, candidate.lat])

    candidates.sort(key=lambda item: (item.score, -item.distance_km), reverse=True)
    chosen = sorted(candidates[:max_per_trip], key=lambda item: item.progress)

    photos = []
    for rank, candidate in enumerate(chosen, start=1):
        src, width, height = write_public_photo(candidate, trip["slug"], rank, max_size)
        photos.append(
            {
                "src": src,
                "lat": round(candidate.lat, 6),
                "lon": round(candidate.lon, 6),
                "progress": round(candidate.progress, 4),
                "capturedAt": candidate.captured_at,
                "score": round(candidate.score, 3),
                "distanceKm": round(candidate.distance_km, 2),
                "width": width,
                "height": height,
            }
        )
    return photos


def load_strava_features() -> list[dict[str, Any]]:
    if not STRAVA_ROUTES.exists():
        return []
    data = json.loads(STRAVA_ROUTES.read_text())
    return [feature for feature in data.get("features", []) if feature.get("properties", {}).get("id")]


def activity_photo_distance_threshold(feature: dict[str, Any]) -> float:
    properties = feature.get("properties", {})
    group = str(properties.get("activityGroup") or properties.get("type") or "").lower()
    distance_km = float(properties.get("distanceMeters") or 0) / 1000
    if "run" in group or "hike" in group or "walk" in group:
        return 1.8 if distance_km < 25 else 3.0
    if "ride" in group or "bike" in group:
        return 7.5 if distance_km < 100 else 12.0
    return 5.0


def should_try_activity_photos(feature: dict[str, Any]) -> bool:
    properties = feature.get("properties", {})
    distance_km = float(properties.get("distanceMeters") or 0) / 1000
    group = str(properties.get("activityGroup") or properties.get("type") or "").lower()
    # Keep the public export focused on activities that can carry a story.
    if "run" in group or "hike" in group or "walk" in group:
        return distance_km >= 25.5
    if "ride" in group or "bike" in group:
        return distance_km >= 96.5
    return distance_km >= 25


def select_activity_photos(
    conn: sqlite3.Connection,
    feature: dict[str, Any],
    max_per_activity: int,
    max_size: int,
) -> list[dict[str, Any]]:
    properties = feature.get("properties", {})
    activity_id = str(properties.get("id") or "")
    coordinates = [coord for coord in feature.get("geometry", {}).get("coordinates", []) if finite_coordinate(coord)]
    start = parse_iso_date(str(properties.get("startDate") or ""))
    if not activity_id or len(coordinates) < 2 or not start or not should_try_activity_photos(feature):
        return []

    window_start = datetime.fromtimestamp(start.timestamp() - 10 * 60 * 60, tz=timezone.utc)
    window_end = datetime.fromtimestamp(start.timestamp() + 30 * 60 * 60, tz=timezone.utc)
    max_distance_km = activity_photo_distance_threshold(feature)
    candidates: list[PhotoCandidate] = []
    seen_locations: list[list[float]] = []

    for row in photos_for_window(conn, window_start, window_end):
        candidate = candidate_for_activity(row, coordinates, max_distance_km)
        if not candidate:
            continue
        if any(haversine([candidate.lon, candidate.lat], location) < 0.05 for location in seen_locations):
            continue
        candidates.append(candidate)
        seen_locations.append([candidate.lon, candidate.lat])

    candidates.sort(key=lambda item: (item.score, -item.distance_km), reverse=True)
    chosen = sorted(candidates[:max_per_activity], key=lambda item: item.progress)
    photos = []
    for rank, candidate in enumerate(chosen, start=1):
        src, width, height = write_public_photo(candidate, f"strava/{activity_id}", rank, max_size)
        photos.append(
            {
                "src": src,
                "lat": round(candidate.lat, 6),
                "lon": round(candidate.lon, 6),
                "progress": round(candidate.progress, 4),
                "capturedAt": candidate.captured_at,
                "score": round(candidate.score, 3),
                "distanceKm": round(candidate.distance_km, 2),
                "width": width,
                "height": height,
            }
        )
    return photos


def main() -> None:
    parser = argparse.ArgumentParser(description="Select geotagged Photos.app images for travel-map playback.")
    parser.add_argument("--max-per-trip", type=int, default=DEFAULT_MAX_PER_TRIP)
    parser.add_argument("--max-per-activity", type=int, default=DEFAULT_MAX_PER_ACTIVITY)
    parser.add_argument("--max-size", type=int, default=1200)
    args = parser.parse_args()

    if args.max_per_trip < 1:
        raise SystemExit("--max-per-trip must be at least 1.")
    if not PHOTOS_DB.exists():
        raise SystemExit(f"Missing Photos database: {PHOTOS_DB}")

    travel = json.loads(TRAVEL_DATA.read_text())
    trips = [trip for trip in travel.get("trips", []) if trip.get("slug")]
    route_lookup = route_coordinates_by_slug()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(f"file:{PHOTOS_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    manifest: dict[str, Any] = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "Apple Photos local derivative metadata",
        "maxPerTrip": args.max_per_trip,
        "maxPerActivity": args.max_per_activity,
        "trips": {},
        "strava": {},
    }

    total = 0
    for trip in trips:
        photos = select_trip_photos(conn, trip, route_lookup, args.max_per_trip, args.max_size)
        if photos:
            manifest["trips"][trip["slug"]] = photos
            total += len(photos)

    activity_total = 0
    for feature in load_strava_features():
        photos = select_activity_photos(conn, feature, args.max_per_activity, args.max_size)
        if photos:
            activity_id = str(feature.get("properties", {}).get("id") or "")
            manifest["strava"][activity_id] = photos
            activity_total += len(photos)

    MANIFEST.write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {MANIFEST}")
    print(f"Trips with photos: {len(manifest['trips'])} / {len(trips)}")
    print(f"Photos selected: {total}")
    print(f"Strava activities with photos: {len(manifest['strava'])}")
    print(f"Strava photos selected: {activity_total}")


if __name__ == "__main__":
    main()
