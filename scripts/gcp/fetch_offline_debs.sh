#!/bin/bash
# Download docker.io and python3-cryptography, plus their dependencies, from
# one Debian snapshot. The guest has no internet route, so these .debs are the
# only packages it can install.
set -euo pipefail
dest=${1:?}
image=debian:12@sha256:bc49dc1918ee1a47a93e65b5e4676e8680fb754b133197b92ca52bfe6731d5f0
mkdir -p "$dest"
script=$(cat <<'EOS'
set -euo pipefail
cat > /etc/apt/sources.list <<'EOF'
deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20261008T000000Z bookworm main
deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20261008T000000Z bookworm-updates main
deb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/20261008T000000Z bookworm-security main
EOF
rm -rf /etc/apt/sources.list.d
mkdir -p /etc/apt/sources.list.d
apt-get update
apt-get install -y --download-only --no-install-recommends docker.io python3-cryptography
cp /var/cache/apt/archives/*.deb /out/
EOS
)
docker run --rm -v "$dest:/out" "$image" bash -c "$script"
find "$dest" -type f -name '*.deb' | grep -q .
