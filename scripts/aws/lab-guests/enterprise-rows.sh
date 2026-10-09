#!/bin/bash
# Verify the policy-allow seal and run the bundled Enterprise row script.
# The runner copies seal.oci.tar and contract.tar into this directory over
# the Instance Connect session. This script does not fetch either file and
# it does not read a token.
set -euo pipefail
seal=${1:?}
here=$(cd "$(dirname "$0")" && pwd)
stage=/opt/vantio-enterprise
image_name=vantio-phantom-engine:policy-allow-df61d97
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
sudo chown -R ubuntu:ubuntu "$stage"
if find "$stage" -name 'private-key.pem' | grep -q .; then
  exit 3
fi
sudo DEBIAN_FRONTEND=noninteractive apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-cryptography docker.io
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "linux-tools-$(uname -r)" linux-tools-common || true
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
  sudo env VANTIO_IMAGE="$image" python3 "$here/descendant_b1.py" "$stage" "$phase"
  rc=$?
  if [ "$phase" = "pre" ]; then
    sync
    sudo reboot || true
  fi
  exit "$rc"
fi
sudo env VANTIO_IMAGE="$image" python3 "$stage/guest_rows.py" "$stage"
