#!/bin/bash
# Run a command inside the OpenFOAM container with this folder mounted at /work.
exec docker run --rm --platform linux/arm64 -v "$(cd "$(dirname "$0")" && pwd)":/work -w /work opencfd/openfoam-run:2412 bash -lc "cd /work && $*"
