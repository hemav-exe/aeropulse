"""Focused tests for AeroPulse AI preconfigured sweep and no-fly exclusion."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import geofencing as geo
import navigation as nav
from detection import Detector
from emergency_generator import EmergencyGenerator


def test_geofencing_and_astar():
    z = {"id": "Z", "shape": "circle", "center": [12.975, 77.60], "radius_m": 500, "rev": 1}
    a, b = (12.975, 77.58), (12.975, 77.62)
    assert not geo.segment_clear(a, b, [z])
    route = nav.plan_route([a, b], [z])
    assert route and len(route) > 2 and not geo.route_hits_zones(route, [z])


def test_generator_reproducible():
    g1, g2 = EmergencyGenerator(seed=5), EmergencyGenerator(seed=5)
    k = lambda g: [(i["type"], i["lat"], i["lon"], i["severity"]) for i in (g.generate_one() for _ in range(6))]
    assert k(g1) == k(g2)


def test_generator_rejects_no_fly_zone_location():
    g = EmergencyGenerator(seed=5)
    zone = {"id": "Z", "shape": "circle", "center": [12.975, 77.565], "radius_m": 500}
    try:
        g.generate_one("R1", lat=12.975, lon=77.565, excluded_zones=[zone])
    except ValueError as exc:
        assert "no-fly zone" in str(exc)
    else:
        raise AssertionError("Emergency inside no-fly zone should be rejected")


def test_end_of_sweep_detects_all_non_restricted_incidents():
    g = EmergencyGenerator(seed=5)
    safe = g.generate_one("R1", type="BRIDGE_CRACK", severity="HIGH", lat=12.975, lon=77.565)
    restricted = g.generate_one("R1", type="PIPELINE_LEAK", severity="MEDIUM", lat=12.976, lon=77.566)
    zone = {"id": "Z", "shape": "circle", "center": [12.976, 77.566], "radius_m": 150}

    class Drone:
        id = "DRN-1"
        name = "Drone 1"
        status = "COMPLETED"
        mission_type = "inspect"
        mission_id = 1
        region_id = "R1"
        lat, lon = 12.975, 77.565
        scan = None

    class Fleet:
        drones = {"DRN-1": Drone()}

    events = Detector().step(Fleet(), [safe, restricted], 0.25, [zone])
    assert safe["detection_status"] == "DETECTED"
    assert safe["detected_by"] == ["DRN-1"]
    assert safe["detections"][0]["method"] == "end-of-sweep scan"
    assert restricted["detection_status"] == "EXCLUDED"
    assert any(e["type"] == "incident_detected" for e in events)


def test_drone_mission_id_survives_manual_reset():
    from drone_simulator import Drone
    drone = Drone(0)
    region = {"bounds": [12.95, 77.55, 13.0, 77.5833]}
    drone.start_mission("inspect", [], region)
    first = drone.mission_id
    drone.reset()
    drone.start_mission("inspect", [], region)
    assert drone.mission_id == first + 1
