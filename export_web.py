"""Export CFD results for the report page (docs/data/*.json).

frog.json        indexed body-frame mesh (mm, snout toward +x) with Cp per
                 vertex for the forward and backward runs
streamlines.json 3D streamlines (body frame, mm) with arrival time and speed

Body frame: forward-run CFD coords are the body rotated 180 deg about z
(x,y negated); backward-run CFD coords equal body coords.
"""
import glob
import json
import os

import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.spatial import cKDTree
from stl import mesh as stlmesh

from post_dicts import gx, gy, gz

ROOT = os.path.dirname(os.path.abspath(__file__))
CFD = os.path.join(ROOT, "cfd")
OUT = os.path.join(ROOT, "docs", "data")
U0, RHO = 10.0, 1.2
FLIP = {"fwd": np.array([-1.0, -1.0, 1.0]), "bwd": np.array([1.0, 1.0, 1.0])}


def latest(case):
    times = [d for d in os.listdir(os.path.join(CFD, case, "postProcessing", "slices"))]
    return max(times, key=float)


def read_raw(path):
    return np.loadtxt(path, comments="#")


def find(case, fo, pattern):
    t = latest(case)
    hits = sorted(glob.glob(os.path.join(CFD, case, "postProcessing", fo, t, "**", pattern), recursive=True))
    if not hits:
        raise FileNotFoundError(f"{case}/{fo}/{t}/{pattern}")
    return hits[0]


def frog_mesh():
    m = stlmesh.Mesh.from_file(os.path.join(ROOT, "geometry", "frog_backward.stl"))  # body frame, metres
    v = m.vectors.reshape(-1, 3)
    uniq, inv = np.unique(np.round(v, 9), axis=0, return_inverse=True)
    return uniq, inv.reshape(-1, 3)


def surface_cp(case, verts_body):
    d = read_raw(find(case, "frogSurface", "*p*"))
    pts = d[:, :3] * FLIP[case[:3]]
    cp = d[:, 3] / (0.5 * U0 ** 2)  # kinematic p
    _, idx = cKDTree(pts).query(verts_body, k=4)
    return cp[idx].mean(axis=1)


def grid_velocity(case):
    d = read_raw(find(case, "grid", "*U*"))
    pts, U = d[:, :3], d[:, 3:6]
    shape = (len(gx), len(gy), len(gz))
    field = np.zeros(shape + (3,))
    ix = np.rint((pts[:, 0] - gx[0]) / 0.0015).astype(int)
    iy = np.rint((pts[:, 1] - gy[0]) / 0.0015).astype(int)
    iz = np.rint((pts[:, 2] - gz[0]) / 0.0015).astype(int)
    field[ix, iy, iz] = U  # points inside the frog stay at zero velocity
    return RegularGridInterpolator((gx, gy, gz), field, bounds_error=False, fill_value=np.nan)


def trace(interp, seeds, ds=0.0004, nmax=900):
    lines = []
    for s in seeds:
        p, t = s.copy(), 0.0
        pts, ts, sp = [p.copy()], [0.0], []
        for _ in range(nmax):
            def vel(q):
                u = interp(q[None])[0]
                return u
            u1 = vel(p)
            if not np.all(np.isfinite(u1)) or np.linalg.norm(u1) < 0.05:
                break
            # RK4 along the unit tangent; time accumulates ds/|U|.
            f = lambda q: (lambda u: u / np.linalg.norm(u) if np.all(np.isfinite(u)) and np.linalg.norm(u) > 1e-6 else None)(vel(q))
            k1 = f(p); k2 = f(p + 0.5 * ds * k1) if k1 is not None else None
            k3 = f(p + 0.5 * ds * k2) if k2 is not None else None
            k4 = f(p + ds * k3) if k3 is not None else None
            if k4 is None:
                break
            p = p + ds / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            t += ds / np.linalg.norm(u1)
            sp.append(np.linalg.norm(u1))
            pts.append(p.copy()); ts.append(t)
        sp.append(sp[-1] if sp else U0)
        if len(pts) > 20:
            lines.append((np.array(pts), np.array(ts), np.array(sp)))
    return lines


def streamlines(case):
    interp = grid_velocity(case)
    ys = np.linspace(-0.0135, 0.0135, 13)
    zs = np.linspace(-0.0075, 0.0085, 9)
    seeds = np.array([[-0.028, y, z] for y in ys for z in zs])
    out = []
    flip = FLIP[case[:3]]
    for pts, ts, sp in trace(interp, seeds):
        step = max(1, len(pts) // 160)
        sel = slice(None, None, step)
        out.append(dict(p=np.round(pts[sel] * flip * 1000, 2).ravel().tolist(),
                        t=np.round(ts[sel] * 1000, 3).tolist(),     # ms
                        s=np.round(sp[sel] / U0, 3).tolist()))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    verts, faces = frog_mesh()
    frog = dict(positions=np.round(verts * 1000, 2).ravel().tolist(), indices=faces.ravel().tolist())
    for case in ("fwd_a0", "bwd_a0"):
        frog["cp_" + case[:3]] = np.round(surface_cp(case, verts), 3).tolist()
    json.dump(frog, open(os.path.join(OUT, "frog.json"), "w"), separators=(",", ":"))
    sl = {case[:3]: streamlines(case) for case in ("fwd_a0", "bwd_a0")}
    json.dump(sl, open(os.path.join(OUT, "streamlines.json"), "w"), separators=(",", ":"))
    print("frog verts", len(verts), "streamlines", {k: len(v) for k, v in sl.items()})


if __name__ == "__main__":
    main()
