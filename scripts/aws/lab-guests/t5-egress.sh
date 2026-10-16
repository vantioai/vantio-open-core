#!/bin/bash
# Lab-only T5 battery. Does not attach a program and does not touch
# vantio-enrolled.slice. Entropy stays in the userspace drills.
set -euo pipefail

bundle="${1:-/var/lib/vantio-lab/enterprise-bundle}"
rows="${2:-/var/lib/vantio-lab/enterprise-pe-rows.json}"

case "${bundle}${rows}" in
  *navera*|*Navera*)
    echo "navera" >&2
    exit 2
    ;;
esac
case "$bundle" in
  /var/lib/vantio-lab/enterprise-bundle) ;;
  *)
    echo "bundle" >&2
    exit 2
    ;;
esac
if [[ "$rows" == *vantio-enrolled.slice* ]]; then
  echo "cgroup" >&2
  exit 2
fi

rm -rf "$bundle/t5-work"
mkdir -p "$bundle/t5-work"
tar -xf "$bundle/t5-egress.tar" -C "$bundle/t5-work"
cd "$bundle/t5-work"
export PYTHONPATH="$PWD/packages/t5-egress-drills:$PWD/packages/t5-egress-kernel"
export T5_HOST_CLASS=vantio-owned
python3 scripts/clean-host/t5/proof.py
python3 scripts/clean-host/t5/kernel_proof.py
python3 - "$rows" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.write_text(
    json.dumps(
        {
            "battery": "t5-egress",
            "result": "pass",
            "label": "Lab-only",
            "kernel_attach": "Roadmap",
        }
    )
    + "\n",
    encoding="utf-8",
)
PY
