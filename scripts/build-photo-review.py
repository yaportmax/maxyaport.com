#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHOTOS_LIBRARY = Path.home() / "Pictures/Photos Library.photoslibrary"
DB = PHOTOS_LIBRARY / "database/Photos.sqlite"
DERIVATIVES = PHOTOS_LIBRARY / "resources/derivatives"
OUT = ROOT / "photo-review"

APPLE_EPOCH_OFFSET = 978307200
TOP_PER_TRIP = 24


@dataclass(frozen=True)
class Trip:
    title: str
    detail: str
    month: str

    @property
    def slug(self) -> str:
        base = f"{self.month} {self.title}".lower()
        base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
        return base


# Rough bounding boxes used only to separate trips that share a month.
# Values are (min_lat, max_lat, min_lon, max_lon).
BOXES: dict[str, list[tuple[float, float, float, float]]] = {
    "Truckee and Auburn": [(38.7, 39.5, -121.4, -120.0)],
    "Sedona": [(34.6, 35.1, -112.1, -111.5)],
    "Lake Almanor": [(40.0, 40.5, -121.5, -120.9)],
    "Tahoe": [(38.7, 39.5, -120.4, -119.7)],
    "Costa Mesa": [(33.5, 33.8, -118.1, -117.7)],
    "Maui": [(20.5, 21.2, -156.8, -155.9)],
    "Paso Robles and Los Osos": [(35.4, 35.8, -121.3, -120.5), (35.2, 35.4, -120.9, -120.7)],
    "Broomfield": [(39.8, 40.1, -105.2, -104.8)],
    "Eastern Sierra and Utah": [(36.2, 38.6, -119.0, -117.5), (37.0, 39.8, -113.7, -109.0)],
    "Arnold": [(38.1, 38.5, -120.5, -119.9)],
    "Bear Valley": [(38.3, 38.6, -120.2, -119.9)],
    "Santa Cruz": [(36.8, 37.1, -122.2, -121.8)],
    "Mammoth": [(37.4, 38.1, -119.3, -118.5)],
    "Yosemite": [(37.4, 38.2, -120.2, -119.1)],
    "Lake Como": [(45.7, 46.3, 8.8, 9.6)],
    "Kauai": [(21.8, 22.3, -159.9, -159.2)],
    "Santa Rosa": [(38.3, 38.7, -123.0, -122.4)],
    "Utah and Zion": [(36.0, 37.5, -115.5, -112.6)],
    "Humboldt and the Redwoods": [(40.3, 41.7, -124.5, -123.5)],
    "Death Valley": [(35.7, 37.2, -117.8, -116.2)],
    "Big Sur": [(35.8, 36.6, -122.2, -121.4)],
    "Scottsdale": [(33.3, 33.8, -112.2, -111.7)],
    "New Zealand": [(-47.4, -34.0, 166.0, 179.0)],
    "Mendocino": [(39.1, 39.6, -123.9, -123.4)],
    "Oregon": [(42.0, 46.4, -124.8, -121.0)],
    "Morro Bay": [(35.2, 35.5, -121.0, -120.7)],
    "Occidental": [(38.35, 38.55, -123.1, -122.8)],
    "Mexico City": [(19.0, 19.8, -99.5, -98.8)],
    "Joshua Tree": [(33.7, 34.3, -116.6, -115.4)],
    "Las Vegas": [(35.8, 36.4, -115.5, -114.9)],
    "San Luis Obispo": [(35.1, 35.4, -120.8, -120.4)],
    "San Luis Obispo and San Simeon": [(35.1, 35.8, -121.3, -120.4)],
    "Seattle": [(47.3, 47.9, -122.6, -121.2)],
    "Portland and Bend": [(44.0, 45.8, -123.2, -121.0)],
    "Orlando": [(28.2, 28.7, -81.6, -81.1)],
    "Sequoia and Kings Canyon": [(35.9, 37.2, -119.3, -118.3)],
    "Graduation Road Trip": [(32.0, 49.0, -124.8, -104.0)],
    "Reno": [(39.3, 39.8, -120.1, -119.5)],
    "Northern California and Oregon": [(39.0, 46.4, -124.8, -121.0)],
    "Mount Pinos": [(34.6, 34.9, -119.3, -118.9)],
    "Big Sur: Ventana Wilderness": [(35.8, 36.4, -121.9, -121.4)],
    "Big Sur: Pfeiffer Ridge": [(36.1, 36.4, -121.9, -121.6)],
    "Santa Barbara": [(34.3, 34.6, -120.0, -119.5)],
    "Croatia, Andorra, Amsterdam": [(42.0, 46.8, 13.0, 19.8), (42.3, 42.8, 1.3, 1.8), (52.2, 52.5, 4.7, 5.1)],
    "Pinnacles": [(36.4, 36.7, -121.4, -121.0)],
    "Arches and Canyonlands": [(38.3, 39.0, -110.3, -109.2)],
    "Washington to California Coast": [(37.0, 48.8, -124.9, -121.8)],
    "Eastern Sierra": [(36.2, 38.6, -119.0, -117.5)],
    "Lebec": [(34.7, 35.1, -119.2, -118.7)],
    "Lake Arrowhead": [(33.9, 34.4, -118.5, -117.0), (35.1, 35.4, -120.8, -120.4)],
    "San Diego": [(32.5, 33.1, -117.4, -116.8)],
    "Tuscany and Italy": [(43.6, 44.0, 11.0, 11.5), (42.5, 43.8, 10.5, 12.4), (41.7, 42.1, 12.3, 12.7), (45.2, 45.6, 12.1, 12.6)],
    "Portland and Mount Hood": [(45.3, 45.7, -122.9, -122.4), (45.2, 45.6, -122.1, -121.5)],
    "Israel": [(29.4, 33.4, 34.2, 35.9)],
    "Coachella": [(33.5, 33.9, -116.6, -115.9)],
    "South Lake Tahoe": [(38.7, 39.1, -120.2, -119.8)],
    "Boston and New York": [(42.2, 42.5, -71.3, -70.9), (40.5, 40.9, -74.2, -73.7)],
    "Alaska": [(58.8, 64.0, -151.5, -146.0)],
    "Iceland Ring Road": [(63.3, 66.7, -24.6, -13.2)],
    "Miami": [(25.6, 26.0, -80.4, -80.0)],
    "Death Valley": [(35.4, 38.4, -119.1, -116.2)],
    "Utah National Parks": [(37.0, 38.0, -113.3, -112.0)],
    "Barcelona and Madrid": [(41.2, 41.6, 1.9, 2.4), (40.2, 40.6, -3.9, -3.5)],
    "Humboldt, Oregon Dunes, and Crater Lake": [(39.0, 43.6, -124.5, -121.7)],
}


def month_bounds(label: str) -> tuple[float, float]:
    start = datetime.strptime(label, "%b %Y").replace(tzinfo=timezone.utc)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start.timestamp() - APPLE_EPOCH_OFFSET, end.timestamp() - APPLE_EPOCH_OFFSET


def trips_from_component() -> list[Trip]:
    source = (ROOT / "src/components/HomeContent.astro").read_text()
    block = re.search(r"const travel = \[(.*?)\];", source, re.S)
    if not block:
        raise RuntimeError("Could not find travel array.")
    trips: list[Trip] = []
    for item in re.finditer(r"\{\s*title:\s*\"([^\"]+)\",\s*detail:\s*\"([^\"]+)\",\s*date:\s*\"([^\"]+)\"", block.group(1), re.S):
        trips.append(Trip(*item.groups()))
    return trips


def derivative_for_uuid(uuid: str) -> Path | None:
    bucket = uuid[0].upper()
    candidates = sorted((DERIVATIVES / bucket).glob(f"{uuid}_1_*_*.jpeg"))
    if candidates:
        preferred = [path for path in candidates if "_1_105_" in path.name]
        return preferred[0] if preferred else candidates[0]
    master_candidates = sorted((DERIVATIVES / "masters" / bucket).glob(f"{uuid}_*.jpeg"))
    return master_candidates[0] if master_candidates else None


def in_box(lat: float, lon: float, boxes: list[tuple[float, float, float, float]]) -> bool:
    return any(min_lat <= lat <= max_lat and min_lon <= lon <= max_lon for min_lat, max_lat, min_lon, max_lon in boxes)


def copy_candidates(conn: sqlite3.Connection, trip: Trip, writer: csv.DictWriter[str]) -> int:
    start, end = month_bounds(trip.month)
    boxes = BOXES.get(trip.title, [])
    rows = conn.execute(
        """
        select
          a.ZUUID,
          coalesce(aa.ZORIGINALFILENAME, a.ZFILENAME) as original_name,
          datetime(a.ZDATECREATED + 978307200, 'unixepoch') as created_at,
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
        """,
        (start, end),
    ).fetchall()

    filtered = []
    for row in rows:
        lat = row["ZLATITUDE"]
        lon = row["ZLONGITUDE"]
        has_location = lat is not None and lon is not None and lat != -180 and lon != -180
        location_match = bool(boxes and has_location and in_box(lat, lon, boxes))
        if boxes and not location_match:
            continue
        score = (
            float(row["aesthetic"] or 0) * 4
            + float(row["curation"] or 0) * 2
            + float(row["promotion"] or 0)
            + (0.35 if row["ZFAVORITE"] else 0)
            + (0.15 if has_location else 0)
        )
        filtered.append((score, row))

    # If GPS boxes were too strict, fall back to the month so the folder is not empty.
    if len(filtered) < 6 and boxes:
        for row in rows:
            has_location = row["ZLATITUDE"] is not None and row["ZLATITUDE"] != -180
            score = float(row["aesthetic"] or 0) * 4 + float(row["curation"] or 0) * 2 + (0.15 if has_location else 0)
            filtered.append((score * 0.75, row))

    filtered.sort(key=lambda item: item[0], reverse=True)
    trip_dir = OUT / trip.slug
    trip_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for index, (score, row) in enumerate(filtered[:TOP_PER_TRIP], start=1):
        src = derivative_for_uuid(row["ZUUID"])
        if not src:
            continue
        ext = src.suffix.lower()
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", row["original_name"] or row["ZUUID"])
        dst = trip_dir / f"{index:02d}-{score:.2f}-{row['created_at'][:10]}-{safe_name}{ext}"
        shutil.copy2(src, dst)
        writer.writerow(
            {
                "trip": trip.title,
                "folder": trip.slug,
                "rank": index,
                "score": f"{score:.3f}",
                "created_at": row["created_at"],
                "latitude": row["ZLATITUDE"],
                "longitude": row["ZLONGITUDE"],
                "width": row["ZWIDTH"],
                "height": row["ZHEIGHT"],
                "favorite": row["ZFAVORITE"],
                "source": str(src),
                "review_file": str(dst),
            }
        )
        count += 1
    return count


def main() -> None:
    OUT.mkdir(exist_ok=True)
    trips = trips_from_component()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    metadata_path = OUT / "metadata.csv"
    with metadata_path.open("w", newline="") as handle:
        fieldnames = [
            "trip",
            "folder",
            "rank",
            "score",
            "created_at",
            "latitude",
            "longitude",
            "width",
            "height",
            "favorite",
            "source",
            "review_file",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        summary = []
        for trip in trips:
            count = copy_candidates(conn, trip, writer)
            summary.append((trip, count))
    readme = OUT / "README.md"
    readme.write_text(
        "# Trip photo review\n\n"
        "Private local export from the Photos library. These are review candidates only, not public site assets.\n\n"
        "Selection uses capture month, rough GPS boxes for trips, Apple Photos aesthetic and curation scores, favorites, and local JPEG derivatives.\n\n"
        + "\n".join(f"- `{trip.slug}/`: {trip.title} ({trip.month}) - {count} photos" for trip, count in summary)
        + "\n"
    )
    print(f"Wrote {OUT}")
    print(f"Wrote {metadata_path}")
    print(f"Wrote {readme}")


if __name__ == "__main__":
    main()
