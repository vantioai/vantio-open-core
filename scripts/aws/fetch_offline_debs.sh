#!/bin/bash
# Download Ubuntu 24.04 packages on the GitHub runner.
# The lab host has no egress. The arm step copies these debs over SSH.
set -euo pipefail
dest=${1:?}
mkdir -p "$dest"
if ! command -v docker >/dev/null 2>&1; then
  echo "docker missing on runner" >&2
  exit 1
fi
docker run --rm -v "$dest:/out" ubuntu:24.04 bash -ceu '
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --download-only docker.io gcc python3-cryptography iptables
  cp -n /var/cache/apt/archives/*.deb /out/
  find /out -name "*.deb" | wc -l
'
find "$dest" -name "docker.io_*.deb" | grep -q .
find "$dest" -name "gcc_*.deb" | grep -q .
find "$dest" -name "python3-cryptography_*.deb" | grep -q .
find "$dest" -name "iptables_*.deb" | grep -q .
