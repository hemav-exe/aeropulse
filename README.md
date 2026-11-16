# AeroPulse AI – Autonomous Drone Navigation & Emergency Detection

A software-only multi-drone simulation for infrastructure inspection, no-fly-zone navigation, simulated emergency generation, detection and ground-station reporting. No physical drone control or real-world damage recognition is performed.

## Features

- Three simulated autonomous drones with region-based sweep missions.
- Leaflet + OpenStreetMap dashboard (no map API key required).
- A* route planning and operator-defined circular/polygon no-fly zones.
- Python-generated simulated infrastructure emergencies.
- Pre-configure no-fly zones and incidents before starting a demo.
- The Run demo action preserves the operator's prepared setup rather than resetting it.
- Drones detect incidents during normal scan-radius passes and reconcile all remaining eligible incidents in their assigned region when the sweep completes.
- Incidents located inside no-fly zones are excluded from generation/detection.
- FastAPI, WebSockets, incident history, CSV and PDF reports.
- Routine warning pop-ups are suppressed; actual emergency alerts remain visible.

## Run locally (Windows)

1. Install Python 3.11 or later.
2. Open this folder in VS Code.
3. In the terminal run:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   cd backend
   uvicorn main:app --reload --host 127.0.0.1 --port 8000
   ```

4. Open http://127.0.0.1:8000 in your browser.

On macOS/Linux, activate the environment with `source .venv/bin/activate`.

## Recommended demo workflow

1. Open **No-Fly Zone Manager** and draw all restricted circles/polygons.
2. Open **Emergency Generator**, choose a region/type/severity if desired, then use **Generate one emergency** or **Pre-generate emergencies** to stage incidents. New incidents are placed outside no-fly zones.
3. Open **Mission Planner** and use **Assign Drone 1/2/3 to R1/R2/R3** if you want to confirm the default region allocation. You can also assign regions individually.
4. Return to **Command Dashboard** and click **Run demo**.
5. The demo keeps the configured zones/incidents, starts the region sweeps, and reports remaining eligible incidents at the end of each drone's sweep.
6. Use **Reports & History** to acknowledge/resolve detected incidents and download CSV/PDF reports.

Do not click **Reset** between setup and the demo: Reset intentionally clears the current simulation state.

## Tests

```bash
pip install -r requirements.txt
pip install pytest httpx
pytest -q
```

## Deploy on Render (no API key)

This repository includes `render.yaml` for a Render Blueprint deployment:

1. Push the repository to GitHub.
2. In Render, choose **New + → Blueprint**.
3. Connect the GitHub repository and apply the detected `render.yaml` configuration.
4. Use the Free web service option if available in your account/region.

Render provides a public URL after a successful deployment. Free instances may sleep when idle, and in-memory simulation state is reset when the service restarts. This prototype does not use persistent storage.

## Technology

- Python, FastAPI, Uvicorn, Pydantic
- React (browser UMD build), JavaScript, Tailwind CDN
- Leaflet, OpenStreetMap
- A* route planning, geofencing, WebSockets

## API keys and external services

No Google Maps, OpenAI, Gemini or other application API key is required. The map uses public OpenStreetMap tile services; retain attribution and follow the tile usage policy: https://operations.osmfoundation.org/policies/tiles/ . The browser requires internet access to load the CDN-hosted React, Leaflet and Tailwind assets and map tiles.

## Limitations

- Drone flight, GPS, battery and scanning are simulated.
- Emergencies are simulated data, not actual sensor detections.
- End-of-sweep detection is a deterministic simulation rule: every pending incident in the drone's assigned region is marked detected unless it lies inside a no-fly zone.
- No physical drone is controlled and no real structural damage recognition is claimed.
