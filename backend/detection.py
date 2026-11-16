"""detection.py - drones detect during radius scans and reconcile all remaining eligible incidents at end of sweep."""
import datetime
from geofencing import haversine_m, in_any_zone


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


class Detector:
    def __init__(self, scan_time_s=3.0):
        self.scan_time_s = scan_time_s            # simulated seconds a drone must stay in range
        self.progress = {}                        # (drone_id, incident_id) -> seconds scanned
        self.completed_sweeps = set()              # (drone_id, mission_id)

    def reset(self):
        self.progress.clear()
        self.completed_sweeps.clear()

    def _record_detection(self, d, inc, distance_m, method="radius scan"):
        first = inc["detection_status"] == "PENDING"
        t = now_iso()
        if d.id not in inc["detected_by"]:
            inc["detected_by"].append(d.id)
        inc["detections"].append({"drone": d.id, "time": t, "distance_m": round(distance_m), "method": method})
        if not first:
            return {"type": "incident_confirmed", "priority": "INFO", "drone": d.id, "incident": inc["id"],
                    "message": f"{d.name} also confirmed {inc['id']} (single incident record kept)"}
        inc.update(detection_status="DETECTED", status="DETECTED", detected_at=t, first_detected_by=d.id)
        hi = inc["severity"] in ("HIGH", "CRITICAL")
        return {"type": "incident_detected", "priority": "ALERT" if hi else "INFO", "drone": d.id,
                "incident": inc["id"],
                "message": f"{'HIGH-PRIORITY ' if hi else ''}{inc['severity']} {inc['type_label']} detected by "
                           f"{d.name} at {inc['lat']:.5f}, {inc['lon']:.5f} - {inc['description']}"}

    def step(self, fleet, incidents, dt, zones=None):
        events = []
        zones = zones or []
        for d in fleet.drones.values():
            d.scan = None
            # When an inspection route finishes, reconcile every remaining incident
            # in that drone's assigned region. Restricted-area incidents are excluded.
            if d.status == "COMPLETED" and d.mission_type == "inspect" and d.region_id:
                sweep_key = (d.id, getattr(d, "mission_id", 0))
                if sweep_key not in self.completed_sweeps:
                    self.completed_sweeps.add(sweep_key)
                    for inc in incidents:
                        if inc["region"] != d.region_id or inc["detection_status"] != "PENDING":
                            continue
                        if in_any_zone(inc["lat"], inc["lon"], zones):
                            inc.update(detection_status="EXCLUDED", status="EXCLUDED", excluded_reason="Located inside a no-fly zone")
                            continue
                        events.append(self._record_detection(d, inc, haversine_m(d.lat, d.lon, inc["lat"], inc["lon"]), "end-of-sweep scan"))
                continue
            if d.status != "FLYING" or not d.region_id:
                continue
            for inc in incidents:
                # only the drone assigned to the incident's region scans for it; never re-report by same drone
                if inc["region"] != d.region_id or d.id in inc["detected_by"] or inc["status"] in ("RESOLVED", "EXCLUDED"):
                    continue
                if in_any_zone(inc["lat"], inc["lon"], zones):
                    inc.update(detection_status="EXCLUDED", status="EXCLUDED", excluded_reason="Located inside a no-fly zone")
                    self.progress.pop((d.id, inc["id"]), None)
                    continue
                dist = haversine_m(d.lat, d.lon, inc["lat"], inc["lon"])
                key = (d.id, inc["id"])
                if dist > d.detection_radius_m:
                    self.progress.pop(key, None)
                    continue
                p = self.progress.get(key, 0.0) + dt
                if p < self.scan_time_s:
                    self.progress[key] = p
                    d.scan = {"incident": inc["id"], "pct": int(100 * p / self.scan_time_s)}
                    continue
                self.progress.pop(key, None)
                events.append(self._record_detection(d, inc, dist, "radius scan"))
        return events
