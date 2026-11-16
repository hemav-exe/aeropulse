"""AeroPulse AI - backend entry point (FastAPI + WebSockets).  SIMULATION ONLY - controls no real drones."""
import asyncio
import datetime
import os
import random
import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import geofencing as geo
import navigation as nav
import reporting
from detection import Detector, now_iso
from drone_simulator import Fleet
from emergency_generator import DEFAULT_REGIONS, EmergencyGenerator

TICK_S = 0.25


class Sim:
    def __init__(self):
        self.clients = set()
        self.scale = 10.0
        self.demo_task = None
        self.reset()

    def reset(self, seed=None, cancel_demo=True):
        if cancel_demo and self.demo_task and not self.demo_task.done():
            self.demo_task.cancel()
        self.zones, self.zone_n = {}, 0
        self.generator = EmergencyGenerator(DEFAULT_REGIONS, seed=seed)
        self.fleet, self.detector = Fleet(DEFAULT_REGIONS), Detector()
        self.events, self.log, self.demo_steps = [], [], []

    def zlist(self):
        return list(self.zones.values())

    def emit(self, type, message, priority="INFO", **data):
        ev = {"type": type, "message": message, "priority": priority, "time": now_iso(), **data}
        self.events.append(ev)
        self.log = (self.log + [ev])[-100:]

    def add(self, evs):
        for e in evs:
            self.emit(e.pop("type"), e.pop("message"), e.pop("priority", "INFO"), **e)

    def snapshot(self):
        incs = self.generator.list()
        drones = []
        for d in self.fleet.drones.values():
            dd = d.to_dict()
            dd["detected"] = [i["id"] for i in incs if d.id in i["detected_by"]]
            dd["pending"] = sum(1 for i in incs if i["region"] == d.region_id and i["detection_status"] == "PENDING")
            drones.append(dd)
        st = [d["status"] for d in drones]
        return {
            "time": now_iso(), "scale": self.scale, "drones": drones, "zones": self.zlist(),
            "regions": list(self.fleet.regions.values()), "incidents": incs, "log": self.log[-40:],
            "demo_steps": self.demo_steps,
            "generator": {"auto": self.generator.auto, "interval_s": self.generator.interval_s, "seed": self.generator.seed,
                          "enabled_regions": self.generator.enabled_regions, "types": self.generator.types(),
                          "count": self.generator.counter},
            "stats": {
                "drones": len(drones), "active": st.count("FLYING"),
                "idle": sum(s in ("IDLE", "COMPLETED", "PAUSED") for s in st),
                "errors": sum(s in ("ERROR", "E_STOP", "BLOCKED") for s in st),
                "incidents": len(incs), "detected": sum(i["detection_status"] == "DETECTED" for i in incs),
                "undetected": sum(i["detection_status"] == "PENDING" for i in incs),
                "critical": sum(i["severity"] == "CRITICAL" and i["status"] != "RESOLVED" for i in incs),
            },
        }

    async def broadcast(self):
        events, self.events = self.events, []
        if not self.clients:
            return
        msg = {"type": "state", "state": self.snapshot(), "events": events}
        for c in list(self.clients):
            try:
                await c.send_json(msg)
            except Exception:
                self.clients.discard(c)


sim = Sim()


async def sim_loop():
    last = time.monotonic()
    while True:
        await asyncio.sleep(TICK_S)
        now = time.monotonic()
        dt, last = (now - last) * sim.scale, now
        try:
            sim.add(sim.fleet.step(dt, sim.zlist()))
            sim.add(sim.detector.step(sim.fleet, sim.generator.list(), dt))
            await sim.broadcast()
        except Exception as e:                      # keep the loop alive
            print("sim error:", repr(e))


async def generator_loop():
    """Independent of the drone simulation: only touches the generator."""
    while True:
        await asyncio.sleep(0.5)
        if sim.generator.auto_due(time.monotonic()):
            inc = sim.generator.generate_one()
            sim.emit("incident_generated", f"{inc['id']} generated in {inc['region']} (undetected)", "QUIET", incident=inc["id"])


@asynccontextmanager
async def lifespan(app):
    tasks = [asyncio.create_task(sim_loop()), asyncio.create_task(generator_loop())]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="AeroPulse AI (simulation)", lifespan=lifespan)


# ---------------------------------------------------------------- helpers / models
def drone_or_404(did):
    d = sim.fleet.drones.get(did)
    if not d:
        raise HTTPException(404, f"Unknown drone {did}")
    return d


class Pos(BaseModel):
    lat: float
    lon: float


class Region(BaseModel):
    region_id: str


class Mission(BaseModel):
    type: str = "inspect"


class ZoneIn(BaseModel):
    name: str = "No-Fly Zone"
    reason: str = ""
    shape: str
    center: Optional[List[float]] = None
    radius_m: Optional[float] = None
    points: Optional[List[List[float]]] = None


class GenIn(BaseModel):
    region_id: Optional[str] = None
    type: Optional[str] = None
    severity: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class GenCfg(BaseModel):
    seed: Optional[int] = None
    interval_s: Optional[float] = None
    enabled_regions: Optional[List[str]] = None


class Scale(BaseModel):
    scale: float


def _start(d, kind):
    if d.status in ("FLYING", "E_STOP", "ERROR"):
        raise HTTPException(409, f"{d.name} cannot start a mission while {d.status} (use Reset for E_STOP/ERROR)")
    if kind == "transit":
        if not d.destination:
            raise HTTPException(400, f"{d.name}: set a destination first")
    elif kind == "inspect":
        if d.region_id not in sim.fleet.regions:
            raise HTTPException(400, f"{d.name}: assign an inspection region first")
    else:
        raise HTTPException(400, "type must be 'inspect' or 'transit'")
    sim.add(d.start_mission(kind, sim.zlist(), sim.fleet.regions.get(d.region_id)))


# ---------------------------------------------------------------- state / sim
@app.get("/api/state")
async def state():
    return sim.snapshot()


@app.post("/api/reset")
async def reset():
    sim.reset()
    sim.emit("reset", "Simulation reset", "INFO")
    return {"ok": True}


@app.post("/api/sim/speed")
async def speed(s: Scale):
    sim.scale = max(1.0, min(40.0, s.scale))
    return {"scale": sim.scale}


# ---------------------------------------------------------------- drones
@app.post("/api/drones/{did}/assign")
async def assign(did: str, r: Region):
    d = drone_or_404(did)
    if r.region_id not in sim.fleet.regions:
        raise HTTPException(400, "Unknown region")
    if d.status == "FLYING":
        raise HTTPException(409, "Drone is flying")
    d.region_id = r.region_id
    sim.emit("region_assigned", f"{d.name} assigned to {sim.fleet.regions[r.region_id]['name']}", "INFO")
    return {"ok": True}


@app.post("/api/drones/{did}/start-location")
async def start_loc(did: str, p: Pos):
    d = drone_or_404(did)
    if d.status in ("FLYING", "PAUSED"):
        raise HTTPException(409, "Cannot move the start point of an active drone")
    if geo.in_any_zone(p.lat, p.lon, sim.zlist()):
        raise HTTPException(400, "Start location is inside a no-fly zone")
    d.lat, d.lon, d.base = p.lat, p.lon, (p.lat, p.lon)
    return {"ok": True}


@app.post("/api/drones/{did}/destination")
async def destination(did: str, p: Pos):
    d = drone_or_404(did)
    if geo.in_any_zone(p.lat, p.lon, sim.zlist()):
        raise HTTPException(400, "Destination is inside a no-fly zone")
    d.destination = (p.lat, p.lon)
    return {"ok": True}


@app.delete("/api/drones/{did}/destination")
async def clear_destination(did: str):
    drone_or_404(did).destination = None
    return {"ok": True}


@app.post("/api/drones/{did}/mission")
async def mission(did: str, m: Mission):
    _start(drone_or_404(did), m.type)
    return {"ok": True}


@app.post("/api/drones/{did}/{action}")
async def drone_action(did: str, action: str):
    d = drone_or_404(did)
    if action == "pause":
        sim.add(d.pause())
    elif action == "resume":
        sim.add(d.resume())
    elif action == "estop":
        sim.add(d.emergency_stop())
    elif action == "reset":
        d.reset()
        sim.emit("drone_reset", f"{d.name} reset to base", "INFO")
    else:
        raise HTTPException(404, "Unknown action")
    return {"ok": True}


@app.post("/api/fleet/{action}")
async def fleet_action(action: str):
    n = 0
    for d in sim.fleet.drones.values():
        if action == "start":
            if d.status in ("IDLE", "COMPLETED", "PAUSED") and d.region_id:
                if d.status == "PAUSED":
                    sim.add(d.resume())
                else:
                    _start(d, "inspect")
                n += 1
        elif action == "pause":
            sim.add(d.pause())
        elif action == "resume":
            sim.add(d.resume())
        elif action == "estop":
            sim.add(d.emergency_stop())
        else:
            raise HTTPException(404, "Unknown fleet action")
    if action == "start" and n == 0:
        raise HTTPException(400, "No drone ready: assign regions first")
    return {"ok": True, "drones": n}


# ---------------------------------------------------------------- no-fly zones
def _zone_changed(zone, verb):
    sim.emit(f"zone_{verb}", f"No-fly zone '{zone['name']}' ({zone['id']}) {verb}", "WARN" if verb != "removed" else "INFO")
    sim.add(sim.fleet.on_zones_changed(sim.zlist()))


@app.get("/api/zones")
async def zones():
    return sim.zlist()


@app.post("/api/zones")
async def add_zone(z: ZoneIn):
    try:
        zone = geo.validate_zone(z.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))
    sim.zone_n += 1
    zone.update(id=f"NFZ-{sim.zone_n:02d}", rev=1, created_at=now_iso())
    sim.zones[zone["id"]] = zone
    _zone_changed(zone, "added")
    return zone


@app.put("/api/zones/{zid}")
async def edit_zone(zid: str, z: ZoneIn):
    old = sim.zones.get(zid)
    if not old:
        raise HTTPException(404, "Unknown zone")
    try:
        zone = geo.validate_zone(z.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))
    zone.update(id=zid, rev=old["rev"] + 1, created_at=old["created_at"])
    sim.zones[zid] = zone
    _zone_changed(zone, "edited")
    return zone


@app.delete("/api/zones/{zid}")
async def del_zone(zid: str):
    zone = sim.zones.pop(zid, None)
    if not zone:
        raise HTTPException(404, "Unknown zone")
    _zone_changed(zone, "removed")
    return {"ok": True}


# ---------------------------------------------------------------- generator / incidents
@app.post("/api/generator/generate")
async def gen_one(g: GenIn):
    try:
        inc = sim.generator.generate_one(g.region_id, g.type, g.severity, g.lat, g.lon)
    except ValueError as e:
        raise HTTPException(400, str(e))
    sim.emit("incident_generated", f"{inc['id']} ({inc['type_label']}) generated in {inc['region']} - waiting for detection",
             "QUIET", incident=inc["id"])
    return inc


@app.post("/api/generator/start")
async def gen_start():
    sim.generator.start_auto(None, time.monotonic())
    sim.emit("generator", f"Automatic emergency generation started (every {sim.generator.interval_s:.0f}s)", "INFO")
    return {"ok": True}


@app.post("/api/generator/stop")
async def gen_stop():
    sim.generator.stop_auto()
    sim.emit("generator", "Automatic emergency generation stopped", "INFO")
    return {"ok": True}


@app.post("/api/generator/config")
async def gen_cfg(c: GenCfg):
    g = sim.generator
    if c.seed is not None:
        g.reseed(c.seed)
    if c.interval_s:
        g.interval_s = max(1.0, c.interval_s)
    if c.enabled_regions is not None:
        g.enabled_regions = [r for r in c.enabled_regions if r in g.regions]
    return {"ok": True}


@app.get("/api/incidents")
async def incidents():
    return sim.generator.list()


def _inc(iid):
    i = sim.generator.incidents.get(iid)
    if not i:
        raise HTTPException(404, "Unknown incident")
    return i


@app.post("/api/incidents/{iid}/acknowledge")
async def ack(iid: str):
    i = _inc(iid)
    if i["detection_status"] != "DETECTED":
        raise HTTPException(409, "Incident has not been detected by a drone yet")
    if i["status"] == "DETECTED":
        i.update(status="ACKNOWLEDGED", acknowledged_at=now_iso())
    return i


@app.post("/api/incidents/{iid}/resolve")
async def resolve(iid: str):
    i = _inc(iid)
    if i["detection_status"] != "DETECTED":
        raise HTTPException(409, "Incident has not been detected by a drone yet")
    i.update(status="RESOLVED", resolved_at=now_iso())
    if not i["acknowledged_at"]:
        i["acknowledged_at"] = i["resolved_at"]
    return i


# ---------------------------------------------------------------- reports
def _download(data, media, name):
    return Response(content=data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/reports/incidents.csv")
async def rep_csv():
    return _download(reporting.export_csv(sim.generator.list()), "text/csv", "aeropulse_incidents.csv")


@app.get("/api/reports/incidents.pdf")
async def rep_pdf():
    return _download(reporting.export_pdf(sim.generator.list()), "application/pdf", "aeropulse_incidents.pdf")


@app.get("/api/reports/incident/{iid}.pdf")
async def rep_one_pdf(iid: str):
    return _download(reporting.export_pdf([_inc(iid)], f"AeroPulse AI - Incident {iid}"), "application/pdf", f"{iid}.pdf")


@app.get("/api/reports/incident/{iid}.json")
async def rep_one_json(iid: str):
    return reporting.build_report(_inc(iid))


# ---------------------------------------------------------------- demo mode (drives the real endpoints/logic)
def _point_ahead(drone, region, min_ahead=800.0):
    """First point on the drone's planned route (>= min_ahead m away) that lies inside the region."""
    r = drone.route_points()
    if len(r) < 2:
        return None
    b = region["bounds"]
    for dist, lat, lon in nav.sample_route(r, 100.0):
        if dist >= min_ahead and b[0] + 0.001 < lat < b[2] - 0.001 and b[1] + 0.001 < lon < b[3] - 0.001:
            return lat, lon
    return None


def _step(text):
    sim.demo_steps.append({"t": now_iso(), "text": text})
    sim.emit("demo", f"DEMO: {text}", "INFO")


async def demo_runner():
    try:
        sim.reset(seed=42, cancel_demo=False)
        sim.scale = 25.0
        _step("1. Dashboard ready - 3 simulated drones on the map")
        for d, r in zip(sim.fleet.drones.values(), ["R1", "R2", "R3"]):
            await assign(d.id, Region(region_id=r))
        _step("2. Each drone assigned a different inspection region (R1, R2, R3)")
        await fleet_action("start")
        _step("3. All three drone missions started")
        await asyncio.sleep(6)
        d1 = sim.fleet.drones["DRN-1"]
        pt = _point_ahead(d1, sim.fleet.regions["R1"], 1200.0) or (d1.lat + 0.01, d1.lon)
        z = await add_zone(ZoneIn(name="Demo NFZ - Event airspace", reason="Temporary restriction (demo)",
                                  shape="circle", center=list(pt), radius_m=450))
        _step(f"4. No-fly zone {z['id']} drawn on {d1.name}'s planned route - affected route recalculated automatically")
        await asyncio.sleep(4)
        sim.generator.start_auto(12.0, time.monotonic())
        _step("5. Python random emergency generator started (auto mode, seed 42)")
        d2 = sim.fleet.drones["DRN-2"]
        pt = _point_ahead(d2, sim.fleet.regions["R2"])
        rnd = random.Random(7)
        kw = {}
        if pt:
            kw = dict(lat=pt[0] + rnd.uniform(-0.0008, 0.0008), lon=pt[1] + rnd.uniform(-0.0008, 0.0008))
        inc = await gen_one(GenIn(region_id="R2", type="BRIDGE_CRACK", severity="HIGH", **kw))
        _step(f"6. Bridge crack {inc['id']} generated in {d2.name}'s region - pending, not yet detected")
        for _ in range(900):
            await asyncio.sleep(0.5)
            if inc["detection_status"] == "DETECTED":
                break
        else:
            _step("Timed out waiting for detection")
            return
        _step(f"7. {inc['first_detected_by']} detected {inc['id']} at {inc['lat']:.5f}, {inc['lon']:.5f} - alert sent to ground station")
        _step("8. Open Reports & History to download the incident report (CSV / PDF)")
    except asyncio.CancelledError:
        raise
    except Exception as e:
        _step(f"Demo error: {e!r}")


@app.post("/api/demo/start")
async def demo_start():
    if sim.demo_task and not sim.demo_task.done():
        raise HTTPException(409, "Demo already running")
    sim.demo_task = asyncio.create_task(demo_runner())
    return {"ok": True}


@app.post("/api/demo/stop")
async def demo_stop():
    if sim.demo_task and not sim.demo_task.done():
        sim.demo_task.cancel()
    return {"ok": True}


# ---------------------------------------------------------------- websocket + static frontend
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    sim.clients.add(websocket)
    try:
        await websocket.send_json({"type": "state", "state": sim.snapshot(), "events": []})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        sim.clients.discard(websocket)


FRONTEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
