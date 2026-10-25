"""Parametric tucked Pacific treefrog (Pseudacris regilla) for CFD.

The body is an implicit surface: a smooth union of ellipsoids (trunk, head,
eyes) and capsules (folded limbs). It is meshed by casting rays from the
body centre through an icosphere and finding the outermost surface crossing,
which gives a watertight, shrink-wrapped triangle mesh.

Frame: x = snout direction, y = left, z = dorsal. Model built in mm, written
in metres, scaled so snout-to-rear length = SVL.

Outputs (in ./geometry):
  frog_forward.stl   snout pointing -x  (flow is +x, so snout leads)
  frog_backward.stl  rotated 180 deg about z (rear leads)
  frog_props.json    volume, centroid, frontal area, length per orientation
  frog_views.png     three-view preview
"""
import json
import os

import numpy as np
from stl import mesh as stlmesh

SVL_MM = 40.0
BLEND_MM = 2.0  # smooth-union radius: legs pressed against the body
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "geometry")


def smin(a, b, k=BLEND_MM):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def ellipsoid(p, c, r):
    q = (p - c) / r
    return (np.linalg.norm(q, axis=-1) - 1.0) * r.min()


def capsule(p, a, b, ra, rb):
    pa, ba = p - a, b - a
    h = np.clip((pa @ ba) / (ba @ ba), 0.0, 1.0)
    return np.linalg.norm(pa - h[..., None] * ba, axis=-1) - (ra + (rb - ra) * h)


def head(p):
    c, r = np.array([11.0, 0.0, 0.5]), np.array([9.5, 7.2, 4.6])
    # Wedge-shaped head: narrows and flattens toward the rounded snout.
    s = np.clip((p[..., 0] - c[0]) / r[0], 0.0, 1.0)
    q = p.copy()
    q[..., 1] = q[..., 1] / (1 - 0.32 * s)
    q[..., 2] = (q[..., 2] - c[2]) / (1 - 0.22 * s) + c[2]
    return ellipsoid(q, c, r)


def frog_sdf(p):
    d = ellipsoid(p, np.array([-2.0, 0.0, 0.5]), np.array([13.5, 7.0, 5.5]))  # trunk
    d = smin(d, head(p))
    for sy in (1.0, -1.0):
        v = lambda x, y, z: np.array([x, sy * y, z])
        eye = np.linalg.norm(p - v(13.5, 4.6, 3.6), axis=-1) - 2.3
        thigh = capsule(p, v(-12.0, 4.5, -0.5), v(-1.5, 8.0, -1.5), 3.0, 2.4)
        shank = capsule(p, v(-1.5, 8.0, -1.5), v(-14.5, 8.3, -2.0), 2.3, 2.0)
        foot = capsule(p, v(-14.5, 7.5, -3.6), v(0.0, 8.5, -4.5), 1.3, 1.1)
        arm = capsule(p, v(7.0, 5.5, -2.5), v(12.0, 4.0, -4.5), 1.6, 1.3)
        for part, k in ((eye, 1.0), (thigh, BLEND_MM), (shank, BLEND_MM), (foot, 1.2), (arm, 1.2)):
            d = smin(d, part, k)
    return d


def icosphere(level):
    t = (1 + 5 ** 0.5) / 2
    v = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
         (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4),
         (11, 10, 2), (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8),
         (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    verts = [np.array(x, float) / np.linalg.norm(x) for x in v]
    faces = f
    for _ in range(level):
        cache, new = {}, []

        def mid(i, j):
            key = (min(i, j), max(i, j))
            if key not in cache:
                m = verts[i] + verts[j]
                verts.append(m / np.linalg.norm(m))
                cache[key] = len(verts) - 1
            return cache[key]

        for a, b, c in faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            new += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        faces = new
    return np.array(verts), np.array(faces)


def build_mesh(level=6, centre=(-1.0, 0.0, 0.0), tmax=30.0, dt=0.05):
    dirs, faces = icosphere(level)
    centre = np.array(centre)
    ts = np.arange(0.0, tmax, dt)
    radii = np.empty(len(dirs))
    for i in range(0, len(dirs), 2000):
        d = dirs[i:i + 2000]
        pts = centre + d[:, None, :] * ts[None, :, None]
        inside = frog_sdf(pts) < 0
        last = len(ts) - 1 - np.argmax(inside[:, ::-1], axis=1)  # outermost inside sample
        lo, hi = ts[last], ts[np.minimum(last + 1, len(ts) - 1)]
        for _ in range(30):  # bisect onto the surface
            m = 0.5 * (lo + hi)
            ins = frog_sdf(centre + d * m[:, None]) < 0
            lo, hi = np.where(ins, m, lo), np.where(ins, hi, m)
        radii[i:i + 2000] = 0.5 * (lo + hi)

    # Light Laplacian smoothing of radius removes stair-steps where the
    # outermost crossing jumps between a limb and the body.
    nbrs = [set() for _ in dirs]
    for a, b, c in faces:
        nbrs[a] |= {b, c}; nbrs[b] |= {a, c}; nbrs[c] |= {a, b}
    nbrs = [np.fromiter(n, int) for n in nbrs]
    for _ in range(3):
        radii = 0.5 * radii + 0.5 * np.array([radii[n].mean() for n in nbrs])
    return centre + dirs * radii[:, None], faces


def props(v, f):
    tri = v[f]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    vol6 = np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2]))
    vol = vol6.sum() / 6
    centroid = (vol6[:, None] * tri.sum(axis=1)).sum(axis=0) / (24 * vol)
    area = 0.5 * np.linalg.norm(cross, axis=1).sum()
    # Frontal (y-z projected) area by rasterising the silhouette.
    n = 1200
    ymin, ymax = v[:, 1].min(), v[:, 1].max()
    zmin, zmax = v[:, 2].min(), v[:, 2].max()
    gy, gz = np.meshgrid(np.linspace(ymin, ymax, n), np.linspace(zmin, zmax, n))
    pts = np.stack([np.zeros_like(gy), gy, gz], -1).reshape(-1, 3)
    hit = np.zeros(len(pts), bool)
    for x in np.linspace(v[:, 0].min(), v[:, 0].max(), 300):
        pts[:, 0] = x
        hit |= frog_sdf_scaled(pts) < 0
    frontal = hit.mean() * (ymax - ymin) * (zmax - zmin)
    return dict(volume=vol, centroid=centroid.tolist(), surface_area=area, frontal_area=frontal,
                length=float(np.ptp(v[:, 0])), width=float(np.ptp(v[:, 1])), height=float(np.ptp(v[:, 2])))


SCALE = 1.0  # set after first build


def frog_sdf_scaled(p_mm):
    return frog_sdf(p_mm / SCALE)


def write_stl(path, v, f, name):
    m = stlmesh.Mesh(np.zeros(len(f), dtype=stlmesh.Mesh.dtype))
    m.vectors = v[f]
    m.save(path)
    # numpy-stl writes a binary header; snappy needs only the file, region name via dict.


def main():
    global SCALE
    os.makedirs(OUT, exist_ok=True)
    v, f = build_mesh()
    SCALE = SVL_MM / np.ptp(v[:, 0])
    v = v * SCALE
    # Put the volume centroid at the origin so moments are about the CG.
    p = props(v, f)
    v = v - np.array(p["centroid"])
    p = props(v + np.array(p["centroid"]), f)  # frontal area via original frame
    p["centroid"] = [0.0, 0.0, 0.0]

    fwd = v.copy()
    fwd[:, 0] *= -1; fwd[:, 1] *= -1           # snout to -x: faces the +x flow
    bwd = v.copy()                              # snout to +x: rear faces the flow
    # Fix winding after the 180 deg rotation (proper rotation keeps winding).
    write_stl(os.path.join(OUT, "frog_forward.stl"), fwd / 1000, f, "frog")
    write_stl(os.path.join(OUT, "frog_backward.stl"), bwd / 1000, f, "frog")

    summary = {k: (val / 1e9 if k == "volume" else val / 1e6 if k.endswith("area") else
                   val / 1e3 if k in ("length", "width", "height") else val)
               for k, val in p.items()}
    summary["mass_g_at_1050kgm3"] = p["volume"] / 1000 * 1.05
    summary["n_triangles"] = int(len(f))
    summary["scale_factor"] = float(SCALE)
    with open(os.path.join(OUT, "frog_props.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps(summary, indent=2))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(13, 9))
    views = [("Top (snout right)", 90, -90), ("Side", 0, -90), ("Front (looking at snout)", 0, 0),
             ("3/4 view", 25, -55)]
    for i, (title, el, az) in enumerate(views):
        ax = fig.add_subplot(2, 2, i + 1, projection="3d")
        tri = v[f]
        nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
        shade = np.clip(nrm @ np.array([0.3, -0.5, 0.8]) / np.linalg.norm([0.3, -0.5, 0.8]), 0, 1)
        cols = np.c_[0.35 + 0.35 * shade, 0.55 + 0.4 * shade, 0.25 + 0.25 * shade, np.ones_like(shade)]
        ax.add_collection3d(Poly3DCollection(tri, facecolors=cols, edgecolor="none"))
        lim = 21
        ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_zlim(-lim, lim)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(el, az)
        ax.set_title(title)
        ax.set_axis_off()
    fig.suptitle(f"Parametric tucked P. regilla — L={p['length']:.1f} mm, W={p['width']:.1f} mm, "
                 f"H={p['height']:.1f} mm, V={p['volume']/1000:.2f} cm³")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "frog_views.png"), dpi=110)


if __name__ == "__main__":
    main()
