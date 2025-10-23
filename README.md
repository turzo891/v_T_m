# Vehicle Tracking Management System

Fleet monitoring demo built with Django and Leaflet that simulates real-time vehicle telemetry, renders live traffic overlays, and provides interactive filters for dispatch teams.

## Features

- **Road-following simulation** – Vehicles follow authentic Dhaka routes with Kalman-smoothed GPS traces, ETA estimates, and rich identifiers (plate, driver, device ID).
- **Interactive map UI** – Leaflet map with marker clustering, route trails, live traffic overlays, geofence polygons, depot markers, and configurable legends.
- **REST endpoints** – `/api/vehicles/` returns the latest vehicle snapshot while `/api/traffic/` streams traffic incidents (TomTom feed with graceful fallbacks).
- **Configurable overlays** – Geofences, depots, and routes are described in the backend and synchronised to the frontend for toggling and filtering.
- **Testing coverage** – Unit tests validate enriched API payloads, overlay metadata, and Kalman filter persistence.

## Getting Started

The `requirements.txt` file pins Django 4.2 LTS (current long-term support release) along with the supporting packages. Re-run `pip install -r requirements.txt` whenever the file changes.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 manage.py migrate          # optional – only required for admin/auth
python3 manage.py runserver
```

Open `http://127.0.0.1:8000/` to view the dashboard. The browser polls the backend every few seconds to refresh vehicle positions and traffic data.

### Development Utilities

- `python3 manage.py check` – Django system checks.
- `python3 manage.py test tracking` – Run the tracking app unit tests.
- `python3 manage.py createsuperuser` – (Optional) enable Django admin if you extend the data model.

### Map Tiles

Use the **Base Map** dropdown in the sidebar to switch between Mapbox and OpenStreetMap tiles on the fly.

- **Mapbox** – add a public access token to `.env` via `MAPBOX_ACCESS_TOKEN=...` (and optionally `MAPBOX_STYLE_ID`). The Mapbox option only appears when a token is present.
- **OpenStreetMap** – always available; you can override `OPENSTREET_TILE_URL` or `OPENSTREET_ATTRIBUTION` in `.env` if you serve custom tiles.

## Project Layout

| Path | Purpose |
| --- | --- |
| `vehicle_tracking_management_system/` | Django project configuration. |
| `tracking/` | Core app: services, views, URLs, tests. |
| `tracking/services.py` | Vehicle simulation, Kalman filtering, overlays, route definitions. |
| `tracking/traffic.py` | Traffic feed integration (TomTom + fallback data). |
| `templates/` | HTML templates with Leaflet map view (`tracking/map.html`). |
| `static/` | Front-end assets (`tracking/js/map.js`, `tracking/css/map.css`). |
| `VERSION` | Current project version string. |

## Version Control Policy

This repository tracks its release version in the `VERSION` file.

- Initial version: **0.0.10.5**
- On every meaningful update (feature, fix, release), bump the version following semantic `major.minor.patch.build` semantics.
- Example workflow:
  1. Edit project files.
  2. Update the `VERSION` file (e.g., `0.0.10.6`).
  3. Commit all changes together:  
     `git add . && git commit -m "Bump version to 0.0.10.6"`

Feel free to introduce release tags that match the version (e.g., `git tag v0.0.10.6`) for easier deployment tracking.

## Next Steps

- Hook the simulation into your live GPS ingestion service or database.
- Replace the traffic fallback with a production TomTom/HERE/Mapbox key.
- Extend the UI with custom filters, geofenced alerts, or driver performance dashboards.
- Containerise deployment or integrate with CI/CD for automated testing and linting.
