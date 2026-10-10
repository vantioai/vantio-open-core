#!/bin/bash
# Stage docker.io, python3-cryptography, ca-certificates, and the CA bundle
# on the GitHub runner. The guest has no route. This script does not run there.
# Packages come from the Ubuntu 24.04 snapshot so the guest Docker knows CAP_BPF.
set -euo pipefail
dest=${1:?}
image=ubuntu:24.04
mkdir -p "$dest"
script=$(cat <<'EOS'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates
cat > /etc/apt/sources.list <<'EOF'
deb [check-valid-until=no] https://snapshot.ubuntu.com/ubuntu/20261008T000000Z noble main universe
deb [check-valid-until=no] https://snapshot.ubuntu.com/ubuntu/20261008T000000Z noble-updates main universe
deb [check-valid-until=no] https://snapshot.ubuntu.com/ubuntu/20261008T000000Z noble-security main universe
EOF
rm -rf /etc/apt/sources.list.d
mkdir -p /etc/apt/sources.list.d
apt-get update
apt-get install -y --download-only --no-install-recommends docker.io python3-cryptography ca-certificates
rm -f /var/cache/apt/archives/ca-certificates_*.deb
( cd /var/cache/apt/archives && apt-get download ca-certificates )
cp /var/cache/apt/archives/*.deb /out/
cp /etc/ssl/certs/ca-certificates.crt /out/ca-certificates.crt
EOS
)
docker run --rm -v "$dest:/out" "$image" bash -c "$script"
find "$dest" -type f -name 'docker.io_*.deb' | grep -q .
find "$dest" -type f -name 'python3-cryptography_*.deb' | grep -q .
find "$dest" -type f -name 'ca-certificates_*.deb' | grep -q .
test -s "$dest/ca-certificates.crt"
