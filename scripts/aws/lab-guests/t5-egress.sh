#!/bin/bash
# Lab-only T5 battery. Attach only the leaf under vantio-t5-lab.slice.
# Entropy stays in the userspace drills unless a later program says otherwise.
set -euo pipefail

bundle="${1:-/var/lib/vantio-lab/enterprise-bundle}"
rows="${2:-/var/lib/vantio-lab/enterprise-pe-rows.json}"
cgroup="/sys/fs/cgroup/vantio-t5-lab.slice/t5-drill"

case "${bundle}${rows}${cgroup}" in
  *navera*|*Navera*)
    echo "navera" >&2
    exit 2
    ;;
esac
case "$bundle" in
  /var/lib/vantio-lab/enterprise-bundle|/var/lib/vantio-lab/guest) ;;
  *)
    echo "bundle" >&2
    exit 2
    ;;
esac
if [[ "$rows" == *vantio-enrolled.slice* || "$cgroup" == *vantio-enrolled.slice* ]]; then
  echo "cgroup" >&2
  exit 2
fi

rm -rf "$bundle/t5-work"
mkdir -p "$bundle/t5-work"
tar -xf "$bundle/t5-egress.tar" -C "$bundle/t5-work"
cd "$bundle/t5-work"
export PYTHONPATH="$PWD/packages/t5-egress-drills:$PWD/packages/t5-egress-kernel"
export T5_HOST_CLASS=vantio-owned
boot_id="$(tr -d '\n' < /proc/sys/kernel/random/boot_id)"
uptime_seconds="$(awk '{print int($1)}' /proc/uptime)"
attach_rc=0
if [[ -x "$bundle/t5_load" && -f "$bundle/t5_egress.bpf.o" ]]; then
  set +e
  sudo env LD_LIBRARY_PATH="$bundle" "$bundle/t5_load" "$bundle/t5_egress.bpf.o" "$cgroup" >"$bundle/t5-attach.json"
  attach_rc=$?
  set -e
else
  printf '%s\n' '{"verifier":"not_run","attached":false,"user_port":"not_run","label":"Roadmap"}' >"$bundle/t5-attach.json"
fi
set +e
python3 scripts/clean-host/t5/proof.py
proof_rc=$?
python3 scripts/clean-host/t5/kernel_proof.py
kernel_rc=$?
set -e
python3 - "$rows" "$bundle/t5-attach.json" "$boot_id" "$uptime_seconds" "$attach_rc" "$proof_rc" "$kernel_rc" "${T5_REQUIRE_ATTACH:-0}" <<'PY'
import json
import sys
from pathlib import Path

rows, attach_path, boot_id, uptime, attach_rc, proof_rc, kernel_rc, require_attach = sys.argv[1:]
try:
    attach = json.loads(Path(attach_path).read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    attach = {"verifier": "not_run", "attached": False, "user_port": "not_run"}
drills = proof_rc == "0" and kernel_rc == "0"
attached_ok = attach_rc == "0" and attach.get("user_port") == "pass" and attach.get("verifier") == "accepted"
passed = drills and (attached_ok if require_attach == "1" else True)
body = {
    "battery": "t5-egress",
    "result": "pass" if passed else "fail",
    "label": "Lab-only" if attach.get("verifier") == "accepted" else "Roadmap",
    "kernel_attach": "Lab-only" if attach.get("attached") is True else "Roadmap",
    "verifier": attach.get("verifier") if attach.get("verifier") in {"accepted", "rejected", "not_run"} else "not_run",
    "user_port": attach.get("user_port") if attach.get("user_port") in {"pass", "fail", "not_run"} else "not_run",
    "attached": attach.get("attached") is True,
    "outside_unaffected": attach.get("outside_unaffected") is True,
    "enrolled_slice": False,
    "cgroup": "/sys/fs/cgroup/vantio-t5-lab.slice/t5-drill",
    "boot_id": boot_id,
    "uptime_seconds": int(uptime) if uptime.isdigit() else 0,
}
Path(rows).write_text(json.dumps(body) + "\n", encoding="utf-8")
sys.exit(0 if passed else 1)
PY
