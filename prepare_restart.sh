#!/bin/bash
# Create the 5-degree pitch/yaw stability cases and initialise them from the
# converged 0-degree solutions (same mesh), keeping the new cases' boundary
# conditions (rotated free stream).
# Usage: ./prepare_restart.sh [iters]
set -e
cd "$(dirname "$0")"
CASES="fwd_p5 bwd_p5 fwd_y5 bwd_y5"
ITERS=${1:-700}
.venv/bin/python make_cases.py --iters "$ITERS" $CASES
for c in $CASES; do
  src=cfd/${c%_*}_a0
  last=$(ls -d "$src"/[0-9]* | grep -v '/0$' | sort -t/ -k3 -n | tail -1)
  mv cfd/$c/0 cfd/$c/0.template
  mkdir cfd/$c/0
  cp "$last"/{U,p,k,omega,nut} cfd/$c/0/
  sed -i '' 's/^writeFormat binary;/writeFormat ascii;/' cfd/$c/system/controlDict
done
./docker_of.sh "for c in $CASES; do foamFormatConvert -case cfd/\$c -time 0 -noFunctionObjects > cfd/\$c/log.foamFormatConvert 2>&1; done"
.venv/bin/python - $CASES <<'EOF'
import sys
for c in sys.argv[1:]:
    for f in ("U", "p", "k", "omega", "nut"):
        conv = open(f"cfd/{c}/0/{f}").read()
        tmpl = open(f"cfd/{c}/0.template/{f}").read()
        # Keep the converged interior field; take boundary conditions from the new case.
        new = conv[:conv.index("boundaryField")] + tmpl[tmpl.index("boundaryField"):]
        open(f"cfd/{c}/0/{f}", "w").write(new)
    print(c, "initialised")
EOF
for c in $CASES; do
  sed -i '' 's/^writeFormat ascii;/writeFormat binary;/' cfd/$c/system/controlDict
  rm -rf cfd/$c/0.template
done
