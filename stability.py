"""Static stability from the 0 deg and 5 deg runs.

Frame: free stream along +x at 0 deg, leading end of the frog at -x, moments
about the volume centroid (taken as the centre of mass). Disturbances:
  pitch: U = (cos a, 0, sin a)  -> leading end raised by a
  yaw:   U = (cos b, sin b, 0)  -> leading end turned by b
Restoring (statically stable) if the moment change turns the leading end back
toward the direction of travel:
  pitch: dMy < 0,  yaw: dMz > 0.
Neutral point: where the incremental side/normal force acts along x,
  pitch: x_np = -dMy / dFz,  yaw: x_np = dMz / dFy   (x_np > 0: behind the CG).
Stable when x_np > 0 (the extra force acts behind the centre of mass, like a dart's flights).

Usage: python stability.py   (after analyze.py has been run on the a0 cases)
"""
import json
import math
import os

import numpy as np
from stl import mesh as stlmesh

import analyze

ROOT = os.path.dirname(os.path.abspath(__file__))
L = analyze.L
DEG = 5.0
MASS = 0.004  # kg, typical adult; inertia scaled from the uniform-density mesh
G, RHO = 9.81, 1.2


def inertia(stl):
    """Inertia tensor about the volume centroid (the STL origin) for MASS spread uniformly."""
    T = stlmesh.Mesh.from_file(os.path.join(ROOT, "geometry", stl)).vectors.astype(float)
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    vol = np.einsum("ij,ij->i", a, np.cross(b, c)) / 6
    s_ = a + b + c
    cov = sum(np.einsum("i,ij,ik->jk", vol / 20, v, v) for v in (a, b, c, s_))  # int x x^T dV
    cov *= MASS / vol.sum()
    return np.trace(cov) * np.eye(3) - cov


def coeffs(case, avg):
    analyze.AVG = avg
    return analyze.summarise(case)


def main():
    out = {}
    A = analyze.A
    for o, stl in (("fwd", "frog_forward.stl"), ("bwd", "frog_backward.stl")):
        a0 = coeffs(f"{o}_a0", 500)
        I = inertia(stl)
        vt = math.sqrt(2 * MASS * G / (RHO * a0["Cd"][0] * A))
        out[o] = {}
        for axis, case, m_key, f_key, sign in (("pitch", f"{o}_p5", "Cm_pitch", "Cz", -1.0),
                                               ("yaw", f"{o}_y5", "Cm_yaw", "Cy", 1.0)):
            d = coeffs(case, 300)
            dCm = d[m_key][0] - a0[m_key][0]
            dCf = d[f_key][0] - a0[f_key][0]
            x_np = (-dCm if axis == "pitch" else dCm) * L / dCf
            # Divergence: I theta'' = k theta, k = q A L |dCm/dtheta|; e-folding time tau = sqrt(I/k).
            Iax = I[1, 1] if axis == "pitch" else I[2, 2]
            slope = abs(dCm) / math.radians(DEG)
            tau = {u: math.sqrt(Iax / (0.5 * RHO * u ** 2 * A * L * slope)) for u in (10.0, vt)}
            out[o][axis] = dict(
                tau_ms_10=tau[10.0] * 1000, tau_ms_vt=tau[vt] * 1000, vt=vt,
                grow10x_cm_vt=vt * tau[vt] * math.log(10) * 100,
                inertia=Iax,
                restoring_per_deg=sign * dCm / DEG,      # > 0 restoring
                dCm=dCm, dCf=dCf, dCm_std=d[m_key][1],
                neutral_point_mm=x_np * 1000,             # > 0 behind the CG
                static_margin_pct=x_np / L * 100,
                Cd=d["Cd"][0],
            )
            print(f"{o} {axis:5s}: dCm={dCm:+.5f} (std {d[m_key][1]:.5f})  dC{f_key[1]}={dCf:+.4f}  "
                  f"restoring/deg={sign * dCm / DEG:+.5f}  neutral point {x_np * 1000:+.1f} mm "
                  f"({x_np / L * 100:+.0f}% L)  -> {'STABLE' if sign * dCm > 0 else 'unstable'}  "
                  f"tau {tau[10.0] * 1000:.0f} ms @10 m/s, {tau[vt] * 1000:.0f} ms @{vt:.1f} m/s; 10x growth in {vt * tau[vt] * math.log(10) * 100:.0f} cm")
    path = os.path.join(ROOT, "docs", "data", "results.json")
    res = json.load(open(path))
    res["stability"] = out
    json.dump(res, open(path, "w"), separators=(",", ":"))


if __name__ == "__main__":
    main()
