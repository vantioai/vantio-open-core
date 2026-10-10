#!/bin/bash
# Stage docker.io, python3-cryptography, ca-certificates, and the CA bundle
# on the GitHub runner. The guest has no route. This script does not run there.
# The Debian image has no system certificates, so the first apt uses the
# image's default HTTP sources. The pinned snapshot is used only after that.
set -euo pipefail
dest=${1:?}
image=debian:12@sha256:bc49dc1918ee1a47a93e65b5e4676e8680fb754b133197b92ca52bfe6731d5f0
mkdir -p "$dest"
script=$(cat <<'EOS'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates
cat > /etc/apt/sources.list <<'EOF'
deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20261008T000000Z bookworm main
deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20261008T000000Z bookworm-updates main
deb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/20261008T000000Z bookworm-security main
EOF
rm -rf /etc/apt/sources.list.d
mkdir -p /etc/apt/sources.list.d
apt-get update
apt-get install -y --download-only --no-install-recommends docker.io python3-cryptography ca-certificates
cp /var/cache/apt/archives/*.deb /out/
cp /etc/ssl/certs/ca-certificates.crt /out/ca-certificates.crt
EOS
)
docker run --rm -v "$dest:/out" "$image" bash -c "$script"
find "$dest" -type f -name 'docker.io_*.deb' | grep -q .
find "$dest" -type f -name 'python3-cryptography_*.deb' | grep -q .
find "$dest" -type f -name 'ca-certificates_*.deb' | grep -q .
test -s "$dest/ca-certificates.crt"
