"""Write system/postSample into solver cases: mid-plane slices, frog surface
pressure, and a 3D grid of velocity samples for streamline tracing.

Usage: python post_dicts.py fwd_a0 bwd_a0 ...
Then (in the container): postProcess -case cfd/<case> -dict system/postSample -latestTime
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
CFD = os.path.join(ROOT, "cfd")

# 1.5 mm grid around the frog and its near wake.
gx = np.arange(-0.030, 0.1301, 0.0015)
gy = np.arange(-0.030, 0.0301, 0.0015)
gz = np.arange(-0.024, 0.0241, 0.0015)

DICT = """FoamFile { version 2.0; format ascii; class dictionary; object postSample; }
functions
{
slices
{
    type surfaces; libs (sampling);
    surfaceFormat raw;
    fields (U p);
    interpolationScheme cellPoint;
    surfaces
    {
        side { type cuttingPlane; point (0 0 0); normal (0 1 0); interpolate true;
               bounds (-0.04 -1 -0.035) (0.14 1 0.035); }
        top  { type cuttingPlane; point (0 0 0); normal (0 0 1); interpolate true;
               bounds (-0.04 -0.035 -1) (0.14 0.035 1); }
    }
}
frogSurface
{
    type surfaces; libs (sampling);
    surfaceFormat raw;
    fields (p);
    interpolationScheme cell;
    surfaces { frog { type patch; patches (frog); interpolate false; } }
}
grid
{
    type sets; libs (sampling);
    setFormat raw;
    fields (U);
    interpolationScheme cellPoint;
    sets { box { type cloud; axis xyz; points #include "gridPoints"; } }
}
}
"""

if __name__ == "__main__":
    X, Y, Z = np.meshgrid(gx, gy, gz, indexing="ij")
    pts = np.c_[X.ravel(), Y.ravel(), Z.ravel()]
    body = "(\n" + "\n".join(f"({x:.5f} {y:.5f} {z:.5f})" for x, y, z in pts) + "\n)\n"
    for c in sys.argv[1:]:
        with open(os.path.join(CFD, c, "system", "postSample"), "w") as fh:
            fh.write(DICT)
        with open(os.path.join(CFD, c, "system", "gridPoints"), "w") as fh:
            fh.write(body)
        print(c, len(pts), "grid points")
