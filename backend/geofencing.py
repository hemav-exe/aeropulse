"""geofencing.py - no-fly zone geometry: haversine, point-in-polygon, segment/zone intersection."""
import math

R_EARTH = 6371008.8
M_PER_DEG_LAT = 110540.0
M_PER_DEG_LON = 111320.0


def haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(a))


def point_in_polygon(lat, lon, pts):
    """Ray casting. pts = [[lat, lon], ...]"""
    inside, n = False, len(pts)
    for i in range(n):
        y1, x1 = pts[i]
        y2, x2 = pts[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            xi = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
            if lon < xi:
                inside = not inside
    return inside


def _dist_to_segment_m(lat, lon, a, b):
    kx = M_PER_DEG_LON * math.cos(math.radians(lat))
    px, py = 0.0, 0.0
    ax, ay = (a[1] - lon) * kx, (a[0] - lat) * M_PER_DEG_LAT
    bx, by = (b[1] - lon) * kx, (b[0] - lat) * M_PER_DEG_LAT
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(ax + t * dx - px, ay + t * dy - py)


def in_zone(lat, lon, zone, buffer_m=0.0):
    if zone["shape"] == "circle":
        c = zone["center"]
        return haversine_m(lat, lon, c[0], c[1]) <= zone["radius_m"] + buffer_m
    pts = zone["points"]
    if point_in_polygon(lat, lon, pts):
        return True
    if buffer_m > 0:
        return any(_dist_to_segment_m(lat, lon, pts[i], pts[(i + 1) % len(pts)]) <= buffer_m
                   for i in range(len(pts)))
    return False


def in_any_zone(lat, lon, zones, buffer_m=0.0):
    return any(in_zone(lat, lon, z, buffer_m) for z in zones)


def zone_bbox(zone, buffer_m=0.0):
    """(lat_min, lon_min, lat_max, lon_max) incl. buffer."""
    if zone["shape"] == "circle":
        lat, lon = zone["center"]
        r = zone["radius_m"] + buffer_m
        dlat = r / M_PER_DEG_LAT
        dlon = r / (M_PER_DEG_LON * math.cos(math.radians(lat)))
        return lat - dlat, lon - dlon, lat + dlat, lon + dlon
    lats = [p[0] for p in zone["points"]]
    lons = [p[1] for p in zone["points"]]
    lat0 = sum(lats) / len(lats)
    return (min(lats) - buffer_m / M_PER_DEG_LAT, min(lons) - buffer_m / (M_PER_DEG_LON * math.cos(math.radians(lat0))),
            max(lats) + buffer_m / M_PER_DEG_LAT, max(lons) + buffer_m / (M_PER_DEG_LON * math.cos(math.radians(lat0))))


def segment_hits_zone(a, b, zone, buffer_m=0.0, step_m=30.0):
    length = haversine_m(a[0], a[1], b[0], b[1])
    n = max(1, int(length / step_m))
    for i in range(n + 1):
        t = i / n
        if in_zone(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, zone, buffer_m):
            return True
    return False


def segment_clear(a, b, zones, buffer_m=0.0, step_m=30.0):
    return not any(segment_hits_zone(a, b, z, buffer_m, step_m) for z in zones)


def route_hits_zones(points, zones, buffer_m=0.0):
    """IDs of zones intersected by a polyline."""
    hit = []
    for z in zones:
        for i in range(len(points) - 1):
            if segment_hits_zone(points[i], points[i + 1], z, buffer_m):
                hit.append(z["id"])
                break
    return hit


def validate_zone(d):
    """Normalise/validate a zone payload; raises ValueError."""
    shape = d.get("shape")
    z = {"name": (d.get("name") or "No-Fly Zone")[:60], "reason": (d.get("reason") or "")[:200], "shape": shape}

    def ok(lat, lon):
        return -90 <= lat <= 90 and -180 <= lon <= 180

    if shape == "circle":
        c, r = d.get("center"), d.get("radius_m")
        if not c or len(c) != 2 or r is None or not ok(c[0], c[1]):
            raise ValueError("Circle needs center [lat, lon] and radius_m")
        if not 50 <= r <= 10000:
            raise ValueError("radius_m must be between 50 and 10000")
        z.update(center=[float(c[0]), float(c[1])], radius_m=float(r))
    elif shape == "polygon":
        pts = d.get("points")
        if not pts or len(pts) < 3 or not all(len(p) == 2 and ok(p[0], p[1]) for p in pts):
            raise ValueError("Polygon needs at least 3 valid [lat, lon] points")
        z.update(points=[[float(p[0]), float(p[1])] for p in pts])
    else:
        raise ValueError("shape must be 'circle' or 'polygon'")
    return z
