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
    if "data-travel-scrubber\n" in page or "data-travel-scrubber " in page:
        raise AssertionError("Timeline should not use a separate range scrollbar control.")
    if "travel-scrubber__range" in css or ".travel-scrubber" in css:
        raise AssertionError("Separate scrubber CSS should be removed; the timeline rail is the scrub surface.")

    assert_contains(page, "data-travel-scrubber-title", "scrubber title output")
    assert_contains(page, "data-initial-scrub-value", "timeline rail initial scrub state")
    assert_contains(page, "data-timeline-focus-start", "timeline calendar focus state")
    assert_contains(page, "data-map-timeline-time", "date-based timeline dot metadata")
    assert_contains(page, "route-progress-marker", "Mapbox route progress marker source/layer")
    assert_contains(page, "setScrubberProgress", "scrubber progress controller")
    assert_contains(page, "timelineValueFromScroll", "timeline scroll to scrub mapping")
    assert_contains(page, "timelineTimeFromScroll", "timeline scroll to calendar time mapping")
    assert_contains(page, "handleTimelineWheel", "wheel based timeline zoom")
    assert_contains(page, "Math.min(720", "compact timeline rail")
    assert_contains(page, "setTimelineZoomWidth(nextWidth)", "wheel zoom controller")
    assert_contains(page, "scrollLeft = dragStartScrollLeft - dragDelta", "direct drag timeline scroll")
    assert_contains(page, "updateRouteProgressMarker", "route progress marker updater")
    assert_contains(page, "maxZoom: 18", "expanded globe zoom limit")
    assert_contains(css, ".travel-timeline-rail.is-dragging", "dragging rail state")
    assert_contains(css, "touch-action: pan-x", "native horizontal touch gesture")


if __name__ == "__main__":
    main()
