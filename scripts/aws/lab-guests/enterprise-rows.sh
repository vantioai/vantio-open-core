#!/bin/bash
# Verify the policy-allow seal and run the bundled Enterprise row script.
# The runner copies seal.oci.tar and contract.tar into this directory over
# the Instance Connect session. This script does not fetch either file and
# it does not read a token.
set -euo pipefail
seal=${1:?}
here=$(cd "$(dirname "$0")" && pwd)
stage=/opt/vantio-enterprise
image_name=vantio-phantom-engine:decision-6f32467
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
load=$(sudo docker load -i "$here/seal.oci.tar" 2>&1)
printf '%s\n' "$load"
image=$(printf '%s\n' "$load" | sed -n 's/^Loaded image: //p' | tail -n 1)
test "$image" = "$image_name"

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
    python3 - "$here/sticky_write.py" << 'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve().parent))
from sticky_write import write_replacing

rows = Path("/tmp/enterprise-pe-rows.json")
try:
    body = json.loads(rows.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    body = {}
out = Path("/tmp/vantio-uninstall.out")
body["uninstall_tail"] = out.read_text(encoding="utf-8", errors="replace")[-1200:] if out.is_file() else ""
write_replacing(rows, json.dumps(body))
PY
    chmod a+r /tmp/enterprise-pe-rows.json 2>/dev/null || true
  }
  trap record_uninstall RETURN
  if ! ensure_working_bpftool; then
    echo "UNINSTALL_RESIDUAL bpftool missing" >&2
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
  sudo env PATH="$PATH" /var/lib/vantio/vantio-loader --uninstall --confirm uninstall --enterprise-approval "$token" >/tmp/vantio-uninstall.out 2>&1
  local urc=$?
  set -e
  cat /tmp/vantio-uninstall.out
  if ! grep -qx 'UNINSTALL_VERIFIED' /tmp/vantio-uninstall.out; then
    echo "UNINSTALL_NOT_VERIFIED rc=$urc" >&2
    return 1
  fi
  if find /sys/fs/bpf -maxdepth 2 -name 'vantio*' -print 2>/dev/null | grep -q .; then
    echo "UNINSTALL_RESIDUAL bpffs" >&2
    find /sys/fs/bpf -maxdepth 2 -name 'vantio*' >&2 || true
    return 1
  fi
  if [ "$require_row" = "yes" ]; then
    python3 - "$probe_pid" /tmp/vantio-uninstall.out /var/log/vantio/uninstall.ndjson /var/lib/vantio-pe-clean-host/evidence/events.ndjson <<'PY'
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

mode=${2:-enterprise}
phase=${3:-pre}
if [ "$mode" = "descendant-b1" ]; then
  if [ -f "$here/descendant_probe.c" ] && command -v gcc >/dev/null; then
    gcc -O2 -o "$here/descendant_probe" "$here/descendant_probe.c"
  fi
  test -x "$here/descendant_probe"
  printf 'IMAGE_LINE=%s\n' "$image"
  set +e
  sudo env VANTIO_IMAGE="$image" VANTIO_PROBE="$here/descendant_probe" python3 "$here/descendant_b1.py" "$stage" "$phase" > /tmp/descendant-b1.out 2>&1
  rc=$?
  set -e
  cat /tmp/descendant-b1.out
  chmod a+r /tmp/descendant-b1.out 2>/dev/null || true
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
  if [ "$phase" = "pre" ] && [ "$rc" -eq 0 ]; then
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
  2c-upgrade-rollback|2d-crash-recovery|2e-performance|2f-tamper|2g-distro)
    set +e
    sudo env VANTIO_IMAGE="$image" VANTIO_IMAGE_ID="${VANTIO_IMAGE_ID:-}" VANTIO_EGRESS_HOST="${VANTIO_EGRESS_HOST:-}" VANTIO_EGRESS_PORT="${VANTIO_EGRESS_PORT:-}" python3 "$here/phase2_host.py" "$stage" "$mode" > /tmp/phase2-host.out 2>&1
    rc=$?
    set -e
    cat /tmp/phase2-host.out
    chmod a+r /tmp/phase2-host.out /tmp/enterprise-pe-rows.json 2>/dev/null || true
    if [ ! -s /tmp/enterprise-pe-rows.json ]; then
      cp /tmp/phase2-host.out /tmp/enterprise-pe-rows.json
    fi
    printf 'PY_RC=%s\n' "$rc"
    require_row=no
    probe_pid=0
    if [ "$mode" = "2f-tamper" ]; then
      require_row=yes
      if [ -s /tmp/enterprise-pe-rows.json ]; then
        probe_pid=$(python3 -c 'import json; d=json.load(open("/tmp/enterprise-pe-rows.json")); e=d.get("enrolled_after") or {}; p=e.get("pid") or 0; print(p if isinstance(p, int) else 0)')
      fi
    fi
    if ! authorized_uninstall "$image" "$require_row" "$probe_pid"; then
      exit 1
    fi
    exit "$rc"
    ;;
esac
set +e
sudo rm -f /tmp/enterprise-pe-rows.json
sudo env VANTIO_IMAGE="$image" python3 "$stage/guest_rows.py" "$stage"
rc=$?
set -e
if ! authorized_uninstall "$image" no 0; then
  exit 1
fi
exit "$rc"
