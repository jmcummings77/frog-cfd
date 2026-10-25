"""Split pressure drag into leading-half (forebody) and trailing-half (afterbody)
contributions by integrating surface pressure over the frog triangles.
Writes the split into docs/data/results.json."""
import json
import os

import numpy as np
from scipy.spatial import cKDTree
from stl import mesh as stlmesh

ROOT = os.path.dirname(os.path.abspath(__file__))
U0 = 10.0
res_path = os.path.join(ROOT, "docs", "data", "results.json")
res = json.load(open(res_path))
A = res["props"]["frontal_area"]
for case, stl in (("fwd_a0", "frog_forward.stl"), ("bwd_a0", "frog_backward.stl")):
    T = stlmesh.Mesh.from_file(os.path.join(ROOT, "geometry", stl)).vectors.astype(float)
    d = np.loadtxt(os.path.join(ROOT, "cfd", case, "postProcessing", "frogSurface", "1500", "p_frog.raw"), comments="#")
    c = T.mean(axis=1)
    _, idx = cKDTree(d[:, :3]).query(c, k=3)
    cp = d[idx, 3].mean(axis=1) / (0.5 * U0 ** 2)
    n_area = 0.5 * np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])   # outward normal * area
    fx = -cp * n_area[:, 0] / A                                       # drag contribution (Cd units)
    xmid = 0.5 * (T[..., 0].min() + T[..., 0].max())
    lead = c[:, 0] < xmid                                             # flow is +x, so leading half has smaller x
    out = dict(leading=float(fx[lead].sum()), trailing=float(fx[~lead].sum()), total=float(fx.sum()))
    res["cases"][case]["split"] = out
    print(case, {k: round(v, 4) for k, v in out.items()}, "| OpenFOAM pressure Cd", round(res["cases"][case]["Cd_pressure"][0], 4))
json.dump(res, open(res_path, "w"), separators=(",", ":"))
