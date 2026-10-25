"""Summarise frog CFD runs: force/moment coefficients averaged over the last
iterations, convergence plots, and implied terminal velocities.

Usage: python analyze.py fwd_a0 bwd_a0
"""
import glob
import json
import os
import sys

import numpy as np

from make_cases import CASES

ROOT = os.path.dirname(os.path.abspath(__file__))
CFD = os.path.join(ROOT, "cfd")
props = json.load(open(os.path.join(ROOT, "geometry", "frog_props.json")))
A, L = props["frontal_area"], props["length"]
RHO, U0, G = 1.2, 10.0, 9.81
Q = 0.5 * RHO * U0 ** 2
AVG = int(os.environ.get("AVG", 500))  # iterations averaged at the end


def load_dat(case, fo, name):
    files = sorted(glob.glob(os.path.join(CFD, case, "postProcessing", fo, "*", name)))
    rows = []
    for f in files:
        for line in open(f):
            if line.startswith("#") or not line.strip():
                continue
            rows.append([float(x) for x in line.replace("(", " ").replace(")", " ").split()])
    a = np.array(rows)
    # Keep the last entry per iteration (restarts can duplicate).
    _, idx = np.unique(a[:, 0][::-1], return_index=True)
    return a[::-1][idx]


def summarise(case):
    f = load_dat(case, "forces1", "force.dat")      # time, total(x y z), pressure(x y z), viscous(x y z)
    m = load_dat(case, "forces1", "moment.dat")
    n = min(len(f), len(m))
    f, m = f[:n], m[:n]
    tail = slice(max(0, n - AVG), n)
    U = U0 * np.array(CASES[case.split("_")[1][:2]])
    drag_dir = U / np.linalg.norm(U)
    Ft, Fp, Fv = f[:, 1:4], f[:, 4:7], f[:, 7:10]
    cd = Ft @ drag_dir / (Q * A)
    cd_p = Fp @ drag_dir / (Q * A)
    cd_v = Fv @ drag_dir / (Q * A)
    cz = Ft[:, 2] / (Q * A)
    cy = Ft[:, 1] / (Q * A)
    cmy = m[:, 2] / (Q * A * L)   # pitch moment about CG (+ = leading end up)
    cmz = m[:, 3] / (Q * A * L)   # yaw moment about CG
    r = lambda x: (float(x[tail].mean()), float(x[tail].std()))
    return dict(case=case, iters=int(f[-1, 0]), U=U.tolist(), Cd=r(cd), Cd_pressure=r(cd_p),
                Cd_viscous=r(cd_v), Cz=r(cz), Cy=r(cy), Cm_pitch=r(cmy), Cm_yaw=r(cmz),
                hist=dict(it=f[:, 0], cd=cd))


def main(cases):
    res = [summarise(c) for c in cases]
    print(f"Aref = {A*1e4:.3f} cm^2, Lref = {L*1e3:.1f} mm, U = {U0} m/s, "
          f"Re_L = {U0*L/1.5e-5:,.0f}; averages over last {AVG} iterations (± = std)\n")
    hdr = f"{'case':10s}{'iters':>6s}{'Cd':>16s}{'Cd_press':>10s}{'Cd_visc':>9s}{'Cz':>9s}{'Cy':>9s}{'Cm_pitch':>10s}{'Cm_yaw':>9s}"
    print(hdr)
    for r in res:
        print(f"{r['case']:10s}{r['iters']:6d}{r['Cd'][0]:10.4f}±{r['Cd'][1]:.4f}{r['Cd_pressure'][0]:10.4f}"
              f"{r['Cd_viscous'][0]:9.4f}{r['Cz'][0]:9.4f}{r['Cy'][0]:9.4f}{r['Cm_pitch'][0]:10.4f}{r['Cm_yaw'][0]:9.4f}")
    mass = props["mass_g_at_1050kgm3"] / 1000
    print(f"\nTerminal velocity if falling in this attitude (m = {mass*1e3:.1f} g model, and 4.0 g typical adult):")
    for r in res:
        cd = r["Cd"][0]
        vt = lambda m_: (2 * m_ * G / (RHO * cd * A)) ** 0.5
        print(f"  {r['case']:10s} {vt(mass):5.1f} m/s   {vt(0.004):5.1f} m/s")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for r in res:
        ax.plot(r["hist"]["it"], r["hist"]["cd"], label=r["case"], lw=1)
    ax.set_ylim(0, 1.2)
    ax.set_xlabel("SIMPLE iteration")
    ax.set_ylabel("C_d (frontal area)")
    ax.set_title("Drag coefficient convergence")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(CFD, "convergence.png"), dpi=110)
    json.dump([{k: v for k, v in r.items() if k != "hist"} for r in res],
              open(os.path.join(CFD, "summary.json"), "w"), indent=2)

    # Page data: coefficients plus a thinned Cd history.
    web = {"avg_iters": AVG, "U": U0, "Re": U0 * L / 1.5e-5, "props": props, "cases": {}}
    for r in res:
        h = r["hist"]
        keep = np.unique(np.r_[np.arange(0, len(h["it"]), 5), len(h["it"]) - 1])
        web["cases"][r["case"]] = {k: v for k, v in r.items() if k != "hist"}
        web["cases"][r["case"]]["hist"] = {"it": h["it"][keep].astype(int).tolist(),
                                           "cd": np.round(h["cd"][keep], 4).tolist()}
    os.makedirs(os.path.join(ROOT, "docs", "data"), exist_ok=True)
    out = os.path.join(ROOT, "docs", "data", "results.json")
    if os.path.exists(out):  # merge with cases analysed earlier (e.g. different AVG windows)
        old = json.load(open(out))
        old["cases"].update(web["cases"])
        web["cases"] = old["cases"]
        web["avg_iters"] = old.get("avg_iters", AVG) if not any(c.endswith("_a0") for c in cases) else AVG
    json.dump(web, open(out, "w"), separators=(",", ":"))


if __name__ == "__main__":
    main(sys.argv[1:])
