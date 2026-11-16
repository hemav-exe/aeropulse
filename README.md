# AeroPulse AI - Autonomous Drone Navigation & Emergency Detection (SIMULATION)

A working end-to-end prototype: FastAPI backend + WebSocket live updates + React/Leaflet ground-station UI.
**Everything is simulated.** Drones, GPS positions and emergencies are generated in software. The system
controls no real drones and does not detect real-world emergencies.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd backend && python main.py                            # or: uvicorn main:app --port 8000
```
Open http://127.0.0.1:8000 . The browser needs internet access for the CDN scripts (React, Tailwind, Leaflet, OpenStreetMap tiles).

Click **Run demo** on the Command Dashboard to run the full scenario automatically. Run the automated test with `python -m pytest -s tests`.

## Map provider (documented substitution)
Google Maps needs an API key and billing, so this build uses **Leaflet + standard OpenStreetMap tiles** (`tile.openstreetmap.org`, with an automatic fallback to `tile.openstreetmap.fr`), which need no key.
Only the display layer is map-specific. Routing, geofencing and detection live in the Python backend, so a Google Maps
JavaScript API layer can replace `MapView` in `frontend/app.jsx` without touching backend logic. Directions APIs are not used for flight routes.

## Layout
| File | Role |
|---|---|
| `backend/main.py` | FastAPI app, REST + WebSocket, sim loop, demo runner |
| `backend/drone_simulator.py` | Drone movement, battery, mission state, rerouting on zone changes |
| `backend/navigation.py` | A* on a geo grid (8-connected, safety buffer), path smoothing, lawn-mower sweep planner |
| `backend/geofencing.py` | Haversine, point-in-polygon, circle/polygon zones, segment-vs-zone tests, validation |
| `backend/emergency_generator.py` | Independent seeded random incident generator (also runnable standalone) |
| `backend/detection.py` | Radius + simulated scan-time detection, de-duplication, multi-drone records |
| `backend/reporting.py` | JSON / CSV / PDF reports (PDF built without extra dependencies) |
| `frontend/index.html`, `app.jsx` | Seven-page ground station UI |

## How it works
* **Routing:** a drone plans its whole remaining route. Straight legs stay straight when clear; otherwise A* finds a detour with a 70 m buffer around zones.
* **New or edited zone:** every active route is tested against the zones. Affected drones are flagged "route blocked", replanned immediately, and notified in the UI. If no safe path exists the drone holds as BLOCKED and retries when zones change.
* **Detection:** a drone reports an incident only if it is assigned to the incident's region, is FLYING inside its detection radius (400 m, Haversine) and stays in range for the 3 s simulated scan. One incident record keeps all detecting drones. A drone never reports the same incident twice. HIGH and CRITICAL raise a high-priority alert (red toast + beep).
* **Generator:** `random.Random(seed)` makes runs reproducible. Set the seed on the Emergency Generator page or use `python emergency_generator.py --seed 7 --count 5`.
* **Sim speed:** the slider scales simulated time (1-40x).

## Demo mode (what it does)
It calls the same functions the UI buttons use: reset, assign R1/R2/R3, start all missions, add a no-fly zone on Drone 1's planned route
(triggers real recalculation), start the auto generator, then generate a HIGH "bridge crack" in Drone 2's region. For a short demo, that
incident's coordinates are placed on Drone 2's route (inside region R2) via the generator's optional `lat/lon` argument. Detection, alerting and
reports are all produced by the normal logic, not scripted. Then download the report from Reports & History.

## Manual demo
1. Mission Planner -> "Assign Drone 1/2/3 to R1/R2/R3" -> Start all. 2. No-Fly Zone Manager -> draw a circle over a drone's path.
3. Emergency Generator -> pick R2 + Bridge crack -> Generate. 4. Watch Incident Detection. 5. Reports & History -> CSV/PDF.

## Limits
Prototype state is in memory (restart clears it). No authentication. Single-process only. Grid planning is 2D (altitude is not planned).

## Troubleshooting the map
* Open the app at `http://127.0.0.1:8000` (not by double-clicking `index.html`); OpenStreetMap rejects tile requests that carry no referrer.
* A tile image that says "API KEY REQUIRED" or "Access blocked" comes from a tile server, not from this code. Hard-refresh (Ctrl+Shift+R) to drop cached tiles from an older version.
* If the map is grey or only partly drawn, resize the window once; the map re-measures itself automatically.
* If both tile servers are unreachable, an amber notice appears and all overlays still draw.


## Deploy online without API keys (GitHub + Render)

This project does not require a Google Maps, OpenAI, Gemini, or other application API key.
The map uses Leaflet in the browser and OpenStreetMap tiles. The frontend and backend are served
from the same FastAPI web service, so no separate frontend hosting or CORS configuration is needed.

### 1. Push the project to GitHub

1. Extract this project folder.
2. Create a new **public** or **private** repository on GitHub (for example, `aeropulse-ai`).
3. Upload the contents of this folder to the repository root. The `render.yaml` file must be at
   the repository root, alongside `requirements.txt`, `backend/`, and `frontend/`.
4. Commit and push to the `main` branch.

You can also use Git from this folder:

```bash
git init
git add .
git commit -m "Initial AeroPulse AI project"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/aeropulse-ai.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your GitHub username and use your actual repository URL.

### 2. Deploy with Render

1. Sign in to Render and connect your GitHub account.
2. Choose **New → Blueprint** and select your `aeropulse-ai` repository.
3. Render reads `render.yaml` and creates the web service.
4. Confirm the Free plan if you want to use the free tier, then deploy.
5. When deployment succeeds, open the `onrender.com` URL shown by Render.

If you create a Web Service manually instead of using Blueprint, use:
- Runtime: Python
- Build command: `pip install -r requirements.txt`
- Start command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/api/state`

### 3. Verify the deployment

- Open the root website URL to load the dashboard.
- Open `/api/state` after the domain to confirm the backend responds with simulation state.
- Start the demo and check that the map, drone movement, WebSocket updates, alerts, and report downloads work.

### Deployment notes

- Render Free web services can sleep after 15 minutes without inbound traffic. The first visit after sleep can take about a minute to wake up.
- The prototype stores simulation state in memory. A restart, redeploy, or sleep/restart can reset drones and incident history. This build does not include a persistent database.
- Render supports WebSockets, which this dashboard uses for live updates.
- OpenStreetMap's public tile service does not require an API key, but it is a shared community service with usage rules. Keep visible attribution, allow normal browser referrer behaviour, respect caching, and do not bulk-download tiles. For heavier public usage, choose a tile provider whose terms fit your deployment.
- GitHub is the source-code repository; Render runs the application. A GitHub Pages deployment alone will not run the Python/FastAPI backend or WebSocket simulation.
