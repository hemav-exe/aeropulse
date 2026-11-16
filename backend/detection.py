"""detection.py - drones report an incident only after entering radius AND completing a simulated scan."""
import datetime
from geofencing import haversine_m


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


class Detector:
    def __init__(self, scan_time_s=3.0):
        self.scan_time_s = scan_time_s            # simulated seconds a drone must stay in range
        self.progress = {}                        # (drone_id, incident_id) -> seconds scanned

    def reset(self):
        self.progress.clear()

    def step(self, fleet, incidents, dt):
        events = []
        for d in fleet.drones.values():
            d.scan = None
            if d.status != "FLYING" or not d.region_id:
                continue
            for inc in incidents:
                # only the drone assigned to the incident's region scans for it; never re-report by same drone
                if inc["region"] != d.region_id or d.id in inc["detected_by"] or inc["status"] == "RESOLVED":
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
                first = inc["detection_status"] == "PENDING"
                t = now_iso()
                inc["detected_by"].append(d.id)
                inc["detections"].append({"drone": d.id, "time": t, "distance_m": round(dist)})
                if first:
                    inc.update(detection_status="DETECTED", status="DETECTED", detected_at=t, first_detected_by=d.id)
                    hi = inc["severity"] in ("HIGH", "CRITICAL")
                    events.append({"type": "incident_detected", "priority": "ALERT" if hi else "INFO", "drone": d.id,
                                   "incident": inc["id"],
                                   "message": f"{'HIGH-PRIORITY ' if hi else ''}{inc['severity']} {inc['type_label']} detected by "
                                              f"{d.name} at {inc['lat']:.5f}, {inc['lon']:.5f} - {inc['description']}"})
                else:
                    events.append({"type": "incident_confirmed", "priority": "INFO", "drone": d.id, "incident": inc["id"],
                                   "message": f"{d.name} also confirmed {inc['id']} (single record kept)"})
        return events
