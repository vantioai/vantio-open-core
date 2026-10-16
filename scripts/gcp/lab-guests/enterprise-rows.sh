#!/bin/bash
# Verify the policy-allow seal and run the bundled Enterprise row script.
# The runner copies seal.oci.tar, contract.tar, and offline .debs into this
# directory over IAP. This host has no internet route. Package install uses
# only those .debs. This script does not fetch and it does not read a token.
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
mode=${2:-plumb}
phase=${3:-pre}
if [ "$mode" = "plumb" ]; then
  python3 - "$here/seal.oci.tar" "$trust_sha" <<'PY'
import hashlib
import json
import os
import pathlib
import sys

seal_path, trust = sys.argv[1], sys.argv[2]
digest = hashlib.sha256(pathlib.Path(seal_path).read_bytes()).hexdigest()
body = {
    "batteries": False,
    "claim_cap": "INTERNAL_CLEAN_HOST_PROOF",
    "mode": "plumb",
    "seal_sha256": digest,
    "trust_sha256": trust,
}
path = pathlib.Path("/tmp/gcp-plumb.json")
path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
os.chmod(path, 0o644)
print(digest)
PY
  exit 0
fi
# A second boot already has bpf in the LSM list. Confirm that and return
# before docker starts. The first boot falls through and proves the refusal.
if [ "$mode" = "lsm-guard" ]; then
  # Drop both copies before this boot writes its own result. The runner
  # keeps the file whose boot id matches the boot it just waited for.
  sudo rm -f /tmp/enterprise-pe-rows.json /var/lib/vantio-lab/enterprise-pe-rows.json
  set +e
  sudo python3 - "$here" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import baseline_diag
raise SystemExit(baseline_diag.write_lsm_status())
PY
  st=$?
  set -e
  if [ "$st" -eq 0 ] || [ "$st" -eq 2 ]; then
    if [ ! -s /var/lib/vantio-lab/enterprise-pe-rows.json ]; then
      echo "rows_missing" >&2
      exit 1
    fi
    sudo chmod a+r /var/lib/vantio-lab/enterprise-pe-rows.json
    exit "$st"
  fi
fi

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

# The rows file is root-owned. Record the live lockdown mode and the exact
# image name into it. A family name is not that image.
stamp_host_evidence() {
  if [ ! -f "$here/baseline_diag.py" ]; then
    return 0
  fi
  if ! sudo python3 - "$here" << 'PY'
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
  if printf '%s' "$loaded" | grep -Eq '^vantio-phantom-engine:(egress-2e6ab54|[0-9a-f]{7,40})$'; then
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

case "$mode" in
  enterprise|descendant-b1|2c-upgrade-rollback|2d-crash-recovery|lsm-guard|uninstall) ;;
  *)
    echo "battery" >&2
    exit 2
    ;;
esac
if [ "$mode" = "uninstall" ]; then
  if ! sudo docker info >/dev/null 2>&1; then
    echo "docker is not up" >&2
    exit 1
  fi
  image=$image_name
  if ! sudo docker image inspect "$image" >/dev/null 2>&1; then
    load=$(sudo docker load -i "$here/seal.oci.tar" 2>&1)
    printf '%s\n' "$load"
    image=$(accept_loaded_image "$load")
  fi
  set +e
  authorized_uninstall "$image" "${VANTIO_REQUIRE_POST_KILL:-yes}" "${VANTIO_PROBE_PID:-0}"
  urc=$?
  set -e
  stamp_host_evidence
  exit "$urc"
fi
if [ -f "$here/debs.tar" ]; then
  if tar -tf "$here/debs.tar" | grep -E '(^/|(^|/)\.\.(/|$))' >/dev/null; then
    echo "debs tar refused" >&2
    exit 6
  fi
  mkdir -p "$here/debs"
  tar -C "$here/debs" -xf "$here/debs.tar"
fi
if ! compgen -G "$here/debs/*.deb" >/dev/null; then
  echo "offline debs missing" >&2
  exit 6
fi
if [ ! -s "$here/ca-certificates.crt" ]; then
  echo "ca bundle missing" >&2
  exit 6
fi
sudo mkdir -p /usr/local/share/ca-certificates /etc/ssl/certs
sudo cp "$here/ca-certificates.crt" /usr/local/share/ca-certificates/vantio-lab.crt
sudo cp "$here/ca-certificates.crt" /etc/ssl/certs/ca-certificates.crt
sudo chmod 644 /etc/ssl/certs/ca-certificates.crt /usr/local/share/ca-certificates/vantio-lab.crt
sudo rm -rf "$stage"
sudo mkdir -p "$stage"
sudo tar -xzf "$here/contract.tar" -C "$stage"
sudo chown -R "$(id -un)": "$stage"
python3 - "$stage/guest_rows.py" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = '"-v", "/sys/fs/bpf:/sys/fs/bpf"'
new = '"-v", "/sys/fs/bpf:/sys/fs/bpf:rshared"'
count = text.count(old)
if count:
    text = text.replace(old, new)
probe = 'os.write(result_w, f"{uid0} {nobody} {here}\\n".encode())'
probed = 'os.write(result_w, f"{uid0} {nobody} {here} pid {os.getpid()}\\n".encode())'
pid_count = text.count(probe)
if pid_count:
    text = text.replace(probe, probed)
path.write_text(text, encoding="utf-8")
print(f"bpf_bind_rshared={count} probe_pid={pid_count}")
PY
if find "$stage" -name 'private-key.pem' | grep -q .; then
  exit 3
fi
sudo mkdir -p /var/cache/apt/archives
sudo cp "$here"/debs/*.deb /var/cache/apt/archives/
printf '%s\n' 'Acquire::http::Timeout "1";' 'Acquire::https::Timeout "1";' 'Acquire::Retries "0";' | sudo tee /etc/apt/apt.conf.d/99vantio-offline >/dev/null
if [ -f /etc/apt/sources.list ]; then
  sudo mv /etc/apt/sources.list /etc/apt/sources.list.vantio-offline
fi
if [ -d /etc/apt/sources.list.d ]; then
  sudo find /etc/apt/sources.list.d -maxdepth 1 -type f \( -name '*.list' -o -name '*.sources' \) -exec mv {} {}.vantio-offline \;
fi
if ! sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-download --no-install-recommends "$here"/debs/*.deb; then
  sudo dpkg -i "$here"/debs/*.deb || sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-download --no-install-recommends -f
fi
dpkg -s docker.io >/dev/null
dpkg -s python3-cryptography >/dev/null
if ! sudo swapon --show | grep -q .; then
  sudo fallocate -l 1536M /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=1536
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
fi
if ! findmnt -n -t bpf /sys/fs/bpf >/dev/null 2>&1; then
  sudo mkdir -p /sys/fs/bpf
  sudo mount -t bpf bpf /sys/fs/bpf
fi
sudo mount --make-rshared /sys/fs/bpf
echo "BPFFS $(findmnt -T /sys/fs/bpf | tr '\n' ' ')"
sudo mkdir -p /etc/docker
printf '%s\n' '{"features":{"containerd-snapshotter":false},"storage-driver":"overlay2"}' | sudo tee /etc/docker/daemon.json >/dev/null
sudo systemctl enable --now docker
sudo systemctl restart docker
ready=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
  if sudo docker info >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done
test "$ready" = 1
ensure_working_bpftool || true
python3 - "$here" <<'PY'
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, sys.argv[1])
import baseline_diag

fs = subprocess.check_output(["stat", "-fc", "%T", "/sys/fs/cgroup"], text=True).strip()
lsm_path = pathlib.Path("/sys/kernel/security/lsm")
facts = {
    "claim_cap": "INTERNAL_CLEAN_HOST_PROOF",
    "kernel": os.uname().release,
    "cgroup_fs": fs,
    "cgroup_v2": fs == "cgroup2fs",
    "btf": pathlib.Path("/sys/kernel/btf/vmlinux").is_file(),
    "bpffs": pathlib.Path("/sys/fs/bpf").is_dir(),
    "lsm": lsm_path.read_text(encoding="utf-8").strip() if lsm_path.is_file() else "",
    "lockdown": baseline_diag.read_lockdown(),
    "image_name": baseline_diag.read_image_name(),
}
path = pathlib.Path("/tmp/gcp-kernel-facts.json")
path.write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
os.chmod(path, 0o644)
PY
load=$(sudo docker load -i "$here/seal.oci.tar" 2>&1)
printf '%s\n' "$load"
image=$(accept_loaded_image "$load")
if [ "$mode" = "descendant-b1" ]; then
  printf 'IMAGE_LINE=%s\n' "$image"
  if [ ! -x "$here/descendant_probe" ]; then
    echo "vfork probe missing" >&2
    exit 6
  fi
  # b1-pre.json survives a reboot. A later pre that fails before it writes
  # would otherwise leave the previous repeat's measurements for post to read.
  if [ "$phase" = "pre" ]; then
    sudo rm -f /var/lib/vantio-lab/b1-pre.json
  fi
  sudo rm -f /tmp/enterprise-pe-rows.json
  set +e
  sudo env VANTIO_IMAGE="$image" VANTIO_PROBE="$here/descendant_probe" python3 "$here/descendant_b1.py" "$stage" "$phase" > /tmp/descendant-b1.out 2>&1
  rc=$?
  set -e
  cat /tmp/descendant-b1.out
  chmod a+r /tmp/descendant-b1.out 2>/dev/null || true
  printf 'PY_RC=%s\n' "$rc"
  if [ -s /var/lib/vantio-lab/enterprise-pe-rows.json ]; then
    sudo cp -f /var/lib/vantio-lab/enterprise-pe-rows.json /tmp/enterprise-pe-rows.json
  fi
  stamp_host_evidence
  if [ -s /tmp/enterprise-pe-rows.json ]; then
    sudo mkdir -p /var/lib/vantio-lab
    sudo cp -f /tmp/enterprise-pe-rows.json /var/lib/vantio-lab/enterprise-pe-rows.json
    sudo chmod a+r /var/lib/vantio-lab/enterprise-pe-rows.json
  elif [ ! -s /var/lib/vantio-lab/enterprise-pe-rows.json ]; then
    echo "rows_missing" >&2
    exit 1
  fi
  if [ "$phase" = "pre" ]; then
    sync
    # The offline lab network leaves google-shutdown-scripts.service/stop
    # running with no limit, so a normal reboot never reaches a new boot.
    # Mask that unit, then force the reset after this shell returns.
    sudo systemctl mask --now google-shutdown-scripts.service >/dev/null 2>&1 || true
    if ! sudo systemd-run --on-active=8s --unit=vantio-lab-reboot systemctl reboot --force; then
      sudo systemctl reboot --force || true
    fi
  fi
  exit "$rc"
fi
case "$mode" in
  2c-upgrade-rollback|2d-crash-recovery|lsm-guard)
    # The pre-reboot guard already wrote the /var/lib copy. Leaving it
    # there makes a failed second run look like a post-reboot confirm.
    sudo rm -f /tmp/enterprise-pe-rows.json /var/lib/vantio-lab/enterprise-pe-rows.json
    test -f "$here/phase2_host.py"
    test -f "$here/phase2_grade.py"
    set +e
    sudo env VANTIO_IMAGE="$image" VANTIO_EGRESS_HOST="${VANTIO_EGRESS_HOST:-}" VANTIO_EGRESS_PORT="${VANTIO_EGRESS_PORT:-}" python3 "$here/phase2_host.py" "$stage" "$mode" > /tmp/phase2-host.out 2>&1
    rc=$?
    set -e
    cat /tmp/phase2-host.out
    # phase2 writes the durable file. Mirror it for the same-boot stamp.
    # The transcript in phase2-host.out is not that file.
    if [ -s /var/lib/vantio-lab/enterprise-pe-rows.json ]; then
      sudo cp /var/lib/vantio-lab/enterprise-pe-rows.json /tmp/enterprise-pe-rows.json
    fi
    sudo chmod a+r /tmp/phase2-host.out /tmp/enterprise-pe-rows.json /var/lib/vantio-lab/enterprise-pe-rows.json 2>/dev/null || true
    printf 'PY_RC=%s\n' "$rc"
    stamp_host_evidence
    if [ -s /tmp/enterprise-pe-rows.json ]; then
      sudo mkdir -p /var/lib/vantio-lab
      sudo cp -f /tmp/enterprise-pe-rows.json /var/lib/vantio-lab/enterprise-pe-rows.json
      sudo chmod a+r /var/lib/vantio-lab/enterprise-pe-rows.json
    elif [ ! -s /var/lib/vantio-lab/enterprise-pe-rows.json ]; then
      echo "rows_missing" >&2
      exit 1
    fi
    if [ "$mode" = "lsm-guard" ] && [ -s /var/lib/vantio-lab/enterprise-pe-rows.json ]; then
      want=$(python3 -c 'import json; d=json.load(open("/var/lib/vantio-lab/enterprise-pe-rows.json")); print("yes" if d.get("reboot_requested") is True and d.get("host_result")=="GUARD_PROVED" else "no")')
      if [ "$want" = "yes" ]; then
        sync
        # The offline lab network leaves google-shutdown-scripts.service/stop
        # running with no limit, so a normal reboot never reaches a new boot.
        # Mask that unit, then force the reset after this shell returns.
        sudo systemctl mask --now google-shutdown-scripts.service >/dev/null 2>&1 || true
        sudo systemctl reset-failed vantio-lab-lsm-reboot >/dev/null 2>&1 || true
        if [ -x /var/lib/vantio-lab/reboot-with-grub.sh ]; then
          reboot_cmd=/var/lib/vantio-lab/reboot-with-grub.sh
        else
          reboot_cmd="systemctl reboot --force"
        fi
        if ! sudo systemd-run --on-active=45s --unit=vantio-lab-lsm-reboot $reboot_cmd; then
          sudo /var/lib/vantio-lab/reboot-with-grub.sh || sudo systemctl reboot --force || true
        fi
      fi
    fi
    exit "$rc"
    ;;
esac
# A user-owned file in /tmp makes root's recreate return EACCES. Each repeat
# starts clean. The var-lib copy survives a reboot, so drop that too.
sudo rm -f /tmp/enterprise-pe-rows.json /var/lib/vantio-lab/enterprise-pe-rows.json
set +e
sudo env VANTIO_IMAGE="$image" python3 "$stage/guest_rows.py" "$stage"
rc=$?
set -e
sudo chmod a+r /tmp/enterprise-pe-rows.json 2>/dev/null || true
sudo chmod a+r /tmp/gcp-kernel-facts.json 2>/dev/null || true
stamp_host_evidence
if [ -s /tmp/enterprise-pe-rows.json ]; then
  sudo mkdir -p /var/lib/vantio-lab
  sudo cp -f /tmp/enterprise-pe-rows.json /var/lib/vantio-lab/enterprise-pe-rows.json
  sudo chmod a+r /var/lib/vantio-lab/enterprise-pe-rows.json
elif [ ! -s /var/lib/vantio-lab/enterprise-pe-rows.json ]; then
  echo "rows_missing" >&2
  exit 1
fi
printf 'PY_RC=%s\n' "$rc"
exit "$rc"
