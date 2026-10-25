"""Write OpenFOAM (v2412) cases for the frog: one mesh per orientation,
one solver case per (orientation, inflow angle).

Flow always enters at x-min. The leading end of the frog sits at -x.
Inflow angles rotate the freestream instead of the body:
  pitch a: U = U0 (cos a, 0, sin a)   -> leading end effectively raised by a
  yaw   b: U = U0 (cos b, sin b, 0)

Usage: python make_cases.py [--surface-level N] [--tag NAME] case_name ...
Case names: fwd_a0 bwd_a0 (fwd/bwd_p5, _y5 = 5 deg pitch/yaw variants)
"""
import argparse
import json
import math
import os
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
GEOM = os.path.join(ROOT, "geometry")
CFD = os.path.join(ROOT, "cfd")

U0 = 10.0
NU = 1.5e-5
RHO = 1.2
props = json.load(open(os.path.join(GEOM, "frog_props.json")))
AREF = props["frontal_area"]
LREF = props["length"]

HEADER = """FoamFile
{{
    version     2.0;
    format      ascii;
    class       {cls};
    object      {obj};
}}
"""


def write(path, cls, obj, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(HEADER.format(cls=cls, obj=obj) + body)


def mesh_case(orient, surface_level, tag):
    d = os.path.join(CFD, f"mesh_{orient}{tag}")
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.join(d, "constant", "triSurface"))
    shutil.copy(os.path.join(GEOM, f"frog_{orient}.stl"), os.path.join(d, "constant", "triSurface", "frog.stl"))
    common_system(d, end_time=0)
    # Base cells 8 mm; domain 6L upstream, 12L downstream, +-4L laterally.
    write(f"{d}/system/blockMeshDict", "dictionary", "blockMeshDict", """
scale 1;
vertices
(
    (-0.24 -0.16 -0.16) (0.48 -0.16 -0.16) (0.48 0.16 -0.16) (-0.24 0.16 -0.16)
    (-0.24 -0.16  0.16) (0.48 -0.16  0.16) (0.48 0.16  0.16) (-0.24 0.16  0.16)
);
blocks ( hex (0 1 2 3 4 5 6 7) (90 40 40) simpleGrading (1 1 1) );
boundary
(
    inlet  { type patch; faces ((0 4 7 3)); }
    outlet { type patch; faces ((1 2 6 5)); }
    sides  { type patch; faces ((0 1 5 4) (3 7 6 2) (0 3 2 1) (4 5 6 7)); }
);
""")
    s = surface_level
    write(f"{d}/system/snappyHexMeshDict", "dictionary", "snappyHexMeshDict", f"""
castellatedMesh true;
snap            true;
addLayers       true;

geometry
{{
    frog.stl {{ type triSurfaceMesh; name frog; }}
    near {{ type searchableBox; min (-0.035 -0.024 -0.022); max (0.10 0.024 0.022); }}
    wake {{ type searchableBox; min (-0.06 -0.045 -0.045); max (0.26 0.045 0.045); }}
}}

castellatedMeshControls
{{
    maxLocalCells 4000000;
    maxGlobalCells 12000000;
    minRefinementCells 10;
    maxLoadUnbalance 0.10;
    nCellsBetweenLevels 3;
    features ();
    refinementSurfaces {{ frog {{ level ({s} {s}); patchInfo {{ type wall; }} }} }}
    resolveFeatureAngle 30;
    refinementRegions
    {{
        near {{ mode inside; levels ((1E15 3)); }}
        wake {{ mode inside; levels ((1E15 2)); }}
    }}
    locationInMesh (0.3013 0.1017 0.1031);
    allowFreeStandingZoneFaces true;
}}

snapControls
{{
    nSmoothPatch 3;
    tolerance 2.0;
    nSolveIter 50;
    nRelaxIter 5;
    nFeatureSnapIter 0;
    implicitFeatureSnap false;
    explicitFeatureSnap false;
    multiRegionFeatureSnap false;
}}

addLayersControls
{{
    relativeSizes true;
    layers {{ frog {{ nSurfaceLayers 3; }} }}
    expansionRatio 1.2;
    finalLayerThickness 0.5;
    minThickness 0.1;
    nGrow 0;
    featureAngle 120;
    slipFeatureAngle 30;
    nRelaxIter 3;
    nSmoothSurfaceNormals 1;
    nSmoothNormals 3;
    nSmoothThickness 10;
    maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3;
    minMedialAxisAngle 90;
    nBufferCellsNoExtrude 0;
    nLayerIter 50;
}}

meshQualityControls
{{
    maxNonOrtho 65;
    maxBoundarySkewness 20;
    maxInternalSkewness 4;
    maxConcave 80;
    minVol 1e-13;
    minTetQuality 1e-15;
    minArea -1;
    minTwist 0.02;
    minDeterminant 0.001;
    minFaceWeight 0.05;
    minVolRatio 0.01;
    minTriangleTwist -1;
    nSmoothScale 4;
    errorReduction 0.75;
    relaxed {{ maxNonOrtho 75; }}
}}

mergeTolerance 1e-6;
""")
    return d


def common_system(d, end_time, U=None, write_interval=500):
    write(f"{d}/system/decomposeParDict", "dictionary", "decomposeParDict", """
numberOfSubdomains 8;
method scotch;
""")
    fo = ""
    if U is not None:
        ux, uy, uz = U
        mag = math.sqrt(ux * ux + uy * uy + uz * uz)
        drag = f"({ux/mag:.8f} {uy/mag:.8f} {uz/mag:.8f})"
        # Lift is perpendicular to drag in the x-z plane (pitch) or z for yaw runs.
        lift = f"({-uz/mag:.8f} 0 {ux/mag:.8f})" if abs(uy) < 1e-12 else "(0 0 1)"
        fo = f"""
functions
{{
    forces1
    {{
        type forces; libs (forces);
        writeControl timeStep; writeInterval 1;
        patches (frog);
        rho rhoInf; rhoInf {RHO};
        CofR (0 0 0);
    }}
    forceCoeffs1
    {{
        type forceCoeffs; libs (forces);
        writeControl timeStep; writeInterval 1;
        patches (frog);
        rho rhoInf; rhoInf {RHO};
        CofR (0 0 0);
        dragDir {drag};
        liftDir {lift};
        pitchAxis (0 1 0);
        magUInf {U0};
        lRef {LREF};
        Aref {AREF};
    }}
    yPlus1
    {{
        type yPlus; libs (fieldFunctionObjects);
        writeControl writeTime;
    }}
}}
"""
    write(f"{d}/system/controlDict", "dictionary", "controlDict", f"""
application simpleFoam;
startFrom latestTime;
startTime 0;
stopAt endTime;
endTime {end_time};
deltaT 1;
writeControl timeStep;
writeInterval {write_interval};
purgeWrite 2;
writeFormat binary;
writePrecision 8;
timeFormat general;
runTimeModifiable true;
{fo}
""")
    write(f"{d}/system/fvSchemes", "dictionary", "fvSchemes", """
ddtSchemes { default steadyState; }
gradSchemes
{
    default Gauss linear;
    grad(U) cellLimited Gauss linear 1;
    grad(k) cellLimited Gauss linear 1;
    grad(omega) cellLimited Gauss linear 1;
}
divSchemes
{
    default none;
    div(phi,U) bounded Gauss linearUpwind grad(U);
    div(phi,k) bounded Gauss limitedLinear 1;
    div(phi,omega) bounded Gauss limitedLinear 1;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear limited corrected 0.5; }
interpolationSchemes { default linear; }
snGradSchemes { default limited corrected 0.5; }
wallDist { method meshWave; }
""")
    write(f"{d}/system/fvSolution", "dictionary", "fvSolution", """
solvers
{
    p { solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.05; }
    Phi { $p; }
    "(U|k|omega)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0.1; }
}
SIMPLE
{
    nNonOrthogonalCorrectors 1;
    consistent no;
    residualControl { p 1e-5; U 1e-6; "(k|omega)" 1e-6; }
}
potentialFlow { nNonOrthogonalCorrectors 5; }
relaxationFactors
{
    fields { p 0.3; }
    equations { U 0.7; "(k|omega)" 0.7; }
}
""")


def solver_case(name, mesh_dir, U, iters):
    d = os.path.join(CFD, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.join(d, "constant"))
    shutil.copytree(os.path.join(mesh_dir, "constant", "polyMesh"), os.path.join(d, "constant", "polyMesh"))
    common_system(d, end_time=iters, U=U)
    write(f"{d}/constant/transportProperties", "dictionary", "transportProperties",
          f"transportModel Newtonian;\nnu {NU};\n")
    write(f"{d}/constant/turbulenceProperties", "dictionary", "turbulenceProperties",
          "simulationType RAS;\nRAS { RASModel kOmegaSST; turbulence on; printCoeffs on; }\n")
    # 0.5% freestream turbulence, eddy-viscosity ratio 1.
    k = 1.5 * (0.005 * U0) ** 2
    om = k / NU
    ustr = f"({U[0]:.8f} {U[1]:.8f} {U[2]:.8f})"
    # Inflow on x-min; with yaw/pitch the sides see inflow too, so use inletOutlet-type freestream.
    bc = {
        "U": ("volVectorField", f"uniform {ustr}",
              f"inlet {{ type fixedValue; value uniform {ustr}; }}\n"
              f"    outlet {{ type inletOutlet; inletValue uniform (0 0 0); value uniform {ustr}; }}\n"
              f"    sides {{ type freestreamVelocity; freestreamValue uniform {ustr}; }}\n"
              f"    frog {{ type noSlip; }}"),
        "p": ("volScalarField", "uniform 0",
              "inlet { type zeroGradient; }\n"
              "    outlet { type fixedValue; value uniform 0; }\n"
              "    sides { type freestreamPressure; freestreamValue uniform 0; }\n"
              "    frog { type zeroGradient; }"),
        "k": ("volScalarField", f"uniform {k}",
              f"inlet {{ type fixedValue; value uniform {k}; }}\n"
              f"    \"(outlet|sides)\" {{ type inletOutlet; inletValue uniform {k}; value uniform {k}; }}\n"
              f"    frog {{ type kqRWallFunction; value uniform {k}; }}"),
        "omega": ("volScalarField", f"uniform {om}",
                  f"inlet {{ type fixedValue; value uniform {om}; }}\n"
                  f"    \"(outlet|sides)\" {{ type inletOutlet; inletValue uniform {om}; value uniform {om}; }}\n"
                  f"    frog {{ type omegaWallFunction; value uniform {om}; }}"),
        "nut": ("volScalarField", "uniform 0",
                "\"(inlet|outlet|sides)\" { type calculated; value uniform 0; }\n"
                "    frog { type nutUSpaldingWallFunction; value uniform 0; }"),
    }
    dims = {"U": "[0 1 -1 0 0 0 0]", "p": "[0 2 -2 0 0 0 0]", "k": "[0 2 -2 0 0 0 0]",
            "omega": "[0 0 -1 0 0 0 0]", "nut": "[0 2 -1 0 0 0 0]"}
    for f, (cls, internal, patches) in bc.items():
        write(f"{d}/0/{f}", cls, f, f"""
dimensions {dims[f]};
internalField {internal};
boundaryField
{{
    {patches}
}}
""")
    return d


CASES = {
    "a0": (1.0, 0.0, 0.0),
    "p5": (math.cos(math.radians(5)), 0.0, math.sin(math.radians(5))),
    "y5": (math.cos(math.radians(5)), math.sin(math.radians(5)), 0.0),
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--surface-level", type=int, default=5)
    ap.add_argument("--tag", default="")
    ap.add_argument("--iters", type=int, default=2000)
    ap.add_argument("--mesh-only", action="store_true")
    ap.add_argument("cases", nargs="*")
    a = ap.parse_args()
    if a.mesh_only:
        for o in ("forward", "backward"):
            print(mesh_case(o, a.surface_level, a.tag))
    for c in a.cases:
        orient = {"fwd": "forward", "bwd": "backward"}[c[:3]]
        U = tuple(U0 * x for x in CASES[c[4:]])
        print(solver_case(c + a.tag, os.path.join(CFD, f"mesh_{orient}{a.tag}"), U, a.iters))
