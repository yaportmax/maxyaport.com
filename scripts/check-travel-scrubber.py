#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "src/pages/travel.astro"
CSS = ROOT / "src/styles/global.css"


def assert_contains(content: str, needle: str, label: str) -> None:
    if needle not in content:
        raise AssertionError(f"Missing {label}: {needle}")


def main() -> None:
    page = PAGE.read_text()
    css = CSS.read_text()

    if "data-map-active-card" in page:
        raise AssertionError("Active timeline detail card should be removed from travel page markup.")
    if "data-map-active-detail" in page:
        raise AssertionError("Timeline should not render the duplicated trip/race detail under the rail.")

    assert_contains(page, "data-travel-scrubber", "timeline scrubber input")
    assert_contains(page, "data-travel-scrubber-title", "scrubber title output")
    assert_contains(page, "route-progress-marker", "Mapbox route progress marker source/layer")
    assert_contains(page, "setScrubberProgress", "scrubber progress controller")
    assert_contains(page, "updateRouteProgressMarker", "route progress marker updater")
    assert_contains(css, ".travel-scrubber", "scrubber CSS")
    assert_contains(css, "::-webkit-slider-thumb", "native range thumb styling")


if __name__ == "__main__":
    main()
