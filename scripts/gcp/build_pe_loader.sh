#!/bin/bash
# Build vantio-loader from the pinned Phantom Engine commit.
# This does not run scripts/enforcement_proof_lab.sh. bash -n does not attach a program.
# The proof guest is an e2-micro on Ubuntu 24.04. No fourth argument uses ubuntu:24.04.
# Stage 4 guests are e2-standard-2. debian13 uses debian:13 for Debian 13
# (kernel pin 6.12.116+deb13-cloud-amd64). ubuntu2604 uses ubuntu:26.04 for
# Ubuntu 26.04 (kernel pin 7.0.0-1016-gcp). The container is that distro's
# userspace. It is not a boot of the guest kernel. ubuntu:24.04 is not a
# stage 4 build host. No boot has shown a 24.04 binary runs on these guests.
# The git tip is not a seal digest.
set -euo pipefail

root=${1:?}
out=${2:?}
pin=${3:?}
guest=${4:-proof}
expected=864289cb2c9c4135d74233c74c6655087de3f20d
# Versions read 2026-11-12. cargo-binstall v1.27.0 from its GitHub release.
# bpf-linker 0.13.0 from crates.io. This script does not float either one.
binstall_tag=v1.27.0
bpf_linker_version=0.13.0

if [[ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" || -n "${GCP_SA_KEY:-}" ]]; then
  echo "static_credentials" >&2
  exit 1
fi
if [[ "$pin" != "$expected" ]]; then
  echo "pe_git_sha" >&2
  exit 1
fi
# Docker uses a slash-free -v source as a named volume. pwd -P is the checkout
# directory, and that absolute path is both the mount and cargo's workdir.
src=$(cd "$root" && pwd -P)
case "$src" in
  /src|/src/) echo "pe_src" >&2; exit 1 ;;
  /*) ;;
  *) echo "pe_src" >&2; exit 1 ;;
esac
head=$(git -C "$src" rev-parse HEAD)
if [[ "$head" != "$expected" ]]; then
  echo "pe_head" >&2
  exit 1
fi
if [[ -n "$(git -C "$src" status --porcelain)" ]]; then
  echo "pe_dirty" >&2
  exit 1
fi
test -f "$src/Cargo.toml"
test -f "$src/rust-toolchain.toml"
test -f "$src/vantio-loader/src/main.rs"
test -f "$src/scripts/enforcement_proof_lab.sh"
mkdir -p "$out"
out_dir=$(cd "$out" && pwd -P)
case "$out_dir" in
  /*) ;;
  *) echo "pe_out" >&2; exit 1 ;;
esac
case "$guest" in
  proof) image=ubuntu:24.04 ;;
  debian13) image=debian:13 ;;
  ubuntu2604) image=ubuntu:26.04 ;;
  *) echo "build_image" >&2; exit 1 ;;
esac

cp "$src/scripts/enforcement_proof_lab.sh" "$out_dir/enforcement_proof_lab.sh"
bash -n "$out_dir/enforcement_proof_lab.sh"
sha256sum "$out_dir/enforcement_proof_lab.sh" | awk '{print $1}' > "$out_dir/script.sha256"

binstall_url="https://github.com/cargo-bins/cargo-binstall/releases/download/${binstall_tag}/cargo-binstall-x86_64-unknown-linux-musl.tgz"
docker run --rm \
  -e "BINSTALL_URL=${binstall_url}" \
  -e "BPF_LINKER_VERSION=${bpf_linker_version}" \
  -v "$src:$src:ro" \
  -v "$out_dir:/out" \
  -w "$src" \
  "$image" \
  bash -c 'set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends build-essential ca-certificates curl pkg-config libssl-dev
curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain nightly --component rust-src
. "$HOME/.cargo/env"
curl -L --proto "=https" --tlsv1.2 -fsS -o /tmp/cargo-binstall.tgz "$BINSTALL_URL"
tar -tzf /tmp/cargo-binstall.tgz | grep -qx cargo-binstall
tar -C "$HOME/.cargo/bin" -xzf /tmp/cargo-binstall.tgz cargo-binstall
cargo binstall --no-confirm "bpf-linker@${BPF_LINKER_VERSION}"
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

if ! python3 -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); d=p.read_bytes(); sys.exit(0 if d[:4]==b"\x7fELF" and b"libssl" not in pathlib.Path(sys.argv[2]).read_bytes() else 1)' "$out_dir/vantio-loader" "$out_dir/ldd.txt"; then
  echo "loader_libs" >&2
  exit 1
fi
sha256sum "$out_dir/vantio-loader" | awk '{print $1}' > "$out_dir/loader.sha256"
echo "loader_built=1"
