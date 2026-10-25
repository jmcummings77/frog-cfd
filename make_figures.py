"""Static report figures from the sampled CFD output (docs/img/*.png).

All panels are drawn in the wind-tunnel frame: air moves left -> right.
"""
import glob
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from scipy.interpolate import griddata
from scipy.spatial import cKDTree
from stl import mesh as stlmesh

ROOT = os.path.dirname(os.path.abspath(__file__))
CFD = os.path.join(ROOT, "cfd")
IMG = os.path.join(ROOT, "docs", "img")
U0 = 10.0
STL = {"fwd": "frog_forward.stl", "bwd": "frog_backward.stl"}
TITLE = {"fwd": "Forwards: snout leading", "bwd": "Backwards: rear leading"}
FROG = "#6fbf4a"
SPEED = LinearSegmentedColormap.from_list("speed", ["#0d366b", "#1c5cab", "#3987e5", "#86b6ef", "#cde2fb", "#f7fafd"])
CP = LinearSegmentedColormap.from_list("cp", ["#184f95", "#5f9fea", "#e8e7e2", "#ec8383", "#b32b2b"])
plt.rcParams.update({"font.family": "sans-serif", "font.size": 10, "axes.edgecolor": "#bbbbb5",
                     "axes.labelcolor": "#52514e", "xtick.color": "#77766f", "ytick.color": "#77766f"})


def latest_dir(case, fo):
    base = os.path.join(CFD, case, "postProcessing", fo)
    t = max(os.listdir(base), key=float)
    return os.path.join(base, t)


def find(case, fo, *keys):
    files = glob.glob(os.path.join(latest_dir(case, fo), "**", "*"), recursive=True)
    hits = [f for f in files if os.path.isfile(f) and all(k in os.path.relpath(f, latest_dir(case, fo)) for k in keys)]
    if not hits:
        raise FileNotFoundError(f"{case} {fo} {keys}: {files}")
    return sorted(hits)[0]


def tris(case):
    return stlmesh.Mesh.from_file(os.path.join(ROOT, "geometry", STL[case])).vectors.astype(float)


def section(T, axis):
    """Segments where the frog surface crosses the plane coord[axis] = 0."""
    d = T[:, :, axis]
    segs = []
    for tri, dd in zip(T, d):
        if dd.min() > 0 or dd.max() < 0:
            continue
        pts = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            if (dd[i] > 0) != (dd[j] > 0):
                f = dd[i] / (dd[i] - dd[j])
                pts.append(tri[i] + f * (tri[j] - tri[i]))
        if len(pts) == 2:
            segs.append(pts)
    return np.array(segs)


def inside(px, py, segs2d):
    """Even-odd test of points against unordered 2D segments."""
    a, b = segs2d[:, 0], segs2d[:, 1]
    res = np.zeros(len(px), bool)
    for i in range(0, len(px), 20000):
        x, y = px[i:i + 20000, None], py[i:i + 20000, None]
        cond = (a[None, :, 1] > y) != (b[None, :, 1] > y)
        xint = a[None, :, 0] + (y - a[None, :, 1]) * (b[None, :, 0] - a[None, :, 0]) / (b[None, :, 1] - a[None, :, 1] + 1e-30)
        res[i:i + 20000] = (np.sum(cond & (x < xint), axis=1) % 2) == 1
    return res


def flow_figure(plane, cases=("fwd_a0", "bwd_a0")):
    ax_idx = {"side": (0, 2, 1), "top": (0, 1, 2)}[plane]  # (horizontal, vertical, normal)
    fig, axes = plt.subplots(len(cases), 1, figsize=(10, 3.9 * len(cases)), sharex=True, squeeze=False)
    axes = axes[:, 0]
    for ax, case in zip(axes, cases):
        d = np.loadtxt(find(case, "slices", plane, "U"), comments="#")
        h, v, n = ax_idx
        x, y = d[:, h] * 1000, d[:, v] * 1000
        U = d[:, 3:6]
        spd = np.linalg.norm(U, axis=1) / U0
        segs = section(tris(case[:3]), n)[:, :, [h, v]] * 1000
        tri = mtri.Triangulation(x, y)
        cx, cy = x[tri.triangles].mean(1), y[tri.triangles].mean(1)
        tri.set_mask(inside(cx, cy, segs))
        ax.set_facecolor(FROG)
        cf = ax.tricontourf(tri, spd, levels=np.linspace(0, 1.2, 25), cmap=SPEED, extend="max")
        # Recirculation: air moving upstream (against the free stream).
        ax.tricontour(tri, U[:, 0], levels=[0], colors="#e34948", linewidths=1.4)
        gxs, gys = np.linspace(-36, 96, 440), np.linspace(-30, 30, 200)
        GX, GY = np.meshgrid(gxs, gys)
        ua = griddata((x, y), U[:, h], (GX, GY), method="linear")
        va = griddata((x, y), U[:, v], (GX, GY), method="linear")
        body = inside(GX.ravel(), GY.ravel(), segs).reshape(GX.shape)
        ua[body] = np.nan; va[body] = np.nan
        ax.streamplot(gxs, gys, np.ma.masked_invalid(ua), np.ma.masked_invalid(va), density=(1.5, 1.1),
                      color=(0.1, 0.1, 0.1, 0.55), linewidth=0.5, arrowstyle="-", broken_streamlines=False)
        for s in segs:
            ax.plot(s[:, 0], s[:, 1], color="#2f5e1f", lw=0.8)
        ax.set_xlim(-32, 92); ax.set_ylim(-22, 22); ax.set_aspect("equal")
        ax.set_title(TITLE[case[:3]], loc="left", fontsize=11, fontweight="bold", color="#0b0b0b")
        ax.set_ylabel({"side": "height (mm)", "top": "across (mm)"}[plane])
    axes[-1].set_xlabel("distance downstream of the centre of mass (mm)   ·   air flows left → right at 10 m/s")
    cb = fig.colorbar(cf, ax=axes, shrink=0.85, pad=0.015)
    cb.set_label("speed / free-stream speed")
    cb.set_ticks([0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2])
    fig.savefig(os.path.join(IMG, f"flow_{plane}.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)


def cp_figure(cases=("fwd_a0", "bwd_a0")):
    fig = plt.figure(figsize=(12, 3.4 * len(cases)))
    views = [("top", 90, -90), ("side", 0, -90), ("3/4", 22, -125)]
    k = 1
    norm = TwoSlopeNorm(vmin=-1.0, vcenter=0.0, vmax=1.0)
    for case in cases:
        T = tris(case[:3])
        d = np.loadtxt(find(case, "frogSurface", "p"), comments="#")
        cp = d[:, 3] / (0.5 * U0 ** 2)
        _, idx = cKDTree(d[:, :3]).query(T.mean(axis=1), k=3)
        cpt = cp[idx].mean(1)
        cols = CP(norm(np.clip(cpt, -1, 1)))
        nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
        shade = 0.72 + 0.28 * np.clip(nrm @ np.array([0.2, -0.4, 0.9]) / 1.005, 0, 1)
        cols[:, :3] *= shade[:, None]
        for title, el, az in views:
            ax = fig.add_subplot(len(cases), 3, k, projection="3d"); k += 1
            ax.add_collection3d(Poly3DCollection(T * 1000, facecolors=cols, edgecolor="none"))
            cxm = 0.5 * (T[..., 0].min() + T[..., 0].max()) * 1000
            ax.set_xlim(cxm - 21, cxm + 21); ax.set_ylim(-21, 21); ax.set_zlim(-21, 21)
            ax.set_box_aspect((1, 1, 1), zoom=1.45); ax.view_init(el, az); ax.set_axis_off()
            ax.set_title(f"{TITLE[case[:3]]}\n{title} view" if title == "top" else f"{title} view", fontsize=10, loc="left")
    sm = plt.cm.ScalarMappable(norm=norm, cmap=CP)
    cb = fig.colorbar(sm, ax=fig.axes, shrink=0.6, pad=0.02)
    cb.set_label("pressure coefficient Cp  (blue = suction, red = pushed on)")
    fig.savefig(os.path.join(IMG, "cp_surface.png"), dpi=140, bbox_inches="tight")
    plt.close(fig)


def geometry_figure():
    T = tris("bwd") * 1000  # body frame: snout toward +x
    nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    shade = 0.55 + 0.45 * np.clip(nrm @ np.array([0.3, -0.5, 0.8]) / np.linalg.norm([0.3, -0.5, 0.8]), 0, 1)
    base = np.array([0.44, 0.75, 0.29])
    cols = np.c_[base[None, :] * shade[:, None], np.ones(len(T))]
    fig = plt.figure(figsize=(12, 3.6))
    for k, (title, el, az) in enumerate([("Top", 90, -90), ("Side", 0, -90), ("Front (snout)", 0, 0), ("Three-quarter", 24, -58)]):
        ax = fig.add_subplot(1, 4, k + 1, projection="3d")
        ax.add_collection3d(Poly3DCollection(T, facecolors=cols, edgecolor="none"))
        ax.set_xlim(-21, 21); ax.set_ylim(-21, 21); ax.set_zlim(-21, 21)
        ax.set_box_aspect((1, 1, 1), zoom=1.35); ax.view_init(el, az); ax.set_axis_off()
        ax.set_title(title, fontsize=10, color="#52514e")
    fig.subplots_adjust(left=0, right=1, top=0.92, bottom=0, wspace=0)
    fig.savefig(os.path.join(IMG, "frog_views.png"), dpi=140, bbox_inches="tight")
    plt.close(fig)


def main():
    os.makedirs(IMG, exist_ok=True)
    geometry_figure()
    for plane in ("side", "top"):
        flow_figure(plane)
        print("flow", plane)
    cp_figure()
    print("cp")


if __name__ == "__main__":
    main()
