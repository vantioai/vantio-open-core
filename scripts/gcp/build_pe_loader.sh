#!/bin/bash
# Build vantio-loader from the pinned Phantom Engine commit.
# This does not run scripts/enforcement_proof_lab.sh. bash -n does not attach a program.
# The guest is an e2-micro. The compile runs in an ubuntu:24.04 container so the
# binary matches that guest's glibc. The git tip is not a seal digest.
set -euo pipefail

root=${1:?}
out=${2:?}
pin=${3:?}
expected=864289cb2c9c4135d74233c74c6655087de3f20d

if [[ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" || -n "${GCP_SA_KEY:-}" ]]; then
  echo "static_credentials" >&2
  exit 1
fi
if [[ "$pin" != "$expected" ]]; then
  echo "pe_git_sha" >&2
  exit 1
fi
head=$(git -C "$root" rev-parse HEAD)
if [[ "$head" != "$expected" ]]; then
  echo "pe_head" >&2
  exit 1
fi
if [[ -n "$(git -C "$root" status --porcelain)" ]]; then
  echo "pe_dirty" >&2
  exit 1
fi
test -f "$root/Cargo.toml"
test -f "$root/rust-toolchain.toml"
test -f "$root/vantio-loader/src/main.rs"
test -f "$root/scripts/enforcement_proof_lab.sh"
mkdir -p "$out"
cp "$root/scripts/enforcement_proof_lab.sh" "$out/enforcement_proof_lab.sh"
bash -n "$out/enforcement_proof_lab.sh"
sha256sum "$out/enforcement_proof_lab.sh" | awk '{print $1}' > "$out/script.sha256"

docker run --rm \
  -v "$root:/src:ro" \
  -v "$out:/out" \
  ubuntu:24.04 \
  bash -c 'set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends build-essential ca-certificates curl pkg-config libssl-dev
curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain nightly --component rust-src
. "$HOME/.cargo/env"
curl -L --proto "=https" --tlsv1.2 -sSf https://raw.githubusercontent.com/cargo-bins/cargo-binstall/main/install-from-binstall-release.sh | bash
cargo binstall --no-confirm bpf-linker
cd /src
export CARGO_HOME=/tmp/cargo
export CARGO_TARGET_DIR=/tmp/target
cargo build -p vantio-loader --release
install -m 0755 /tmp/target/release/vantio-loader /out/vantio-loader
if ldd /out/vantio-loader | grep -E "libssl|libcrypto"; then
  echo "loader_libs" >&2
  exit 1
fi
ldd /out/vantio-loader > /out/ldd.txt || true
'

if ! python3 -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); d=p.read_bytes(); sys.exit(0 if d[:4]==b"\x7fELF" and b"libssl" not in pathlib.Path(sys.argv[2]).read_bytes() else 1)' "$out/vantio-loader" "$out/ldd.txt"; then
  echo "loader_libs" >&2
  exit 1
fi
sha256sum "$out/vantio-loader" | awk '{print $1}' > "$out/loader.sha256"
echo "loader_built=1"
