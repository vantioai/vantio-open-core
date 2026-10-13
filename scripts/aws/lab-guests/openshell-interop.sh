#!/bin/bash
# Record an OpenShell interop observation. Does not restart the machine.
# A missing installer is a gap, not a pass.
set -euo pipefail
out=/tmp/enterprise-pe-rows.json
python3 - "$out" <<'PY'
import json
import sys
from pathlib import Path

dest = Path(sys.argv[1])
lsm = ""
try:
    lsm = Path("/sys/kernel/security/lsm").read_text(encoding="utf-8").strip()
except OSError:
    lsm = ""
bpf = "bpf" in [part.strip() for part in lsm.split(",") if part.strip()]
staged = Path("/var/lib/vantio-lab/openshell/RELEASE").is_file()
body = {
    "battery": "openshell-interop",
    "bpf_in_lsm": bpf,
    "host_result": "GAP",
    "lab_pass": False,
    "live": "GAP",
    "openshell_staged": staged,
    "reason": "openshell_not_staged" if not staged else "openshell_observations_missing",
    "reboot_requested": False,
}
dest.write_text(json.dumps(body, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(body, sort_keys=True))
PY
chmod a+r "$out" 2>/dev/null || true
exit 2
