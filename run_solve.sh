#!/bin/bash
# Usage (inside the OpenFOAM container): run_solve.sh cfd/fwd_a0 [cfd/bwd_a0 ...]
for c in "$@"; do
  (
  cd "$c" || exit 1
  decomposePar -force > log.decomposePar 2>&1
  mpirun --allow-run-as-root --oversubscribe -np 8 potentialFoam -parallel -writephi > log.potentialFoam 2>&1
  mpirun --allow-run-as-root --oversubscribe -np 8 simpleFoam -parallel > log.simpleFoam 2>&1
  reconstructPar -latestTime > log.reconstructPar 2>&1
  rm -rf processor*
  )
done
