"""drone_simulator.py - simulated autonomous drones (movement, battery, mission state, rerouting)."""
import math
import navigation as nav
from geofencing import haversine_m, in_any_zone, route_hits_zones

CRUISE_ALT = 80.0
BASE = (12.9440, 77.5985)
COLORS = ["#38bdf8", "#a78bfa", "#f472b6"]


class Drone:
    def __init__(self, idx):
        self.id, self.name = f"DRN-{idx + 1}", f"Drone {idx + 1}"
        self.base = (BASE[0], BASE[1] + 0.0015 * idx)
        self.color = COLORS[idx % len(COLORS)]
        self.detection_radius_m, self.speed_mps = 400.0, 15.0
        self.region_id = None
        self.mission_id = 0
        self.reset()

    def reset(self):
        self.lat, self.lon = self.base
        self.alt, self.battery, self.status = 0.0, 100.0, "IDLE"
        self.destination, self.mission_type = None, None
        self.targets, self.path, self.path_i = [], [], 0
        self.trail, self.scanned_regions, self.scan = [], [], None
        self.heading, self.dist_m, self.note, self._low = 0.0, 0.0, "", False

    def _ev(self, type, msg, priority="INFO", **kw):
        return {"type": type, "message": msg, "priority": priority, "drone": self.id, **kw}

    # ---- route helpers
    def route_points(self):
        if self.status in ("COMPLETED", "IDLE") or not self.path:
            return []
        return [(self.lat, self.lon)] + list(self.path[self.path_i:])

    def remaining_m(self):
        r = self.route_points()
        return nav.route_length_m(r) if len(r) > 1 else 0.0

    @property
    def progress(self):
        if self.status == "COMPLETED":
            return 100.0
        if not self.targets:
            return 0.0
        rem = self.remaining_m()
        return round(100 * self.dist_m / (self.dist_m + rem), 1) if self.dist_m + rem > 0 else 0.0

    # ---- mission control
    def start_mission(self, kind, zones, region):
        self.mission_id += 1
        self.targets = [self.destination] if kind == "transit" else nav.sweep_waypoints(region["bounds"])
        self.mission_type, self.path, self.path_i, self.dist_m = kind, [], 0, 0.0
        self.trail, self.status, self.note = [(self.lat, self.lon)], "FLYING", ""
        if kind == "inspect" and self.region_id in self.scanned_regions:
            self.scanned_regions.remove(self.region_id)
        return [self._ev("mission_started", f"{self.name} started {kind} mission", region=self.region_id)] + self._plan(zones)

    def _plan(self, zones):
        """Plan the WHOLE remaining route (A* detours wherever a straight leg hits a zone)."""
        ev = []
        remaining = self._remaining_targets()
        keep = [t for t in remaining if not in_any_zone(t[0], t[1], zones, 0)]
        if len(keep) < len(remaining):
            ev.append(self._ev("waypoint_skipped", f"{self.name}: {len(remaining) - len(keep)} waypoint(s) inside a no-fly zone skipped", "WARN"))
        self.targets = self.targets[:len(self.targets) - len(remaining)] + keep
        if not keep:
            return ev + self._finish()
        route = nav.plan_route([(self.lat, self.lon)] + [tuple(t) for t in keep], zones)
        if route is None:
            self.status, self.path, self.note = "BLOCKED", [], "No safe route"
            return ev + [self._ev("route_blocked", f"{self.name}: NO SAFE ROUTE available - holding position", "WARN")]
        self.path, self.path_i = route, 1
        return ev

    def _remaining_targets(self):
        """Targets not yet reached: those after the last one the path has passed."""
        if not self.path:
            return list(self.targets)
        rest = self.path[self.path_i:]
        return [t for t in self.targets if tuple(t) in set(map(tuple, rest))]

    def _finish(self):
        self.status, self.path, self.note = "COMPLETED", [], "Mission complete"
        if self.mission_type == "inspect" and self.region_id not in self.scanned_regions:
            self.scanned_regions.append(self.region_id)
        return [self._ev("mission_complete", f"{self.name} completed its mission", region=self.region_id)]

    def replan(self, zones):
        old = self.remaining_m()
        if self.status == "BLOCKED":
            self.status = "FLYING"
        ev = self._plan(zones)
        if self.status not in ("BLOCKED", "COMPLETED"):
            extra = self.remaining_m() - old
            ev.append(self._ev("route_recalculated", f"{self.name}: route recalculated around no-fly zone ({extra:+.0f} m)", "WARN"))
        return ev

    def pause(self):
        if self.status == "FLYING":
            self.status = "PAUSED"
            return [self._ev("drone_paused", f"{self.name} paused")]
        return []

    def resume(self):
        if self.status == "PAUSED":
            self.status = "FLYING"
            return [self._ev("drone_resumed", f"{self.name} resumed")]
        return []

    def emergency_stop(self):
        self.status, self.note = "E_STOP", "Emergency stop"
        return [self._ev("emergency_stop", f"{self.name} EMERGENCY STOP", "ALERT")]

    # ---- simulation step (dt in simulated seconds)
    def step(self, dt, zones):
        ev = []
        if self.status in ("IDLE", "COMPLETED", "E_STOP", "ERROR"):
            self.alt = max(0.0, self.alt - 8 * dt)
        if self.status != "FLYING":
            return ev
        self.alt = min(CRUISE_ALT, self.alt + 6 * dt)
        remaining, moved = self.speed_mps * dt, 0.0
        while remaining > 0 and self.status == "FLYING":
            if self.path_i >= len(self.path):
                ev += self._finish()
                break
            tgt = self.path[self.path_i]
            d = haversine_m(self.lat, self.lon, tgt[0], tgt[1])
            if d > 0.01:
                self.heading = (math.degrees(math.atan2(tgt[1] - self.lon, tgt[0] - self.lat))) % 360
            if d <= remaining:
                self.lat, self.lon = tgt
                remaining -= d
                moved += d
                self.path_i += 1
            else:
                f = remaining / d
                self.lat += (tgt[0] - self.lat) * f
                self.lon += (tgt[1] - self.lon) * f
                moved += remaining
                remaining = 0
        self.dist_m += moved
        self.battery = max(0.0, self.battery - moved / 1000 * 0.55)
        if not self.trail or haversine_m(self.lat, self.lon, *self.trail[-1]) > 60:
            self.trail.append((self.lat, self.lon))
        if self.battery < 20 and not self._low:
            self._low = True
            ev.append(self._ev("low_battery", f"{self.name}: battery below 20%", "WARN"))
        if self.battery <= 0:
            self.status, self.note = "ERROR", "Battery depleted"
            ev.append(self._ev("drone_error", f"{self.name}: battery depleted - landing", "ALERT"))
        return ev

    def to_dict(self):
        r6 = lambda p: [round(p[0], 6), round(p[1], 6)]
        return {
            "id": self.id, "name": self.name, "color": self.color, "lat": round(self.lat, 6), "lon": round(self.lon, 6),
            "alt": round(self.alt, 1), "battery": round(self.battery, 1), "status": self.status, "region_id": self.region_id,
            "mission_type": self.mission_type, "mission_id": self.mission_id, "progress": self.progress,
            "speed": self.speed_mps if self.status == "FLYING" else 0.0, "heading": round(self.heading),
            "detection_radius_m": self.detection_radius_m, "base": r6(self.base),
            "destination": r6(self.destination) if self.destination else None,
            "route": [r6(p) for p in self.route_points()], "trail": [r6(p) for p in self.trail[-300:]],
            "scanned_regions": self.scanned_regions, "scan": self.scan, "note": self.note,
        }


class Fleet:
    def __init__(self, regions):
        self.regions = {r["id"]: r for r in regions}
        self.drones = {d.id: d for d in (Drone(i) for i in range(3))}

    def step(self, dt, zones):
        ev = []
        for d in self.drones.values():
            ev += d.step(dt, zones)
        return ev

    def on_zones_changed(self, zones):
        """Re-validate every active route against the current zone set; reroute what is affected."""
        ev = []
        for d in self.drones.values():
            if not d.targets or d.status not in ("FLYING", "PAUSED", "BLOCKED"):
                continue
            if d.status == "BLOCKED":
                ev += d.replan(zones)
                continue
            hit = route_hits_zones(d.route_points(), zones, 0)
            if hit:
                ev.append(d._ev("route_blocked", f"{d.name}: route blocked by {', '.join(hit)} - recalculating", "WARN", zones=hit))
                ev += d.replan(zones)
        return ev
