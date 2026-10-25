#!/bin/bash
# Usage (inside the OpenFOAM container): run_mesh.sh cfd/mesh_forward
set -e
cd "$1"
surfaceCheck constant/triSurface/frog.stl > log.surfaceCheck 2>&1 || true
blockMesh > log.blockMesh 2>&1
decomposePar -force > log.decomposePar 2>&1
mpirun --allow-run-as-root --oversubscribe -np 8 snappyHexMesh -parallel -overwrite > log.snappyHexMesh 2>&1
reconstructParMesh -constant > log.reconstructParMesh 2>&1
rm -rf processor*
checkMesh -constant > log.checkMesh 2>&1 || true
