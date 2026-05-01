#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "public/data/trip-photos/manifest.json"
PUBLIC = ROOT / "public"


def public_path_exists(src: Any) -> bool:
    value = str(src or "")
    return value.startswith("/") and (PUBLIC / value.lstrip("/")).is_file()


def valid_photo_metadata(photo: dict[str, Any]) -> bool:
    if "progress" not in photo:
        return True
    try:
        progress = float(photo["progress"])
    except (TypeError, ValueError):
        return False
    return 0 <= progress <= 1


def clean_groups(groups: dict[str, Any] | None) -> tuple[dict[str, list[dict[str, Any]]], int, int, int]:
    cleaned: dict[str, list[dict[str, Any]]] = {}
    kept = 0
    removed = 0
    invalid = 0

    for key, photos in (groups or {}).items():
        if not isinstance(photos, list):
            invalid += 1
            continue
        valid_photos = []
        for photo in photos:
            if isinstance(photo, dict) and public_path_exists(photo.get("src")) and valid_photo_metadata(photo):
                valid_photos.append(photo)
                kept += 1
            else:
                if isinstance(photo, dict) and public_path_exists(photo.get("src")):
                    invalid += 1
                else:
                    removed += 1
        if valid_photos:
            cleaned[key] = valid_photos

    return cleaned, kept, removed, invalid


def main() -> None:
    parser = argparse.ArgumentParser(description="Prune or validate missing trip photo manifest entries.")
    parser.add_argument("--check", action="store_true", help="Validate without writing.")
    args = parser.parse_args()

    if not MANIFEST.exists():
        raise SystemExit(f"Missing {MANIFEST}")

    manifest = json.loads(MANIFEST.read_text())
    cleaned_trips, kept_trips, removed_trips, invalid_trips = clean_groups(manifest.get("trips"))
    cleaned_strava, kept_strava, removed_strava, invalid_strava = clean_groups(manifest.get("strava") or manifest.get("activities"))
    if args.check and (removed_trips or removed_strava or invalid_trips or invalid_strava):
        raise SystemExit(
            "Trip photo manifest check failed: "
            f"{removed_trips + removed_strava} missing file reference(s), "
            f"{invalid_trips + invalid_strava} invalid metadata entries."
        )

    if not args.check:
        manifest["trips"] = cleaned_trips
        manifest["strava"] = cleaned_strava
        manifest.pop("activities", None)
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"Kept trip photos: {kept_trips}")
    print(f"Removed missing trip photos: {removed_trips}")
    print(f"Invalid trip photo metadata: {invalid_trips}")
    print(f"Kept Strava photos: {kept_strava}")
    print(f"Removed missing Strava photos: {removed_strava}")
    print(f"Invalid Strava photo metadata: {invalid_strava}")


if __name__ == "__main__":
    main()
