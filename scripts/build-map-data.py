#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHOTO_SCRIPT = ROOT / "scripts/build-photo-review.py"
OUT = ROOT / "src/data/travel-map.json"
PRESERVED_TRIP_FIELDS = ("lat", "lon", "travelMode", "routeNodes", "routeSegments")

RACE_COORDS = {
    "Canyons 100K": (39.118, -120.947),
    "IRONMAN 70.3 Santa Cruz Relay": (36.974, -122.03),
    "Tamalpa Headlands 50K": (37.862, -122.581),
    "Broken Arrow Skyrace|Olympic Valley, CA - 23K": (39.197, -120.235),
    "IRONMAN 70.3 St. George": (37.096, -113.568),
    "IRONMAN 70.3 World Championship": (-38.685, 176.07),
    "Golden Gate Trail Classic": (37.775, -122.419),
    "IRONMAN 70.3 Santa Cruz": (36.974, -122.03),
    "Hood to Coast": (45.515, -122.679),
    "Twilight 5000": (37.775, -122.419),
    "Broken Arrow Skyrace|Olympic Valley, CA - 18K": (39.197, -120.235),
    "Escape from Alcatraz Triathlon": (37.807, -122.426),
    "IRONMAN 70.3 Morro Bay": (35.365, -120.849),
    "Napa Valley Marathon": (38.502, -122.265),
    "Santa Cruz Triathlon": (36.974, -122.03),
}

RACE_DATES = {
    "Canyons 100K": "Apr 25 2026",
    "IRONMAN 70.3 Santa Cruz Relay": "Sep 7 2025",
    "Tamalpa Headlands 50K": "Aug 16 2025",
    "Broken Arrow Skyrace|Olympic Valley, CA - 23K": "Jun 22 2025",
    "IRONMAN 70.3 St. George": "May 10 2025",
    "IRONMAN 70.3 World Championship": "Dec 15 2024",
    "Golden Gate Trail Classic": "Nov 23 2024",
    "IRONMAN 70.3 Santa Cruz": "Sep 8 2024",
    "Hood to Coast": "Aug 23 2024",
    "Twilight 5000": "Jul 17 2024",
    "Broken Arrow Skyrace|Olympic Valley, CA - 18K": "Jun 21 2024",
    "Escape from Alcatraz Triathlon": "Jun 9 2024",
    "IRONMAN 70.3 Morro Bay": "May 19 2024",
    "Napa Valley Marathon": "Mar 3 2024",
    "Santa Cruz Triathlon": "Sep 24 2023",
}


def load_photo_script():
    spec = importlib.util.spec_from_file_location("photo_review", PHOTO_SCRIPT)
    if not spec or not spec.loader:
        raise RuntimeError("Could not load photo review script.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def center(boxes):
    min_lat, max_lat, min_lon, max_lon = boxes[0]
    return round((min_lat + max_lat) / 2, 5), round((min_lon + max_lon) / 2, 5)


def parse_races(source: str):
    block = re.search(r"const races = \[(.*?)\];", source, re.S)
    if not block:
        raise RuntimeError("Could not find races array.")
    races = []
    for item in re.finditer(r"\{\s*title:\s*\"([^\"]+)\",\s*href:\s*\"([^\"]+)\",\s*detail:\s*\"([^\"]+)\",\s*result:\s*\"([^\"]+)\"(?:,\s*rank:\s*\"([^\"]+)\")?", block.group(1), re.S):
        title, href, detail, result, rank = item.groups()
        coords = RACE_COORDS.get(f"{title}|{detail}") or RACE_COORDS.get(title)
        if not coords:
            continue
        lat, lon = coords
        date = RACE_DATES.get(f"{title}|{detail}") or RACE_DATES.get(title) or result[:4]
        slug = re.sub(r"[^a-z0-9]+", "-", f"{result[:4]} {title} {detail}".lower()).strip("-")
        races.append(
            {
                "type": "race",
                "slug": slug,
                "title": title,
                "detail": detail,
                "date": date,
                "result": result,
                "rank": rank or "",
                "href": href,
                "lat": lat,
                "lon": lon,
            }
        )
    return races


def main() -> None:
    photo = load_photo_script()
    existing_trips = {}
    if OUT.exists():
        try:
            existing = json.loads(OUT.read_text())
            existing_trips = {trip.get("slug"): trip for trip in existing.get("trips", []) if trip.get("slug")}
        except json.JSONDecodeError:
            existing_trips = {}

    trips = []
    for trip in photo.trips_from_component():
        boxes = photo.BOXES.get(trip.title)
        if not boxes:
            continue
        lat, lon = center(boxes)
        item = {
            "type": "trip",
            "slug": trip.slug,
            "title": trip.title,
            "detail": trip.detail,
            "date": trip.month,
            "lat": lat,
            "lon": lon,
        }
        previous = existing_trips.get(trip.slug, {})
        for field in PRESERVED_TRIP_FIELDS:
            if field in previous:
                item[field] = previous[field]
        trips.append(item)

    source = (ROOT / "src/components/HomeContent.astro").read_text()
    data = {"trips": trips, "races": parse_races(source)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Wrote {OUT}")
    print(f"Trips: {len(trips)}")
    print(f"Races: {len(data['races'])}")


if __name__ == "__main__":
    main()
