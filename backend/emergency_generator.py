"""emergency_generator.py - SIMULATED infrastructure emergencies. Independent of the drone simulation.

Standalone use:  python emergency_generator.py --seed 7 --count 5
"""
import argparse
import datetime
import json
import random
from geofencing import in_any_zone

DEFAULT_REGIONS = [
    {"id": "R1", "name": "Region 1 - West", "bounds": [12.950, 77.5500, 13.000, 77.5833], "color": "#38bdf8"},
    {"id": "R2", "name": "Region 2 - Central", "bounds": [12.950, 77.5833, 13.000, 77.6167], "color": "#a78bfa"},
    {"id": "R3", "name": "Region 3 - East", "bounds": [12.950, 77.6167, 13.000, 77.6500], "color": "#f472b6"},
]

INCIDENT_TYPES = {
    "BRIDGE_CRACK": ("Bridge structural crack", {"LOW": 2, "MEDIUM": 4, "HIGH": 3, "CRITICAL": 1},
                     ["Hairline crack along bridge deck joint", "Structural crack on bridge pier", "Widening crack on bridge girder"]),
    "PIPELINE_LEAK": ("Pipeline leakage", {"LOW": 2, "MEDIUM": 4, "HIGH": 3, "CRITICAL": 2},
                      ["Water main leakage reported by pressure drop", "Gas pipeline seep detected", "Fluid pooling near pipeline junction"]),
    "FIRE_SMOKE": ("Fire or smoke", {"LOW": 1, "MEDIUM": 3, "HIGH": 4, "CRITICAL": 3},
                   ["Smoke plume rising from warehouse roof", "Open fire in vacant plot", "Smouldering waste fire near residences"]),
    "BUILDING_DAMAGE": ("Building damage", {"LOW": 2, "MEDIUM": 4, "HIGH": 3, "CRITICAL": 2},
                        ["Partial wall collapse", "Roof section caved in", "Facade damage over pedestrian path"]),
    "POWER_LINE_DOWN": ("Fallen electrical infrastructure", {"LOW": 1, "MEDIUM": 3, "HIGH": 4, "CRITICAL": 3},
                        ["Power line down across roadway", "Transformer pole toppled", "Live conductor on ground"]),
    "ROAD_OBSTRUCTION": ("Road obstruction", {"LOW": 4, "MEDIUM": 4, "HIGH": 2, "CRITICAL": 1},
                         ["Fallen tree blocking lanes", "Debris covering carriageway", "Stalled vehicle chain blocking junction"]),
    "HEAT_ANOMALY": ("Unusual heat detection", {"LOW": 3, "MEDIUM": 4, "HIGH": 3, "CRITICAL": 1},
                     ["Thermal hotspot on rooftop", "Overheating substation equipment", "Abnormal heat signature at industrial site"]),
}
SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class EmergencyGenerator:
    def __init__(self, regions=None, seed=None):
        self.regions = {r["id"]: r for r in (regions or DEFAULT_REGIONS)}
        self.enabled_regions = list(self.regions)
        self.incidents = {}
        self.counter = 0
        self.auto = False
        self.interval_s = 15.0
        self._next_at = 0.0
        self.reseed(seed)

    # ---- configuration
    def reseed(self, seed):
        self.seed = seed
        self.rng = random.Random(seed)          # same seed -> same sequence of incidents

    def types(self):
        return [{"key": k, "label": v[0]} for k, v in INCIDENT_TYPES.items()]

    def region_of(self, lat, lon):
        for r in self.regions.values():
            b = r["bounds"]
            if b[0] <= lat <= b[2] and b[1] <= lon <= b[3]:
                return r["id"]
        return "UNASSIGNED"

    # ---- generation
    def generate_one(self, region_id=None, type=None, severity=None, lat=None, lon=None, excluded_zones=None):
        rng = self.rng
        pool = [r for r in self.enabled_regions if r in self.regions] or list(self.regions)
        region_id = region_id or rng.choice(pool)
        if region_id not in self.regions:
            raise ValueError(f"Unknown region {region_id}")
        type = type or rng.choice(list(INCIDENT_TYPES))
        if type not in INCIDENT_TYPES:
            raise ValueError(f"Unknown incident type {type}")
        label, weights, descs = INCIDENT_TYPES[type]
        severity = severity or rng.choices(SEVERITIES, [weights[s] for s in SEVERITIES])[0]
        desc = rng.choice(descs)
        excluded_zones = excluded_zones or []
        if lat is None or lon is None:
            b = self.regions[region_id]["bounds"]
            m = 0.0008                                          # ~90 m margin from region edges
            # Try several candidate locations so randomly generated incidents never
            # appear inside an operator-defined no-fly zone.
            for _ in range(500):
                candidate = (rng.uniform(b[0] + m, b[2] - m), rng.uniform(b[1] + m, b[3] - m))
                if not in_any_zone(candidate[0], candidate[1], excluded_zones):
                    lat, lon = candidate
                    break
            else:
                raise ValueError(f"No available emergency location in {region_id}; its area may be covered by no-fly zones")
        elif in_any_zone(lat, lon, excluded_zones):
            raise ValueError("Emergency location is inside a no-fly zone")
        self.counter += 1
        inc = {
            "id": f"INC-{self.counter:04d}", "type": type, "type_label": label,
            "lat": round(lat, 6), "lon": round(lon, 6), "severity": severity,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "description": f"[SIMULATED] {desc}", "detection_status": "PENDING", "status": "UNDETECTED",
            "region": self.region_of(lat, lon), "detected_by": [], "detections": [],
            "first_detected_by": None, "detected_at": None, "acknowledged_at": None, "resolved_at": None,
        }
        self.incidents[inc["id"]] = inc
        return inc

    def start_auto(self, interval_s=None, now=0.0):
        if interval_s:
            self.interval_s = max(1.0, float(interval_s))
        self.auto, self._next_at = True, now + self.interval_s

    def stop_auto(self):
        self.auto = False

    def auto_due(self, now):
        if self.auto and now >= self._next_at:
            self._next_at = now + self.interval_s
            return True
        return False

    def list(self):
        return list(self.incidents.values())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate SIMULATED emergencies (standalone)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--count", type=int, default=5)
    a = ap.parse_args()
    g = EmergencyGenerator(seed=a.seed)
    print(json.dumps([g.generate_one() for _ in range(a.count)], indent=2))
