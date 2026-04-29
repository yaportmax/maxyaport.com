#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib import parse, request
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".strava-work"
API = "https://www.strava.com/api/v3"


def api_get(path: str, token: str, params: dict[str, str | int] | None = None):
    url = f"{API}{path}"
    if params:
        url += "?" + parse.urlencode(params)
    req = request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def refresh_access_token() -> dict:
    required = ["STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "STRAVA_REFRESH_TOKEN"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing env vars for refresh: {', '.join(missing)}")

    payload = parse.urlencode(
        {
            "client_id": os.environ["STRAVA_CLIENT_ID"],
            "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
            "refresh_token": os.environ["STRAVA_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    req = request.Request("https://www.strava.com/api/v3/oauth/token", data=payload, method="POST")
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_token() -> str:
    if all(os.environ.get(name) for name in ["STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "STRAVA_REFRESH_TOKEN"]):
        token_data = refresh_access_token()
        (OUT / "token-refresh.json").write_text(json.dumps(token_data, indent=2))
        return token_data["access_token"]

    token = os.environ.get("STRAVA_ACCESS_TOKEN", "")
    if not token:
        token_data = refresh_access_token()
        (OUT / "token-refresh.json").write_text(json.dumps(token_data, indent=2))
        return token_data["access_token"]
    try:
        api_get("/athlete", token)
        return token
    except HTTPError as error:
        if error.code != 401:
            raise
        token_data = refresh_access_token()
        (OUT / "token-refresh.json").write_text(json.dumps(token_data, indent=2))
        return token_data["access_token"]


def main() -> int:
    OUT.mkdir(exist_ok=True)
    token = get_token()

    athlete = api_get("/athlete", token)
    (OUT / "athlete.json").write_text(json.dumps(athlete, indent=2))

    activities = []
    page = 1
    while True:
        try:
            batch = api_get("/athlete/activities", token, {"page": page, "per_page": 200})
        except HTTPError as error:
            if page == 1 and error.code == 401 and all(
                os.environ.get(name) for name in ["STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "STRAVA_REFRESH_TOKEN"]
            ):
                token_data = refresh_access_token()
                (OUT / "token-refresh.json").write_text(json.dumps(token_data, indent=2))
                token = token_data["access_token"]
                try:
                    batch = api_get("/athlete/activities", token, {"page": page, "per_page": 200})
                except HTTPError as retry_error:
                    body = retry_error.read().decode("utf-8", errors="replace")
                    print(f"Strava activity fetch failed with HTTP {retry_error.code}: {body}", file=sys.stderr)
                    return 2
            else:
                body = error.read().decode("utf-8", errors="replace")
                print(f"Strava activity fetch failed with HTTP {error.code}: {body}", file=sys.stderr)
                return 2
        if not batch:
            break
        activities.extend(batch)
        print(f"Fetched page {page}: {len(batch)} activities")
        if len(batch) < 200:
            break
        page += 1
        time.sleep(0.2)

    (OUT / "activities.json").write_text(json.dumps(activities, indent=2))
    mapped = sum(1 for item in activities if (item.get("map") or {}).get("summary_polyline"))
    print(f"Wrote {OUT / 'activities.json'}")
    print(f"Activities: {len(activities)}")
    print(f"With summary polylines: {mapped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
