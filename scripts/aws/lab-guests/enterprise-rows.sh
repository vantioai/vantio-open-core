#!/bin/bash
# Verify the policy-allow seal and run the bundled Enterprise row script.
# The runner copies seal.oci.tar and contract.tar into this directory over
# the Instance Connect session. This script does not fetch either file and
# it does not read a token.
set -euo pipefail
seal=${1:?}
here=$(cd "$(dirname "$0")" && pwd)
stage=/opt/vantio-enterprise
image_name=vantio-phantom-engine:loader-kill-3ee6b2a
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
mode=${2:-enterprise}
phase=${3:-pre}
if [ "$mode" = "descendant-b1" ]; then
  command -v gcc >/dev/null
  gcc -O2 -o "$here/descendant_probe" "$here/descendant_probe.c"
  printf 'IMAGE_LINE=%s\n' "$image"
  set +e
  sudo env VANTIO_IMAGE="$image" VANTIO_PROBE="$here/descendant_probe" python3 "$here/descendant_b1.py" "$stage" "$phase" > /tmp/descendant-b1.out 2>&1
  rc=$?
  set -e
  cat /tmp/descendant-b1.out
  chmod a+r /tmp/descendant-b1.out 2>/dev/null || true
  if [ ! -s /tmp/enterprise-pe-rows.json ]; then
    cp /tmp/descendant-b1.out /tmp/enterprise-pe-rows.json
  fi
  chmod a+r /tmp/enterprise-pe-rows.json 2>/dev/null || true
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
    sudo reboot || true
  fi
  exit "$rc"
fi
case "$mode" in
  2c-upgrade-rollback|2d-crash-recovery|2e-performance|2f-tamper|2g-distro)
    set +e
    sudo env VANTIO_IMAGE="$image" VANTIO_IMAGE_ID="${VANTIO_IMAGE_ID:-}" python3 "$here/phase2_host.py" "$stage" "$mode" > /tmp/phase2-host.out 2>&1
    rc=$?
    set -e
    cat /tmp/phase2-host.out
    chmod a+r /tmp/phase2-host.out /tmp/enterprise-pe-rows.json 2>/dev/null || true
    if [ ! -s /tmp/enterprise-pe-rows.json ]; then
      cp /tmp/phase2-host.out /tmp/enterprise-pe-rows.json
    fi
    printf 'PY_RC=%s\n' "$rc"
    exit "$rc"
    ;;
esac
sudo env VANTIO_IMAGE="$image" python3 "$stage/guest_rows.py" "$stage"
