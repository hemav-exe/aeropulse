"""End-to-end test of the demonstration scenario through the real API (run: pytest -s tests)."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from fastapi.testclient import TestClient
import main
import geofencing as geo, navigation as nav
from emergency_generator import EmergencyGenerator


def test_geofencing_and_astar():
    z = {"id": "Z", "shape": "circle", "center": [12.975, 77.60], "radius_m": 500, "rev": 1}
    a, b = (12.975, 77.58), (12.975, 77.62)
    assert not geo.segment_clear(a, b, [z])
    r = nav.plan_route([a, b], [z])
    assert r and len(r) > 2 and not geo.route_hits_zones(r, [z])
    poly = {"id": "P", "shape": "polygon", "points": [[12.97, 77.59], [12.97, 77.61], [12.98, 77.61], [12.98, 77.59]], "rev": 1}
    assert geo.in_zone(12.975, 77.60, poly) and not geo.in_zone(12.99, 77.60, poly)


def test_generator_reproducible():
    a = [EmergencyGenerator(seed=5).generate_one() for _ in range(1)]
    g1, g2 = EmergencyGenerator(seed=5), EmergencyGenerator(seed=5)
    k = lambda g: [(i["type"], i["lat"], i["lon"], i["severity"]) for i in (g.generate_one() for _ in range(6))]
    assert k(g1) == k(g2)


def test_demo_end_to_end():
    with TestClient(main.app) as c:
        c.post("/api/reset")
        assert c.post("/api/demo/start").status_code == 200
        t0, inc = time.time(), None
        while time.time() - t0 < 150:
            st = c.get("/api/state").json()
            det = [i for i in st["incidents"] if i["detection_status"] == "DETECTED"]
            if det:
                inc = det[0]
                break
            time.sleep(1)
        assert inc, "no detection"
        print("detected after %.0fs by %s" % (time.time() - t0, inc["detected_by"]))
        assert inc["type"] == "BRIDGE_CRACK" and inc["region"] == "R2" and inc["first_detected_by"] == "DRN-2"
        types = [e["type"] for e in st["log"]]
        assert "route_blocked" in types and "route_recalculated" in types and "incident_detected" in types
        d1 = [d for d in st["drones"] if d["id"] == "DRN-1"][0]
        z = st["zones"][0]
        assert not geo.route_hits_zones([tuple(p) for p in d1["route"]], [z])
        assert c.post(f"/api/incidents/{inc['id']}/acknowledge").json()["status"] == "ACKNOWLEDGED"
        assert c.post(f"/api/incidents/{inc['id']}/resolve").json()["status"] == "RESOLVED"
        assert c.get("/api/reports/incidents.csv").text.startswith("id,")
        pdf = c.get(f"/api/reports/incident/{inc['id']}.pdf").content
        assert pdf.startswith(b"%PDF") and pdf.rstrip().endswith(b"%%EOF")
        c.post("/api/demo/stop")
