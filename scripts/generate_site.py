#!/usr/bin/env python3
"""Generate a privacy-preserving flight timeliness status page.

Inputs (env):
  - FLIGHT_NUMBER (required): e.g. UA1234

Output (created/overwritten):
  - site/index.html
  - site/data.json

Privacy goals:
  - The generated site must not include: airline name/code, flight number, origin, destination.
  - Keep all output to generic delay/status-only fields.

Implementation notes:
  - Uses FlightAware's embedded `trackpollBootstrap` JSON object on the public flight page.
  - Does not print the flight number (or request URL) to stdout/stderr.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class Timeliness:
    status: str
    departure_delay_min: int | None
    arrival_delay_min: int | None
    last_updated_utc: str
    note: str | None = None


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _fetch_html(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (GitHub Actions; +https://github.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        # FlightAware is UTF-8.
        return resp.read().decode("utf-8", errors="replace")


def _extract_trackpoll_bootstrap(html: str) -> dict[str, Any]:
    marker = "var trackpollBootstrap = "
    i = html.find(marker)
    if i < 0:
        raise ValueError("trackpollBootstrap marker not found")
    j = i + len(marker)
    k = html.find(";</script>", j)
    if k < 0:
        # Fallback: script closing tag exists even if semicolon formatting differs.
        k = html.find("</script>", j)
    if k < 0:
        raise ValueError("trackpollBootstrap script end not found")

    blob = html[j:k].strip()
    # Most pages end with `...}}};` (a trailing semicolon is outside this slice)
    if blob.endswith(";"):
        blob = blob[:-1]

    return json.loads(blob)


def _first_known_flight(bootstrap: dict[str, Any]) -> dict[str, Any] | None:
    flights = bootstrap.get("flights")
    if not isinstance(flights, dict):
        return None

    for _, flight in flights.items():
        if not isinstance(flight, dict):
            continue
        if flight.get("unknown") is True:
            continue
        return flight

    return None


def _delay_minutes(times: dict[str, Any] | None) -> int | None:
    """Compute delay minutes (actual/estimated - scheduled)."""
    if not isinstance(times, dict):
        return None

    scheduled = times.get("scheduled")
    actual = times.get("actual")
    estimated = times.get("estimated")

    # Prefer actual when available, else estimated.
    best = actual if isinstance(actual, (int, float)) else estimated

    if not isinstance(scheduled, (int, float)) or not isinstance(best, (int, float)):
        return None

    return int(round((best - scheduled) / 60.0))


def _derive_status(f: dict[str, Any]) -> str:
    if f.get("cancelled") is True:
        return "Cancelled"
    if f.get("diverted") is True:
        return "Diverted"

    landing_actual = (f.get("landingTimes") or {}).get("actual")
    takeoff_actual = (f.get("takeoffTimes") or {}).get("actual")
    gate_depart_actual = (f.get("gateDepartureTimes") or {}).get("actual")

    if isinstance(landing_actual, (int, float)):
        return "Arrived"
    if isinstance(takeoff_actual, (int, float)):
        return "In flight"
    if isinstance(gate_depart_actual, (int, float)):
        return "Departed gate"
    return "Scheduled"


def build_timeliness(flight_number: str) -> Timeliness:
    # Avoid printing flight_number; errors should remain generic.
    url = f"https://www.flightaware.com/live/flight/{flight_number}"

    try:
        html = _fetch_html(url)
        bootstrap = _extract_trackpoll_bootstrap(html)
        f = _first_known_flight(bootstrap)

        if not f:
            return Timeliness(
                status="Unavailable",
                departure_delay_min=None,
                arrival_delay_min=None,
                last_updated_utc=_utc_now_iso(),
                note="No tracking data available yet.",
            )

        departure_delay = _delay_minutes(f.get("gateDepartureTimes"))
        arrival_delay = _delay_minutes(f.get("gateArrivalTimes"))

        return Timeliness(
            status=_derive_status(f),
            departure_delay_min=departure_delay,
            arrival_delay_min=arrival_delay,
            last_updated_utc=_utc_now_iso(),
            note=None,
        )

    except Exception:
        # Keep this intentionally vague to avoid leaking identifiers in logs.
        return Timeliness(
            status="Unavailable",
            departure_delay_min=None,
            arrival_delay_min=None,
            last_updated_utc=_utc_now_iso(),
            note="Data fetch/parse error.",
        )


def _format_delay(mins: int | None) -> str:
    if mins is None:
        return "Unknown"
    if mins == 0:
        return "On time"
    if mins > 0:
        return f"Delayed by {mins} min"
    return f"Early by {abs(mins)} min"


def render_html(t: Timeliness) -> str:
    # Keep the page intentionally generic.
    dep = _format_delay(t.departure_delay_min)
    arr = _format_delay(t.arrival_delay_min)
    note_html = f"<p class=\"note\">{t.note}</p>" if t.note else ""

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>Flight timeliness</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; }}
    .card {{ border: 1px solid rgba(127,127,127,.35); border-radius: 12px; padding: 16px; }}
    h1 {{ margin: 0 0 8px; font-size: 22px; }}
    .meta {{ opacity: .8; font-size: 13px; margin: 0 0 12px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .item {{ border: 1px solid rgba(127,127,127,.25); border-radius: 10px; padding: 12px; }}
    .label {{ opacity: .75; font-size: 12px; margin: 0 0 6px; }}
    .value {{ font-size: 18px; margin: 0; }}
    .status {{ margin: 12px 0 0; font-weight: 600; }}
    .note {{ margin: 12px 0 0; opacity: .75; font-size: 13px; }}
    footer {{ margin-top: 18px; opacity: .6; font-size: 12px; }}
  </style>
</head>
<body>
  <div class=\"card\">
    <h1>Flight timeliness</h1>
    <p class=\"meta\">Last updated (UTC): <span id=\"updated\">{t.last_updated_utc}</span></p>

    <div class=\"grid\">
      <div class=\"item\">
        <p class=\"label\">Departure</p>
        <p class=\"value\">{dep}</p>
      </div>
      <div class=\"item\">
        <p class=\"label\">Arrival</p>
        <p class=\"value\">{arr}</p>
      </div>
    </div>

    <p class=\"status\">Status: <span id=\"status\">{t.status}</span></p>
    {note_html}

    <footer>
      This page intentionally omits airline, flight number, and route details.
    </footer>
  </div>
</body>
</html>
"""


def main() -> int:
    flight_number = os.environ.get("FLIGHT_NUMBER", "").strip()
    if not flight_number:
        # No identifier provided; still generate a safe page.
        t = Timeliness(
            status="Unavailable",
            departure_delay_min=None,
            arrival_delay_min=None,
            last_updated_utc=_utc_now_iso(),
            note="Missing FLIGHT_NUMBER secret.",
        )
    else:
        t = build_timeliness(flight_number)

    out_dir = os.path.join(os.getcwd(), "site")
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "data.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "status": t.status,
                "departure_delay_min": t.departure_delay_min,
                "arrival_delay_min": t.arrival_delay_min,
                "last_updated_utc": t.last_updated_utc,
                "note": t.note,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
        f.write("\n")

    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_html(t))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
