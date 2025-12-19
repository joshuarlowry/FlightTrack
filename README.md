# FlightTrack

Generates a **privacy-preserving** GitHub Pages site that shows **timeliness-only** updates for a flight.

## What it shows (and what it does not)

- **Shows**: generic status + delay minutes (e.g. "Delayed by 12 min")
- **Does not show**: airline, flight number, origin, destination

## Setup

1. **Create the secret** `FLIGHT_NUMBER`
   - Example value: `UA1234`

2. **Enable GitHub Pages (Actions deployment)**
   - Repo Settings → Pages → **Source: GitHub Actions**

3. **Enable/disable scheduled rebuilds**

This repo uses a schedule that runs every 15 minutes, but it is gated by a repo variable so you can turn it off when you’re done.

- **To enable the every-15-min updates (today):**
  - Repo Settings → Secrets and variables → Actions → **Variables**
  - Create/update `FLIGHT_UPDATES_ENABLED` = `true`

- **To disable updates (later):**
  - Set `FLIGHT_UPDATES_ENABLED` = `false` (or delete the variable)
  - The last deployed page stays up, but it will stop rebuilding on the cron.

You can still run it manually anytime via **Actions → “Flight timeliness page” → Run workflow**, even when the cron is disabled.

You can also disable the workflow entirely in the Actions UI if you prefer, but the variable toggle is the quickest on/off switch.

## How it works

- `scripts/generate_site.py` fetches public flight status data and generates `site/index.html` and `site/data.json`.
- `.github/workflows/flight-timeliness-pages.yml` deploys `site/` to GitHub Pages.
