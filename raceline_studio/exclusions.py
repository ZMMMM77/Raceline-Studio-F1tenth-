"""User exclusion polygons in world metres; original maps remain immutable."""
import hashlib
import json
import os
import threading
import uuid
from pathlib import Path

import numpy as np
from matplotlib.path import Path as PolygonPath
from .planner import PlanningError


def validate_zones(value):
    if not isinstance(value, list) or len(value) > 20:
        raise PlanningError('禁行区最多 20 个，每个区域需要 3–64 个顶点。')
    zones = []
    for points in value:
        try:
            p = np.asarray(points, dtype=float)
        except (ValueError, TypeError):
            raise PlanningError('禁行区顶点需要有效的地图坐标。') from None
        if (p.ndim != 2 or p.shape[1] != 2 or not 3 <= len(p) <= 64
                or not np.isfinite(p).all() or np.max(abs(p)) > 1e6):
            raise PlanningError('禁行区最多 20 个，每个区域需要 3–64 个有效地图坐标。')
        # Reject repeated vertices, touching nonadjacent edges and collinear overlaps.
        if np.min(np.linalg.norm(p[:, None] - p[None, :] + np.eye(len(p))[:, :, None] * 1e9, axis=2)) < 1e-7:
            raise PlanningError('禁行区不能重复顶点或自交，请重新圈选。')
        cross = lambda a, b: a[0] * b[1] - a[1] * b[0]
        def intersects(a, b, c, d):
            if np.any(np.maximum(np.minimum(a, b), np.minimum(c, d)) > np.minimum(np.maximum(a, b), np.maximum(c, d)) + 1e-9):
                return False
            return (cross(b-a, c-a)*cross(b-a, d-a) <= 1e-12
                    and cross(d-c, a-c)*cross(d-c, b-c) <= 1e-12)
        for i in range(len(p)):
            for j in range(i+1, len(p)):
                if j == i+1 or (i == 0 and j == len(p)-1):
                    continue
                if intersects(p[i], p[(i+1) % len(p)], p[j], p[(j+1) % len(p)]):
                    raise PlanningError('禁行区不能重复顶点或自交，请重新圈选。')
        area = sum(cross(p[i], p[(i+1) % len(p)]) for i in range(len(p))) / 2
        if abs(area) < 1e-6:
            raise PlanningError('禁行区面积太小，请重新圈选。')
        zones.append(p.tolist())
    return zones


class ExclusionField:
    """Exact distance to polygon edges, positive outside the forbidden union.

    The minimum of individual signed distances is conservative for overlapping
    polygons. At nondifferentiable ties one valid edge gradient is returned.
    """
    def __init__(self, zones):
        self.zones = validate_zones(zones)
        self.polygons = []
        for points in self.zones:
            p = np.asarray(points)
            edges = np.roll(p, -1, axis=0) - p
            orientation = np.sign(np.sum(p[:, 0]*np.roll(p[:, 1], -1) - p[:, 1]*np.roll(p[:, 0], -1)))
            outward = orientation * np.c_[edges[:, 1], -edges[:, 0]] / np.linalg.norm(edges, axis=1)[:, None]
            self.polygons.append((p, edges, outward, PolygonPath(np.vstack([p, p[0]]))))

    def distance(self, points, gradient=False):
        p = np.asarray(points, dtype=float)
        values = np.full(len(p), np.inf)
        grads = np.zeros_like(p)
        for vertices, edges, outward, path in self.polygons:
            # Chunked to bound memory for dense trajectory validation.
            for start in range(0, len(p), 4096):
                q = p[start:start+4096]
                delta = q[:, None] - vertices
                t = np.clip(np.sum(delta*edges, axis=2)/np.sum(edges*edges, axis=1), 0, 1)
                residual = delta-t[:, :, None]*edges
                distances = np.linalg.norm(residual, axis=2)
                ids = np.argmin(distances, axis=1); rows = np.arange(len(q))
                d = distances[rows, ids]
                sign = np.where(path.contains_points(q), -1., 1.)
                signed = d*sign
                grad = sign[:, None]*residual[rows, ids]/np.maximum(d[:, None], 1e-12)
                grad[d < 1e-10] = outward[ids[d < 1e-10]]
                sl = slice(start, start+len(q)); replace = signed < values[sl]
                values[sl] = np.where(replace, signed, values[sl])
                grads[sl] = np.where(replace[:, None], grad, grads[sl])
        return (values, grads) if gradient else values


def track_key(center, widths, map_data):
    """Content identity, never a filename: map coordinates/occupancy must match."""
    h = hashlib.sha256()
    if map_data is not None:
        h.update(b'map-v1')
        h.update(np.asarray(map_data.image).tobytes())
        h.update(np.asarray(map_data.free, dtype=np.uint8).tobytes())
        h.update(np.asarray([*map_data.image.size, map_data.resolution, *map_data.origin], dtype='<f8').tobytes())
    else:
        h.update(b'csv-corridor-v1')
        h.update(np.round(np.column_stack([center, widths]), 6).astype('<f8').tobytes())
    return h.hexdigest()


class ExclusionConflict(PlanningError):
    pass


class ExclusionStore:
    def __init__(self, root):
        self.root = Path(root)
        self.lock = threading.RLock()

    def _config(self, key, zones):
        zones = validate_zones(zones)
        revision = hashlib.sha256(json.dumps(zones, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        return dict(key=key, revision=revision, zones=zones)

    def load(self, key):
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise PlanningError('无效的禁行区地图标识。')
        with self.lock:
            path = self.root / (key+'.json')
            if not path.exists():
                return self._config(key, [])
            try:
                return self._config(key, json.loads(path.read_text(encoding='utf-8'))['zones'])
            except (OSError, ValueError, KeyError, TypeError, PlanningError):
                raise PlanningError('已保存的禁行区无法读取，请检查本地规划设置。') from None

    def save(self, key, zones, revision):
        with self.lock:
            current = self.load(key)
            if revision != current['revision']:
                raise ExclusionConflict('禁行区已在其他窗口更改，请重新载入后再编辑。')
            config = self._config(key, zones)
            self.root.mkdir(parents=True, exist_ok=True)
            path = self.root / (key+'.json')
            temp = self.root / (key+'.'+uuid.uuid4().hex+'.tmp')
            try:
                temp.write_text(json.dumps(config, ensure_ascii=False, allow_nan=False), encoding='utf-8')
                os.replace(temp, path)
            finally:
                temp.unlink(missing_ok=True)
            return config
