# frog-cfd

**Does a Pacific treefrog fly faster forwards or backwards?**

This is a 3D CFD study of a tucked, 40 mm *Pseudacris regilla*: steady RANS (k-ω SST) in OpenFOAM v2412 at 10 m/s (Re ≈ 27,000), flown snout first and rear first.

📄 **Report with interactive 3D flow visualisation:** https://jmcummings77.github.io/frog-cfd/

## Layout

| Path | What |
|---|---|
| `frog_geometry.py` | Parametric tucked-frog surface (implicit blend of ellipsoids and capsules), written as STL |
| `geometry/` | Frog STLs (forward and backward orientation), properties, preview |
| `make_cases.py` | Writes OpenFOAM mesh and solver cases (blockMesh, snappyHexMesh, simpleFoam) |
| `run_mesh.sh`, `run_solve.sh` | Run inside the OpenFOAM container via `docker_of.sh` |
| `post_dicts.py` | Sampling dictionaries: slices, surface pressure, 3D velocity grid |
| `analyze.py` | Force and moment coefficients, convergence, terminal velocities |
| `make_figures.py`, `export_web.py` | Report figures and web data |
| `cfd/<case>/` | Case setups (`0/`, `constant/`, `system/`), logs and `postProcessing/` force histories and samples |
| `docs/` | The GitHub Pages report |

Meshes and full field outputs (about 1 GB) aren't committed. The run scripts regenerate them.

## Reproduce

Requirements: Docker (image `opencfd/openfoam-run:2412`) and Python 3 with `numpy scipy matplotlib numpy-stl`.

```bash
python frog_geometry.py
python make_cases.py --mesh-only
./docker_of.sh ./run_mesh.sh cfd/mesh_forward
./docker_of.sh ./run_mesh.sh cfd/mesh_backward
python make_cases.py fwd_a0 bwd_a0
./docker_of.sh ./run_solve.sh cfd/fwd_a0 cfd/bwd_a0
python post_dicts.py fwd_a0 bwd_a0
./docker_of.sh 'for c in fwd_a0 bwd_a0; do postProcess -case cfd/$c -dict system/postSample -latestTime; done'
python analyze.py fwd_a0 bwd_a0
python make_figures.py
python export_web.py
```

## Caveats

The frog is parametric, not scanned. RANS with a fully turbulent model is a simplification at this Reynolds number, where real boundary layers are partly laminar. See the report's caveats section.
