#!/bin/bash
# Verify the policy-allow seal and run the bundled Enterprise row script.
# The runner copies seal.oci.tar, contract.tar, and offline .debs into this
# directory over IAP. This host has no internet route. Package install uses
# only those .debs. This script does not fetch and it does not read a token.
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
case "$mode" in
  enterprise|descendant-b1|2c-upgrade-rollback|2d-crash-recovery) ;;
  *)
    echo "battery" >&2
    exit 2
    ;;
esac
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
python3 - <<'PY'
import json
import os
import pathlib
import subprocess

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
}
path = pathlib.Path("/tmp/gcp-kernel-facts.json")
path.write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
os.chmod(path, 0o644)
PY
load=$(sudo docker load -i "$here/seal.oci.tar" 2>&1)
printf '%s\n' "$load"
image=$(printf '%s\n' "$load" | sed -n 's/^Loaded image: //p' | tail -n 1)
test "$image" = "$image_name"
if [ "$mode" = "descendant-b1" ]; then
  printf 'IMAGE_LINE=%s\n' "$image"
  set +e
  sudo env VANTIO_IMAGE="$image" python3 "$here/descendant_b1.py" "$stage" "$phase" > /tmp/descendant-b1.out 2>&1
  rc=$?
  set -e
  cat /tmp/descendant-b1.out
  chmod a+r /tmp/descendant-b1.out 2>/dev/null || true
  if [ ! -s /tmp/enterprise-pe-rows.json ]; then
    cp /tmp/descendant-b1.out /tmp/enterprise-pe-rows.json
  fi
  chmod a+r /tmp/enterprise-pe-rows.json 2>/dev/null || true
  printf 'PY_RC=%s\n' "$rc"
  if [ "$phase" = "pre" ] && [ "$rc" -eq 0 ]; then
    sync
    sudo reboot || true
  fi
  exit "$rc"
fi
case "$mode" in
  2c-upgrade-rollback|2d-crash-recovery)
    test -f "$here/phase2_host.py"
    test -f "$here/phase2_grade.py"
    set +e
    sudo env VANTIO_IMAGE="$image" python3 "$here/phase2_host.py" "$stage" "$mode" > /tmp/phase2-host.out 2>&1
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
sudo chmod a+r /tmp/enterprise-pe-rows.json 2>/dev/null || true
sudo chmod a+r /tmp/gcp-kernel-facts.json 2>/dev/null || true
