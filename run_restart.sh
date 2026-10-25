#!/bin/bash
# Usage (inside the OpenFOAM container): run_restart.sh cfd/fwd_p5 [cfd/bwd_p5 ...]
for c in "$@"; do
  (
  cd "$c" || exit 1
  decomposePar -force > log.decomposePar 2>&1
  # Restarted from the converged 0-degree fields: no potentialFoam initialisation.
  mpirun --allow-run-as-root --oversubscribe -np 8 simpleFoam -parallel > log.simpleFoam 2>&1
  reconstructPar -latestTime > log.reconstructPar 2>&1
  rm -rf processor*
  )
done
