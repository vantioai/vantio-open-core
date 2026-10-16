#!/bin/bash
# Verify the policy-allow seal and run the bundled Enterprise row script.
# The runner copies seal.oci.tar and contract.tar into this directory over
# the Instance Connect session. This script does not fetch either file and
# it does not read a token.
set -euo pipefail
seal=${1:?}
here=$(cd "$(dirname "$0")" && pwd)
stage=/opt/vantio-enterprise
image_name=vantio-phantom-engine:egress-2e6ab54
trust_sha=2e4a1da7bf44f0bddfc2a3ce3eda007fa6cc1455332f26769bd346fafc297876
if ! printf '%s' "$seal" | grep -Eq '^[0-9a-f]{64}$'; then
  exit 2
fi
test -f "$here/seal.oci.tar"
test -f "$here/contract.tar"
echo "${seal}  ${here}/seal.oci.tar" | sha256sum -c -
if tar -tzf "$here/contract.tar" | grep -E '(^/|(^|/)\.\.(/|$)|private-key\.pem$)' >/dev/null; then
  echo "contract member refused" >&2
  exit 3
fi
if tar -xOzf "$here/contract.tar" | grep -E 'BEGIN [A-Z ]*PRIVATE KEY' >/dev/null; then
  echo "private key refused" >&2
  exit 4
fi
python3 - "$here/contract.tar" "$trust_sha" <<'PY'
import hashlib
import json
import sys
import tarfile

path, expected = sys.argv[1], sys.argv[2]
found = False
with tarfile.open(path, "r:*") as tar:
    for member in tar.getmembers():
        if member.name != "vantio_enterprise_protocol/trust/test_nonprod_2026_10_02.json":
            continue
        handle = tar.extractfile(member)
        if handle is None:
            raise SystemExit(5)
        body = handle.read()
        if hashlib.sha256(body).hexdigest() != expected:
            raise SystemExit(5)
        payload = json.loads(body)
        keys = payload.get("keys") or []
        if len(keys) != 1 or not isinstance(keys[0], dict):
            raise SystemExit(5)
        key = keys[0]
        if key.get("not_a_production_root") is not True:
            raise SystemExit(5)
        if key.get("environment") != "NON-PRODUCTION" or key.get("label") != "TEST":
            raise SystemExit(5)
        if key.get("key_id") != "test-nonprod-ed25519-2026-10-02":
            raise SystemExit(5)
        found = True
if not found:
    raise SystemExit(5)
PY
# One reboot for every battery. vantio-lab-lsm-reboot running
# reboot-with-grub.sh is the schedule that changed the boot on this image.
# A second unit name, and a bare `systemctl reboot`, are a different path.
# --system --slice=system.slice puts the timer in the system manager.
# The SSH session scope is not that slice, and the user manager is not
# this bus. The runner drops its session before the 45s timer fires.
# A fresh host has no sealed script. reboot-check and descendant install
# the stock one. lsm-guard writes the sealed one itself and must not have
# a stock script substituted for it. The sealed script reads
# /var/lib/vantio-lab/guest/baseline_diag.py when it re-seals or records
# boot evidence. The runner copies that file into the bundle, not guest/.
ensure_stock_reboot_script() {
  if [ -x /var/lib/vantio-lab/reboot-with-grub.sh ]; then
    return 0
  fi
  sudo python3 - "$here" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import baseline_diag
baseline_diag.install_stock_reboot_script()
PY
}

stage_reboot_guest_files() {
  if [ ! -f "$here/baseline_diag.py" ]; then
    return 0
  fi
  sudo mkdir -p /var/lib/vantio-lab/guest
  sudo cp -f "$here/baseline_diag.py" /var/lib/vantio-lab/guest/baseline_diag.py
  sudo chmod 644 /var/lib/vantio-lab/guest/baseline_diag.py
}

schedule_forced_reboot() {
  local unit=vantio-lab-lsm-reboot
  local reboot_cmd=/var/lib/vantio-lab/reboot-with-grub.sh
  sudo systemctl mask --now google-shutdown-scripts.service >/dev/null 2>&1 || true
  sudo systemctl reset-failed "${unit}.service" "${unit}.timer" >/dev/null 2>&1 || true
  sudo systemctl stop "${unit}.timer" "${unit}.service" >/dev/null 2>&1 || true
  stage_reboot_guest_files
  if [ ! -x "$reboot_cmd" ]; then
    echo "reboot_script_missing" >&2
    return 1
  fi
  if ! sudo systemd-run --system --slice=system.slice --on-active=45s --timer-property=AccuracySec=1s --unit="$unit" "$reboot_cmd"; then
    echo "reboot_not_scheduled unit=${unit}" >&2
    return 1
  fi
  echo "reboot_scheduled unit=${unit} delay=45s slice=system.slice"
}

# The runner reads /var/lib/vantio-lab/enterprise-pe-rows.json. /tmp is
# tmpfs on this image, so a file left only there is gone after the reboot.
# Copy the newest body. A missing body is rows_missing, not a guess.
publish_durable_rows() {
  sudo mkdir -p /var/lib/vantio-lab
  sudo chmod 755 /var/lib/vantio-lab
  local src=/tmp/enterprise-pe-rows.json
  if [ ! -s "$src" ] && [ -s /var/lib/vantio-lab/enterprise-pe-rows.json ]; then
    src=/var/lib/vantio-lab/enterprise-pe-rows.json
  fi
  if [ ! -s "$src" ]; then
    echo "rows_missing" >&2
    return 1
  fi
  if [ "$src" != /var/lib/vantio-lab/enterprise-pe-rows.json ]; then
    sudo cp -f "$src" /var/lib/vantio-lab/enterprise-pe-rows.json
  fi
  sudo chmod a+r /var/lib/vantio-lab/enterprise-pe-rows.json
}

# A second boot already has bpf in the LSM list. Confirm that and return
# before docker starts. The first boot falls through and proves the refusal.
if [ "${2:-}" = "lsm-guard" ]; then
  set +e
  sudo env VANTIO_IMAGE_NAME="${VANTIO_IMAGE_NAME:-}" python3 - "$here" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import baseline_diag
raise SystemExit(baseline_diag.write_lsm_status())
PY
  st=$?
  set -e
  if [ "$st" -eq 0 ] || [ "$st" -eq 2 ]; then
    if ! publish_durable_rows; then
      exit 1
    fi
    exit "$st"
  fi
fi
# The rows file is root-owned. Record the live lockdown mode and the exact
# image name into it. A family name is not that image.
stamp_host_evidence() {
  if [ ! -f "$here/baseline_diag.py" ]; then
    return 0
  fi
  if ! sudo env VANTIO_IMAGE_NAME="${VANTIO_IMAGE_NAME:-}" python3 - "$here" << 'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import baseline_diag
from sticky_write import write_replacing

lockdown = baseline_diag.read_lockdown()
image_name = baseline_diag.read_image_name()
rows = Path("/tmp/enterprise-pe-rows.json")
if not rows.is_file():
    raise SystemExit(0)
try:
    body = json.loads(rows.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)
if not isinstance(body, dict):
    raise SystemExit(1)
changed = False
if lockdown:
    body["lockdown"] = lockdown
    changed = True
if image_name:
    body["image_name"] = image_name
    changed = True
if changed:
    write_replacing(rows, json.dumps(body) + "\n")
PY
  then
    echo "rows_malformed" >&2
  fi
  sudo chmod a+r /tmp/enterprise-pe-rows.json 2>/dev/null || true
}

# Reboot proof only. No docker and no descendant probe. The schedule is the
# function above; the runner leaves and then reads the new boot id.
# A fresh host has never run the LSM guard, so the sealed script is absent.
# Install the stock reboot script first. Leave a sealed script in place.
# A previous battery leaves the rows file owned by root. Remove it before
# this run writes, and write as root. The durable record is in place before
# the timer is armed. A failed schedule rewrites that record and stops the timer.
if [ "${2:-}" = "reboot-check" ]; then
  sudo rm -f /tmp/enterprise-pe-rows.json /var/lib/vantio-lab/enterprise-pe-rows.json
  boot_id=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || true)
  reason=""
  if ! ensure_stock_reboot_script; then
    reason=reboot_script_missing
  elif [ ! -x /var/lib/vantio-lab/reboot-with-grub.sh ]; then
    reason=reboot_script_missing
  fi
  write_reboot_check_rows() {
    sudo python3 - "$boot_id" "$reason" <<'PY'
import json
import sys

boot_id, reason = sys.argv[1], sys.argv[2]
body = {
    "battery": "reboot-check",
    "boot_id": boot_id,
    "reboot_requested": reason == "",
    "unit": "vantio-lab-lsm-reboot",
}
if reason:
    body["reason"] = reason
text = json.dumps(body) + "\n"
with open("/tmp/enterprise-pe-rows.json", "w", encoding="utf-8") as handle:
    handle.write(text)
print(text, end="")
PY
  }
  if ! write_reboot_check_rows; then
    exit 1
  fi
  sudo chmod a+r /tmp/enterprise-pe-rows.json 2>/dev/null || true
  stamp_host_evidence
  if ! publish_durable_rows; then
    exit 1
  fi
  if [ -n "$reason" ]; then
    exit 1
  fi
  if ! schedule_forced_reboot; then
    reason=reboot_not_scheduled
    sudo systemctl stop vantio-lab-lsm-reboot.timer vantio-lab-lsm-reboot.service >/dev/null 2>&1 || true
    if ! write_reboot_check_rows; then
      exit 1
    fi
    sudo chmod a+r /tmp/enterprise-pe-rows.json 2>/dev/null || true
    stamp_host_evidence
    if ! publish_durable_rows; then
      exit 1
    fi
    exit 1
  fi
  exit 0
fi
sudo rm -rf "$stage"
sudo mkdir -p "$stage"
sudo tar -xzf "$here/contract.tar" -C "$stage"
sudo chown -R "$(id -un):$(id -un)" "$stage"
if find "$stage" -name 'private-key.pem' | grep -q .; then
  exit 3
fi
python3 - "$stage/guest_rows.py" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
probe = 'os.write(result_w, f"{uid0} {nobody} {here}\\n".encode())'
probed = 'os.write(result_w, f"{uid0} {nobody} {here} pid {os.getpid()}\\n".encode())'
if probe in text:
    path.write_text(text.replace(probe, probed), encoding="utf-8")
PY
# The lab security group has no egress. Packages arrive over the runner SSH
# session. This script does not reach apt mirrors.
if ! compgen -G "$here/debs/*.deb" >/dev/null; then
  echo "offline debs missing; refusing network apt" >&2
  exit 6
fi
dpkg_ok=0
for _pass in 1 2 3 4 5; do
  if sudo dpkg -i "$here/debs"/*.deb >/tmp/dpkg-offline.log 2>&1; then
    dpkg_ok=1
    break
  fi
done
if [ "$dpkg_ok" != 1 ]; then
  echo "offline dpkg failed" >&2
  tail -n 40 /tmp/dpkg-offline.log >&2 || true
  exit 6
fi
command -v docker >/dev/null
python3 -c "import cryptography"
sudo mkdir -p /etc/docker
printf '%s\n' '{"features":{"containerd-snapshotter":false},"storage-driver":"overlay2"}' | sudo tee /etc/docker/daemon.json >/dev/null
sudo systemctl enable --now docker
sudo systemctl restart docker
ready=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  if sudo docker info >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done
test "$ready" = 1

# The seal tar is already sha256-checked. docker load prints the tag baked
# into that tar. Keep the historical lab tag, and also accept a
# vantio-phantom-engine tag that is the engine commit. Anything else stops
# here and writes a rows file so the runner can see the refusal.
normalize_loaded_image() {
  local loaded=$1
  loaded=${loaded#docker.io/library/}
  loaded=${loaded//$'\r'/}
  loaded=${loaded#"${loaded%%[![:space:]]*}"}
  loaded=${loaded%"${loaded##*[![:space:]]}"}
  if [ "$loaded" = "$image_name" ]; then
    printf '%s\n' "$loaded"
    return 0
  fi
  if printf '%s' "$loaded" | grep -Eq '^vantio-phantom-engine:[0-9a-f]{7,40}$'; then
    printf '%s\n' "$loaded"
    return 0
  fi
  return 1
}

refuse_loaded_image() {
  local loaded=$1
  printf '%s\n' "loaded image refused" >&2
  python3 - "$loaded" <<'PY'
import json
import sys

loaded = sys.argv[1][:180]
body = {
    "battery": "lsm-guard",
    "host_result": "FAIL",
    "reason": "loaded_image_refused",
    "loaded_image": loaded,
    "lab_pass": False,
    "customer_claim": False,
    "reboot_requested": False,
    "bootchain": {},
}
text = json.dumps(body) + "\n"
with open("/tmp/enterprise-pe-rows.json", "w", encoding="utf-8") as handle:
    handle.write(text)
print(text, end="")
PY
  chmod a+r /tmp/enterprise-pe-rows.json 2>/dev/null || true
  if ! publish_durable_rows; then
    exit 1
  fi
  exit 6
}

accept_loaded_image() {
  local load=$1 loaded normalized
  loaded=$(printf '%s\n' "$load" | sed -n 's/^Loaded image: //p' | tail -n 1)
  if ! normalized=$(normalize_loaded_image "$loaded"); then
    refuse_loaded_image "$loaded"
  fi
  printf '%s\n' "$normalized"
}

load=$(sudo docker load -i "$here/seal.oci.tar" 2>&1)
printf '%s\n' "$load"
image=$(accept_loaded_image "$load")

# The distro bpftool is a wrapper. It exits 2 when the package for this
# kernel is absent, even if another kernel's bpftool binary is installed.
# A failing wrapper makes the engine report bpftool missing and never print
# UNINSTALL_VERIFIED.
ensure_working_bpftool() {
  export PATH="/usr/local/bin:/usr/sbin:/usr/bin:$PATH"
  if bpftool version >/dev/null 2>&1; then
    return 0
  fi
  local found="" candidate
  while IFS= read -r candidate; do
    if [ -n "$candidate" ] && "$candidate" version >/dev/null 2>&1; then
      found=$candidate
      break
    fi
  done < <(sudo find /usr/lib /usr/sbin /usr/bin -name bpftool -type f 2>/dev/null || true)
  if [ -z "$found" ]; then
    return 1
  fi
  sudo ln -sfn "$found" /usr/local/bin/bpftool
  if [ -e /usr/sbin/bpftool ] && ! /usr/sbin/bpftool version >/dev/null 2>&1; then
    sudo mv -f /usr/sbin/bpftool /usr/sbin/bpftool.wrapper
    sudo ln -sfn "$found" /usr/sbin/bpftool
  fi
  export PATH="/usr/local/bin:/usr/sbin:/usr/bin:$PATH"
  bpftool version >/dev/null 2>&1
}

# A restarted container keeps a second loader generation and its fds.
stop_loader_containers() {
  local id
  sudo docker update --restart=no vantio-lab-loader >/dev/null 2>&1 || true
  sudo docker stop --signal SIGINT --time 20 vantio-lab-loader >/dev/null 2>&1 || true
  sudo docker rm -f vantio-lab-loader >/dev/null 2>&1 || true
  sudo docker update --restart=no vantio-pe-lab >/dev/null 2>&1 || true
  sudo docker rm -f vantio-pe-lab >/dev/null 2>&1 || true
  for id in $(sudo docker ps -q 2>/dev/null || true); do
    if sudo docker top "$id" -eo pid,comm 2>/dev/null | grep -q vantio-loader; then
      sudo docker update --restart=no "$id" >/dev/null 2>&1 || true
      sudo docker rm -f "$id" >/dev/null 2>&1 || true
    fi
  done
}

ensure_working_bpftool || true

authorized_uninstall() {
  local image="$1"
  local require_row="${2:-no}"
  local probe_pid="${3:-0}"
  export PATH="/usr/local/bin:/usr/sbin:/usr/bin:$PATH"
  record_uninstall() {
    # guest_rows.py runs as root and owns this file. The lab user cannot
    # truncate it, so the tail has to be written as root or the runner
    # uploads the pre-uninstall body.
    if ! sudo python3 - "$here/sticky_write.py" << 'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve().parent))
from sticky_write import write_replacing

rows = Path("/tmp/enterprise-pe-rows.json")
if rows.is_file():
    try:
        body = json.loads(rows.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise SystemExit(1)
    if not isinstance(body, dict):
        raise SystemExit(1)
else:
    body = {}
out = Path("/var/lib/vantio-lab/vantio-uninstall.out")
body["uninstall_tail"] = out.read_text(encoding="utf-8", errors="replace")[-1200:] if out.is_file() else ""
try:
    boot = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
except OSError:
    boot = ""
if boot and "\n" not in boot and len(boot) <= 80:
    body["boot_id"] = boot
write_replacing(rows, json.dumps(body))
PY
    then
      echo "rows_malformed" >&2
    fi
    sudo chmod a+r /tmp/enterprise-pe-rows.json /var/lib/vantio-lab/vantio-uninstall.out 2>/dev/null || true
  }
  trap record_uninstall RETURN
  # A previous battery can leave this file. The loader truncates it only
  # when it runs, and the shell markers below have to be in it too. The
  # recorder reads this file, not the script's stderr. The shell redirect
  # owns the file. tee as root is refused in sticky /tmp.
  sudo mkdir -p /var/lib/vantio-lab
  sudo rm -f /var/lib/vantio-lab/vantio-uninstall.out
  if ! ensure_working_bpftool; then
    echo "UNINSTALL_RESIDUAL bpftool missing" | tee -a /var/lib/vantio-lab/vantio-uninstall.out >&2
    return 1
  fi
  stop_loader_containers
  sudo mkdir -p /var/lib/vantio /var/log/vantio
  if [ ! -s /var/lib/vantio/enterprise-uninstall.token ]; then
    printf '%s\n' "lab-nonprod-uninstall" | sudo tee /var/lib/vantio/enterprise-uninstall.token >/dev/null
  fi
  local token
  token=$(sudo cat /var/lib/vantio/enterprise-uninstall.token)
  if [ -f /run/vantio-failclosed-mounts ]; then
    while IFS= read -r path; do
      case "$path" in
        /*) sudo umount "$path" >/dev/null 2>&1 || true ;;
      esac
    done < /run/vantio-failclosed-mounts
  fi
  if ! sudo docker image inspect "$image" >/dev/null 2>&1; then
    sudo docker load -i "$here/seal.oci.tar" >/dev/null
  fi
  local cid
  cid=$(sudo docker create "$image")
  sudo docker cp "$cid":/vantio-loader /var/lib/vantio/vantio-loader
  sudo docker rm "$cid" >/dev/null
  sudo chmod 755 /var/lib/vantio/vantio-loader
  set +e
  sudo env PATH="$PATH" /var/lib/vantio/vantio-loader --uninstall --confirm uninstall --enterprise-approval "$token" >/var/lib/vantio-lab/vantio-uninstall.out 2>&1
  local urc=$?
  set -e
  cat /var/lib/vantio-lab/vantio-uninstall.out
  if ! grep -qx 'UNINSTALL_VERIFIED' /var/lib/vantio-lab/vantio-uninstall.out; then
    echo "UNINSTALL_NOT_VERIFIED rc=$urc" | tee -a /var/lib/vantio-lab/vantio-uninstall.out >&2
    return 1
  fi
  if find /sys/fs/bpf -maxdepth 2 -name 'vantio*' -print 2>/dev/null | grep -q .; then
    {
      echo "UNINSTALL_RESIDUAL bpffs"
      find /sys/fs/bpf -maxdepth 2 -name 'vantio*' -print 2>/dev/null || true
    } | tee -a /var/lib/vantio-lab/vantio-uninstall.out >&2
    return 1
  fi
  if [ "$require_row" = "yes" ]; then
    python3 - "$probe_pid" /var/lib/vantio-lab/vantio-uninstall.out /var/log/vantio/uninstall.ndjson /var/lib/vantio-pe-clean-host/evidence/events.ndjson <<'PY'
import json, sys
want = int(sys.argv[1])
found = False
for path in sys.argv[2:]:
    try:
        lines = open(path, errors="replace").read().splitlines()
    except OSError:
        continue
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("source") != "deny_attr_post_kill" or row.get("ActionTaken") != "DENIED":
            continue
        pid = row.get("Pid")
        anchor = row.get("lineage_anchor")
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            continue
        if isinstance(anchor, bool) or not isinstance(anchor, int) or anchor <= 0:
            continue
        if want > 0 and pid != want:
            continue
        print(f"deny_attr_post_kill pid {pid} anchor {anchor}")
        found = True
        break
    if found:
        break
if not found:
    raise SystemExit("post_kill_row_missing")
PY
  fi
}

# phase2 and descendant write the durable file. Mirror it to /tmp for
# the same-boot shell checks. The runner does not read that mirror.
publish_current_rows() {
  if [ -s /var/lib/vantio-lab/enterprise-pe-rows.json ]; then
    sudo cp -f /var/lib/vantio-lab/enterprise-pe-rows.json /tmp/enterprise-pe-rows.json
    sudo chmod a+r /tmp/enterprise-pe-rows.json || true
  fi
}

mode=${2:-enterprise}
phase=${3:-pre}
if [ "$mode" = "descendant-b1" ]; then
  if [ -f "$here/descendant_probe.c" ] && command -v gcc >/dev/null; then
    gcc -O2 -o "$here/descendant_probe" "$here/descendant_probe.c"
  fi
  test -x "$here/descendant_probe"
  printf 'IMAGE_LINE=%s\n' "$image"
  # b1-pre.json survives a reboot. A later pre that fails before it writes
  # would otherwise leave the previous repeat's measurements for post to read.
  # The enterprise rows file also survives, and the runner would upload it
  # as this phase's result.
  if [ "$phase" = "pre" ]; then
    sudo rm -f /var/lib/vantio-lab/b1-pre.json /var/lib/vantio-lab/enterprise-pe-rows.json /tmp/enterprise-pe-rows.json
  else
    sudo rm -f /var/lib/vantio-lab/enterprise-pe-rows.json /tmp/enterprise-pe-rows.json
  fi
  set +e
  sudo env VANTIO_IMAGE="$image" VANTIO_PROBE="$here/descendant_probe" python3 "$here/descendant_b1.py" "$stage" "$phase" > /tmp/descendant-b1.out 2>&1
  rc=$?
  set -e
  cat /tmp/descendant-b1.out
  chmod a+r /tmp/descendant-b1.out 2>/dev/null || true
  publish_current_rows
  if [ -f "$here/redteam_rows.py" ] && [ -f "$here/redteam_packet.py" ]; then
    cp "$here/redteam_packet.py" "$stage/redteam_packet.py"
    brain=/var/lib/vantio-lab/brain
    if [ ! -s "$brain/qwen2.5-3b-instruct-q4_k_m.gguf" ] || [ ! -x "$brain/llama-b11540/llama-server" ]; then
      echo "brain_not_landed $brain" >&2
    fi
    set +e
    sudo env VANTIO_BRAIN_DIR="$brain" python3 "$here/redteam_rows.py" "$stage" > /tmp/redteam-rows.out 2>&1
    rt=$?
    set -e
    cat /tmp/redteam-rows.out
    chmod a+r /tmp/redteam-rows.json 2>/dev/null || true
    printf 'REDTEAM_RC=%s\n' "$rt"
  fi
  printf 'PY_RC=%s\n' "$rc"
  stamp_host_evidence
  if ! publish_durable_rows; then
    exit 1
  fi
  if [ "$phase" = "pre" ] && [ "$rc" -eq 0 ]; then
    sync
    # A fresh host has no sealed reboot script. Install the stock one
    # when it is missing, and leave a script the LSM guard already wrote.
    if ! ensure_stock_reboot_script; then
      exit 1
    fi
    if ! schedule_forced_reboot; then
      exit 1
    fi
  fi
  exit "$rc"
fi
case "$mode" in
  soak-hourly)
    sudo install -d /var/lib/vantio-lab/bin
    sudo cp "$here/soak_check.py" "$here/soak-hourly.sh" "$here/record-check.sh" \
      "$here/phase2_host.py" "$here/phase2_grade.py" "$here/baseline_diag.py" "$here/sticky_write.py" \
      /var/lib/vantio-lab/bin/
    sudo chmod 755 /var/lib/vantio-lab/bin/soak-hourly.sh /var/lib/vantio-lab/bin/record-check.sh
    sudo bash /var/lib/vantio-lab/bin/soak-hourly.sh install
    sudo rm -f /tmp/enterprise-pe-rows.json /var/lib/vantio-lab/enterprise-pe-rows.json
    set +e
    sudo env VANTIO_IMAGE="$image" VANTIO_IMAGE_ID="${VANTIO_IMAGE_ID:-}" VANTIO_IMAGE_NAME="${VANTIO_IMAGE_NAME:-}" VANTIO_EGRESS_HOST="${VANTIO_EGRESS_HOST:-}" VANTIO_EGRESS_PORT="${VANTIO_EGRESS_PORT:-}" bash /var/lib/vantio-lab/bin/soak-hourly.sh start > /tmp/phase2-host.out 2>&1
    rc=$?
    set -e
    cat /tmp/phase2-host.out
    publish_current_rows
    chmod a+r /tmp/phase2-host.out /tmp/enterprise-pe-rows.json /var/lib/vantio-lab/checks.ndjson 2>/dev/null || true
    printf 'PY_RC=%s\n' "$rc"
    stamp_host_evidence
    if ! publish_durable_rows; then
      exit 1
    fi
    exit "$rc"
    ;;
  2c-upgrade-rollback|2d-crash-recovery|2e-performance|2f-tamper|2g-distro|lsm-guard)
    # A previous battery leaves both copies. Delete both, then this phase
    # writes the durable file the runner reads.
    sudo rm -f /tmp/enterprise-pe-rows.json /var/lib/vantio-lab/enterprise-pe-rows.json
    set +e
    sudo env VANTIO_IMAGE="$image" VANTIO_IMAGE_ID="${VANTIO_IMAGE_ID:-}" VANTIO_IMAGE_NAME="${VANTIO_IMAGE_NAME:-}" VANTIO_EGRESS_HOST="${VANTIO_EGRESS_HOST:-}" VANTIO_EGRESS_PORT="${VANTIO_EGRESS_PORT:-}" python3 "$here/phase2_host.py" "$stage" "$mode" > /tmp/phase2-host.out 2>&1
    rc=$?
    set -e
    cat /tmp/phase2-host.out
    chmod a+r /tmp/phase2-host.out /tmp/enterprise-pe-rows.json 2>/dev/null || true
    publish_current_rows
    printf 'PY_RC=%s\n' "$rc"
    require_row=no
    probe_pid=0
    if [ "$mode" = "2f-tamper" ]; then
      require_row=yes
      if [ -s /var/lib/vantio-lab/enterprise-pe-rows.json ]; then
        probe_pid=$(python3 -c 'import json; d=json.load(open("/var/lib/vantio-lab/enterprise-pe-rows.json")); e=d.get("enrolled_after") or {}; p=e.get("pid") or 0; print(p if isinstance(p, int) else 0)')
      fi
    fi
    if ! authorized_uninstall "$image" "$require_row" "$probe_pid"; then
      stamp_host_evidence
      if ! publish_durable_rows; then
        exit 1
      fi
      exit 1
    fi
    stamp_host_evidence
    if ! publish_durable_rows; then
      exit 1
    fi
    if [ "$mode" = "lsm-guard" ]; then
      want=$(python3 -c 'import json; d=json.load(open("/var/lib/vantio-lab/enterprise-pe-rows.json")); print("yes" if d.get("reboot_requested") is True and d.get("host_result")=="GUARD_PROVED" else "no")')
      if [ "$want" = "yes" ]; then
        sync
        if ! schedule_forced_reboot; then
          exit 1
        fi
      fi
    fi
    exit "$rc"
    ;;
esac
set +e
sudo rm -f /tmp/enterprise-pe-rows.json /var/lib/vantio-lab/enterprise-pe-rows.json
# guest_rows reads bpftool before this shell's uninstall. The Noble wrapper
# exits 2 until a real bpftool is on PATH. Point at that binary first.
# This does not detach programs.
if ! ensure_working_bpftool; then
  python3 -c 'import json; json.dump({"uninstall_tail":"UNINSTALL_RESIDUAL bpftool missing\n"}, open("/tmp/enterprise-pe-rows.json","w"))'
  stamp_host_evidence
  if ! publish_durable_rows; then
    exit 1
  fi
  exit 1
fi
sudo env VANTIO_IMAGE="$image" python3 "$stage/guest_rows.py" "$stage"
rc=$?
set -e
if ! authorized_uninstall "$image" no 0; then
  stamp_host_evidence
  if ! publish_durable_rows; then
    exit 1
  fi
  exit 1
fi
# Read bpftool and bpffs after the product uninstall. Do not detach.
if ! sudo env PATH="/usr/local/bin:/usr/sbin:/usr/bin:$PATH" python3 "$here/product_uninstall_census.py" --record /tmp/enterprise-pe-rows.json --guest-rc "$rc"; then
  stamp_host_evidence
  if ! publish_durable_rows; then
    exit 1
  fi
  exit 1
fi
stamp_host_evidence
if ! publish_durable_rows; then
  exit 1
fi
exit 0
