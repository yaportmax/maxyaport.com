#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "src/data/travel-map.json"
OUT_PATH = ROOT / "public/data/trip-routes.geojson"
ENV_PATHS = (ROOT / ".env.local", ROOT / ".env")
DEFAULT_MAX_POINTS = 240
GENERATED_SEGMENT_FIELDS = (
    "coordinates",
    "routeProvider",
    "routeProfile",
    "distanceMeters",
    "durationSeconds",
)


def dotenv_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for path in ENV_PATHS:
        if not path.exists():
            continue
        for raw_line in path.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key:
                values[key] = value
    return values


def mapbox_token(required: bool) -> str:
    env = dotenv_values()
    token = os.environ.get("MAPBOX_TOKEN") or os.environ.get("PUBLIC_MAPBOX_TOKEN")
    token = token or env.get("MAPBOX_TOKEN") or env.get("PUBLIC_MAPBOX_TOKEN")
    if required and not token:
        raise SystemExit("Missing MAPBOX_TOKEN or PUBLIC_MAPBOX_TOKEN.")
    return token or ""


def finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def valid_node(node: Any) -> bool:
    if not isinstance(node, dict):
        return False
    lat = finite_number(node.get("lat"))
    lon = finite_number(node.get("lon"))
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def valid_coordinates(value: Any) -> bool:
    if not isinstance(value, list) or len(value) < 2:
        return False
    for coord in value:
        if not isinstance(coord, list) or len(coord) < 2:
            return False
        lon = finite_number(coord[0])
        lat = finite_number(coord[1])
        if lon is None or lat is None or not (-180 <= lon <= 180 and -90 <= lat <= 90):
            return False
    return True


def sampled_coordinates(coordinates: list[list[float]], max_points: int) -> list[list[float]]:
    if len(coordinates) <= max_points:
        return coordinates

    sampled: list[list[float]] = []
    step = (len(coordinates) - 1) / (max_points - 1)
    last_index = -1
    for index in range(max_points):
        source_index = round(index * step)
        if source_index == last_index:
            continue
        sampled.append(coordinates[source_index])
        last_index = source_index
    if sampled[-1] != coordinates[-1]:
        sampled[-1] = coordinates[-1]
    return sampled


def rounded_coordinates(coordinates: list[list[float]], max_points: int) -> list[list[float]]:
    return [
        [round(float(lon), 5), round(float(lat), 5)]
        for lon, lat in sampled_coordinates(coordinates, max_points)
    ]


def to_radians(degrees: float) -> float:
    return degrees * math.pi / 180


def to_degrees(radians: float) -> float:
    return radians * 180 / math.pi


def great_circle_coordinates(start: list[float], end: list[float], steps: int = 80) -> list[list[float]]:
    lon1 = to_radians(start[0])
    lat1 = to_radians(start[1])
    lon2 = to_radians(end[0])
    lat2 = to_radians(end[1])
    delta = 2 * math.asin(
        math.sqrt(
            math.sin((lat2 - lat1) / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
        )
    )

    if delta == 0:
        return [start, end]

    coordinates: list[list[float]] = []
    for step in range(steps + 1):
        fraction = step / steps
        a = math.sin((1 - fraction) * delta) / math.sin(delta)
        b = math.sin(fraction * delta) / math.sin(delta)
        x = a * math.cos(lat1) * math.cos(lon1) + b * math.cos(lat2) * math.cos(lon2)
        y = a * math.cos(lat1) * math.sin(lon1) + b * math.cos(lat2) * math.sin(lon2)
        z = a * math.sin(lat1) + b * math.sin(lat2)
        lon = to_degrees(math.atan2(y, x))
        lat = to_degrees(math.atan2(z, math.sqrt(x * x + y * y)))

        if coordinates:
            previous_lon = coordinates[-1][0]
            while lon - previous_lon > 180:
                lon -= 360
            while lon - previous_lon < -180:
                lon += 360

        coordinates.append([round(lon, 5), round(lat, 5)])

    return coordinates


def fetch_route(
    *,
    token: str,
    profile: str,
    start: dict[str, Any],
    end: dict[str, Any],
    max_points: int,
) -> tuple[list[list[float]], float, float]:
    coordinates = f"{start['lon']},{start['lat']};{end['lon']},{end['lat']}"
    query = urllib.parse.urlencode(
        {
            "geometries": "geojson",
            "overview": "full",
            "alternatives": "false",
            "access_token": token,
        }
    )
    url = f"https://api.mapbox.com/directions/v5/{profile}/{coordinates}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "maxyaport-travel-map/1.0"})

    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    routes = payload.get("routes") or []
    if payload.get("code") != "Ok" or not routes:
        message = payload.get("message") or payload.get("code") or "no route returned"
        raise RuntimeError(str(message))

    route = routes[0]
    geometry = route.get("geometry") or {}
    raw_coordinates = geometry.get("coordinates") or []
    if not valid_coordinates(raw_coordinates):
        raise RuntimeError("route geometry was missing or invalid")

    return (
        rounded_coordinates(raw_coordinates, max_points),
        float(route.get("distance") or 0),
        float(route.get("duration") or 0),
    )


def segment_mode(trip: dict[str, Any], segment: dict[str, Any]) -> str:
    configured = segment.get("mode") or trip.get("travelMode") or "drive"
    return configured if configured in {"flight", "sail"} else "drive"


def ensure_segments(trip: dict[str, Any], leg_count: int) -> list[dict[str, Any]]:
    segments = trip.get("routeSegments")
    if not isinstance(segments, list):
        segments = []
    normalized = [segment if isinstance(segment, dict) else {} for segment in segments[:leg_count]]
    while len(normalized) < leg_count:
        normalized.append({"mode": trip.get("travelMode") or "drive"})
    trip["routeSegments"] = normalized
    return normalized


def leg_key(mode: str, profile: str, start: dict[str, Any], end: dict[str, Any]) -> str:
    return "|".join(
        [
            mode,
            profile,
            f"{float(start['lon']):.5f},{float(start['lat']):.5f}",
            f"{float(end['lon']):.5f},{float(end['lat']):.5f}",
        ]
    )


def feature_for_segment(
    *,
    trip: dict[str, Any],
    segment: dict[str, Any],
    index: int,
    mode: str,
    start: dict[str, Any],
    end: dict[str, Any],
    coordinates: list[list[float]],
    key: str,
    profile: str,
    distance: float = 0,
    duration: float = 0,
) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "slug": trip.get("slug", ""),
        "title": trip.get("title", ""),
        "mode": mode,
        "vehicle": segment.get("vehicle", ""),
        "segmentIndex": index,
        "startTitle": start.get("title", ""),
        "endTitle": end.get("title", ""),
        "routeKey": key,
    }
    if mode == "drive":
        properties["routeProvider"] = "mapbox-directions"
        properties["routeProfile"] = profile
    if distance:
        properties["distanceMeters"] = round(distance)
    if duration:
        properties["durationSeconds"] = round(duration)
    if mode == "sail":
        properties["routeProvider"] = "great-circle"
        properties["routeProfile"] = mode

    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "properties": properties,
    }


def load_cached_features() -> dict[str, dict[str, Any]]:
    if not OUT_PATH.exists():
        return {}
    try:
        data = json.loads(OUT_PATH.read_text())
    except json.JSONDecodeError:
        return {}

    cache: dict[str, dict[str, Any]] = {}
    for feature in data.get("features", []):
        properties = feature.get("properties") or {}
        key = properties.get("routeKey")
        coordinates = (feature.get("geometry") or {}).get("coordinates")
        if isinstance(key, str) and valid_coordinates(coordinates):
            cache[key] = feature
    return cache


def strip_generated_segment_fields(data: dict[str, Any]) -> int:
    removed = 0
    for trip in data.get("trips", []):
        for segment in trip.get("routeSegments", []):
            if not isinstance(segment, dict):
                continue
            for field in GENERATED_SEGMENT_FIELDS:
                if field in segment:
                    del segment[field]
                    removed += 1
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build public/data/trip-routes.geojson from configured travel route nodes and modes."
    )
    parser.add_argument("--refresh", action="store_true", help="Regenerate drive geometry instead of using cache.")
    parser.add_argument("--profile", default="mapbox/driving", help="Mapbox Directions profile for drive legs.")
    parser.add_argument("--max-points", type=int, default=DEFAULT_MAX_POINTS, help="Maximum coordinates stored per leg.")
    parser.add_argument("--sleep", type=float, default=0.15, help="Delay between Directions API requests.")
    parser.add_argument(
        "--strip-inline",
        action="store_true",
        help="Remove generated segment coordinate fields from src/data/travel-map.json after writing GeoJSON.",
    )
    args = parser.parse_args()

    if args.max_points < 2:
        raise SystemExit("--max-points must be at least 2.")

    data = json.loads(DATA_PATH.read_text())
    cache = load_cached_features()
    token = mapbox_token(required=args.refresh or not cache)
    features: list[dict[str, Any]] = []
    routed = 0
    cached = 0
    inline = 0
    generated_flights = 0
    generated_sails = 0
    failed = 0

    for trip in data.get("trips", []):
        nodes = [node for node in trip.get("routeNodes", []) if valid_node(node)]
        if len(nodes) < 2:
            continue

        segments = ensure_segments(trip, len(nodes) - 1)
        for index, segment in enumerate(segments):
            if segment.get("render") is False:
                continue
            mode = segment_mode(trip, segment)
            start = nodes[index]
            end = nodes[index + 1]
            key = leg_key(mode, args.profile, start, end)
            label = f"{trip.get('title', trip.get('slug'))}: {start.get('title', 'start')} -> {end.get('title', 'end')}"

            coordinates = segment.get("coordinates")
            if valid_coordinates(coordinates) and not args.refresh:
                features.append(
                    feature_for_segment(
                        trip=trip,
                        segment=segment,
                        index=index,
                        mode=mode,
                        start=start,
                        end=end,
                        coordinates=rounded_coordinates(coordinates, args.max_points),
                        key=key,
                        profile=args.profile,
                        distance=float(segment.get("distanceMeters") or 0),
                        duration=float(segment.get("durationSeconds") or 0),
                    )
                )
                inline += 1
                continue

            if mode in {"flight", "sail"}:
                features.append(
                    feature_for_segment(
                        trip=trip,
                        segment=segment,
                        index=index,
                        mode=mode,
                        start=start,
                        end=end,
                        coordinates=great_circle_coordinates([start["lon"], start["lat"]], [end["lon"], end["lat"]]),
                        key=key,
                        profile=args.profile,
                    )
                )
                if mode == "flight":
                    generated_flights += 1
                if mode == "sail":
                    generated_sails += 1
                continue

            distance = float(segment.get("distanceMeters") or 0)
            duration = float(segment.get("durationSeconds") or 0)

            cached_feature = cache.get(key)
            if cached_feature and not args.refresh:
                cached_properties = cached_feature.get("properties") or {}
                features.append(
                    feature_for_segment(
                        trip=trip,
                        segment=segment,
                        index=index,
                        mode=mode,
                        start=start,
                        end=end,
                        coordinates=rounded_coordinates(cached_feature["geometry"]["coordinates"], args.max_points),
                        key=key,
                        profile=args.profile,
                        distance=float(cached_properties.get("distanceMeters") or 0),
                        duration=float(cached_properties.get("durationSeconds") or 0),
                    )
                )
                cached += 1
                continue

            try:
                coordinates, distance, duration = fetch_route(
                    token=token,
                    profile=args.profile,
                    start=start,
                    end=end,
                    max_points=args.max_points,
                )
            except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
                failed += 1
                print(f"warning: {label}: {error}")
                features.append(
                    feature_for_segment(
                        trip=trip,
                        segment=segment,
                        index=index,
                        mode=mode,
                        start=start,
                        end=end,
                        coordinates=[[start["lon"], start["lat"]], [end["lon"], end["lat"]]],
                        key=key,
                        profile=args.profile,
                    )
                )
                continue

            features.append(
                feature_for_segment(
                    trip=trip,
                    segment=segment,
                    index=index,
                    mode=mode,
                    start=start,
                    end=end,
                    coordinates=coordinates,
                    key=key,
                    profile=args.profile,
                    distance=distance,
                    duration=duration,
                )
            )
            routed += 1
            print(f"routed: {label} ({len(coordinates)} points)")
            if args.sleep > 0:
                time.sleep(args.sleep)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({"type": "FeatureCollection", "features": features}, indent=2) + "\n")

    stripped = 0
    if args.strip_inline:
        stripped = strip_generated_segment_fields(data)
        DATA_PATH.write_text(json.dumps(data, indent=2) + "\n")

    print(
        "Wrote "
        f"{OUT_PATH} with {len(features)} segment(s): "
        f"{routed} routed, {cached} cached, {inline} inline, "
        f"{generated_flights} flight, {generated_sails} sail, {failed} failed."
    )
    if stripped:
        print(f"Removed {stripped} generated inline field(s) from {DATA_PATH}.")


if __name__ == "__main__":
    main()
