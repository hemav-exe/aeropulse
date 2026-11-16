"""navigation.py - A* path planning on a geo-referenced grid with no-fly-zone avoidance."""
import heapq
import math
from geofencing import (haversine_m, in_any_zone, in_zone, zone_bbox, segment_clear,
                        M_PER_DEG_LAT, M_PER_DEG_LON)

BOUNDS = (12.930, 77.535, 13.015, 77.665)   # lat_min, lon_min, lat_max, lon_max (operating area)
CELL_M = 120.0
BUFFER_M = 70.0                              # safety margin around zones
_cache = {}


class Grid:
    def __init__(self, bounds=BOUNDS, cell_m=CELL_M):
        self.lat0, self.lon0, self.lat1, self.lon1 = bounds
        self.mlat = M_PER_DEG_LAT
        self.mlon = M_PER_DEG_LON * math.cos(math.radians((self.lat0 + self.lat1) / 2))
        self.cell = cell_m
        self.ny = int((self.lat1 - self.lat0) * self.mlat / cell_m) + 1
        self.nx = int((self.lon1 - self.lon0) * self.mlon / cell_m) + 1

    def cell_of(self, lat, lon):
        j = int((lat - self.lat0) * self.mlat / self.cell)
        i = int((lon - self.lon0) * self.mlon / self.cell)
        return max(0, min(self.nx - 1, i)), max(0, min(self.ny - 1, j))

    def center(self, i, j):
        return (self.lat0 + (j + 0.5) * self.cell / self.mlat, self.lon0 + (i + 0.5) * self.cell / self.mlon)

    def blocked_cells(self, zones, buffer_m):
        blocked = set()
        for z in zones:
            la0, lo0, la1, lo1 = zone_bbox(z, buffer_m)
            i0, j0 = self.cell_of(la0, lo0)
            i1, j1 = self.cell_of(la1, lo1)
            for i in range(i0, i1 + 1):
                for j in range(j0, j1 + 1):
                    c = self.center(i, j)
                    if in_zone(c[0], c[1], z, buffer_m):
                        blocked.add((i, j))
        return blocked


def _blocked(zones, buffer_m):
    key = (tuple((z["id"], z.get("rev", 0)) for z in zones), buffer_m)
    if key not in _cache:
        if len(_cache) > 20:
            _cache.clear()
        g = Grid()
        _cache[key] = (g, g.blocked_cells(zones, buffer_m))
    return _cache[key]


def _smooth(pts, zones, buffer_m):
    out, i = [pts[0]], 0
    while i < len(pts) - 1:
        j = len(pts) - 1
        while j > i + 1 and not segment_clear(pts[i], pts[j], zones, buffer_m, 40.0):
            j -= 1
        out.append(pts[j])
        i = j
    return out


def astar(start, goal, zones, buffer_m=BUFFER_M):
    """A* (8-connected, octile heuristic). Returns [(lat, lon), ...] or None if no safe route exists."""
    g, blocked = _blocked(zones, buffer_m)
    s, e = g.cell_of(*start), g.cell_of(*goal)
    if e in blocked:                                     # snap goal to nearest free cell
        e = next(((e[0] + di, e[1] + dj) for r in range(1, 25) for di in range(-r, r + 1) for dj in range(-r, r + 1)
                  if max(abs(di), abs(dj)) == r and 0 <= e[0] + di < g.nx and 0 <= e[1] + dj < g.ny
                  and (e[0] + di, e[1] + dj) not in blocked), None)
        if e is None:
            return None
    SQ2 = math.sqrt(2)

    def h(c):
        dx, dy = abs(c[0] - e[0]), abs(c[1] - e[1])
        return (dx + dy) + (SQ2 - 2) * min(dx, dy)

    openq, came, gs, n = [(h(s), 0, s)], {}, {s: 0.0}, 0
    closed = set()
    while openq:
        _, _, cur = heapq.heappop(openq)
        if cur == e:
            break
        if cur in closed:
            continue
        closed.add(cur)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di == dj == 0:
                    continue
                nb = (cur[0] + di, cur[1] + dj)
                if not (0 <= nb[0] < g.nx and 0 <= nb[1] < g.ny) or nb in blocked or nb in closed:
                    continue
                if di and dj and ((cur[0] + di, cur[1]) in blocked or (cur[0], cur[1] + dj) in blocked):
                    continue                              # no corner cutting
                ng = gs[cur] + (SQ2 if di and dj else 1.0)
                if ng < gs.get(nb, 1e18):
                    gs[nb], came[nb] = ng, cur
                    n += 1
                    heapq.heappush(openq, (ng + h(nb), n, nb))
    else:
        return None
    if e not in came and e != s:
        return None
    cells = [e]
    while cells[-1] != s:
        cells.append(came[cells[-1]])
    cells.reverse()
    pts = [tuple(start)] + [g.center(*c) for c in cells[1:-1]]
    pts.append(tuple(goal) if not in_any_zone(goal[0], goal[1], zones, 0) else g.center(*cells[-1]))
    return _smooth(pts, zones, buffer_m)


def plan_route(points, zones, buffer_m=BUFFER_M):
    """Route through waypoints. Straight segments are kept when clear; otherwise A* detours are inserted."""
    route = [tuple(points[0])]
    for a, b in zip(points, points[1:]):
        if segment_clear(a, b, zones, buffer_m):
            route.append(tuple(b))
        else:
            leg = astar(a, b, zones, buffer_m)
            if leg is None:
                return None
            route.extend(leg[1:])
    return route


def route_length_m(points):
    return sum(haversine_m(a[0], a[1], b[0], b[1]) for a, b in zip(points, points[1:]))


def sample_route(points, step_m=100.0):
    """Yield (distance_from_start_m, lat, lon) along a polyline."""
    d = 0.0
    yield 0.0, points[0][0], points[0][1]
    for a, b in zip(points, points[1:]):
        L = haversine_m(a[0], a[1], b[0], b[1])
        k = int(L // step_m)
        for i in range(1, k + 1):
            t = i * step_m / L
            yield d + i * step_m, a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        d += L


def sweep_waypoints(bounds, spacing_m=600.0, inset_m=150.0):
    """Lawn-mower (boustrophedon) coverage path over a region; lanes run north-south."""
    lat0, lon0, lat1, lon1 = bounds
    mlon = M_PER_DEG_LON * math.cos(math.radians((lat0 + lat1) / 2))
    width = (lon1 - lon0) * mlon
    first = min(300.0, width / 2)
    n = max(1, math.ceil((width - 2 * first) / spacing_m) + 1)
    step = (width - 2 * first) / (n - 1) if n > 1 else 0
    south, north = lat0 + inset_m / M_PER_DEG_LAT, lat1 - inset_m / M_PER_DEG_LAT
    pts = []
    for k in range(n):
        lon = lon0 + (first + k * step) / mlon
        pts += [(south, lon), (north, lon)] if k % 2 == 0 else [(north, lon), (south, lon)]
    return pts
