#!/bin/bash
# Build vantio-loader from the pinned Phantom Engine commit.
# This does not run scripts/enforcement_proof_lab.sh. bash -n does not attach a program.
# The proof guest is an e2-micro on Ubuntu 24.04. No fourth argument uses
# the Ubuntu 24.04 image. Stage 4 guests are e2-standard-2. debian13 uses
# the Debian 13 image (kernel pin 6.12.116+deb13-cloud-amd64). ubuntu2604
# uses the Ubuntu 26.04 image (kernel pin 7.0.0-1016-gcp). Each image is
# tag@sha256 of the linux/amd64 manifest. The container is that distro's
# userspace. It is not a boot of the guest kernel. The Ubuntu 24.04 image
# is not a stage 4 build host. No boot has shown a 24.04 binary runs on
# these guests.
# The git tip is not a seal digest.
# Digests below are sha256 of the release bytes read 2026-11-12.
# The same bpf-linker bytes hashed the same way a second time.
# Checking the digest is not a boot, and it does not make this
# container a match for the guest kernel.
set -euo pipefail

root=${1:?}
out=${2:?}
pin=${3:?}
guest=${4:-proof}
expected=864289cb2c9c4135d74233c74c6655087de3f20d
# Versions read 2026-11-12. cargo-binstall v1.27.0 from its GitHub release.
# bpf-linker 0.13.0 is the musl release archive, not a crates.io fetch.
# This script does not float either one. sha256 is checked before extract.
binstall_tag=v1.27.0
binstall_sha256=b2e4b70fcddc5bd6fd90c5cf8dc17b4cf0ea54a3db16c65ee0307f42c9bd3187
bpf_linker_version=0.13.0
bpf_linker_sha256=0e9b2b30f68898177f1cb6f0ecbfa909a82479473a49a0ef66529fd088e3e410
# linux/amd64 manifest digests read from registry-1.docker.io on 2026-11-12.
# The tag index digests that day were ubuntu:24.04
# sha256:2198e4c65076e9cb0b3d695219df667c0e3b0072da64ca3c2648aca17dcecaf5,
# debian:13 sha256:9c6e381421d0f48d1b8133e573f33c185ee16cbf505eda9c4a8a4791b25ea8a6,
# and ubuntu:26.04 sha256:065aa8626841f16057b78b027b464cd59c4fac36c204c72dcbf48d66f5fa8a96.
# The pin below is the amd64 manifest those indexes named, not the index.
ubuntu_2404_image=ubuntu:24.04@sha256:77eb101c607d6e3d4f5ad0c8a02c2136c689b98aba1f359e6502ba517e5c57ec
debian_13_image=debian:13@sha256:bfc36aecdece0387418759dba474aa856c026ca8087da3606b41b90ab0509c99
ubuntu_2604_image=ubuntu:26.04@sha256:0d5255be560e2d2ddcfbfda88549e9e815ef29e7cd7fc62183d5709e6e2963c6
# rustup 1.29.3 is the version in static.rust-lang.org/rustup/release-stable.toml
# on 2026-11-12. The sha256 is that archive's rustup-init.sha256 and the
# hash of the downloaded binary. nightly-2026-11-12 is the channel date
# in static.rust-lang.org/dist/2026-11-12/channel-rust-nightly.toml
# (rustc 1.102.0-nightly, 3ef0c22cd). Apt is the snapshot at the timestamp,
# not the live mirror.
rustup_version=1.29.3
rustup_sha256=b1c8cb14e30889e7e2999e6b69e62d9e9b9ffc0f4df8180564d306d9680e6c55
rustup_toolchain=nightly-2026-11-12
ubuntu_snapshot=https://snapshot.ubuntu.com/ubuntu/20261111T000000Z
debian_snapshot=https://snapshot.debian.org/archive/debian/20261112T025704Z
debian_security_snapshot=https://snapshot.debian.org/archive/debian-security/20261112T025704Z

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
ubuntu_opt='[check-valid-until=no signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg]'
debian_opt='[check-valid-until=no signed-by=/usr/share/keyrings/debian-archive-keyring.gpg]'
case "$guest" in
  proof)
    image=$ubuntu_2404_image
    apt_sources=$(printf '%s\n' \
      "deb ${ubuntu_opt} ${ubuntu_snapshot} noble main universe" \
      "deb ${ubuntu_opt} ${ubuntu_snapshot} noble-updates main universe" \
      "deb ${ubuntu_opt} ${ubuntu_snapshot} noble-security main universe")
    ;;
  debian13)
    image=$debian_13_image
    apt_sources=$(printf '%s\n' \
      "deb ${debian_opt} ${debian_snapshot} trixie main" \
      "deb ${debian_opt} ${debian_snapshot} trixie-updates main" \
      "deb ${debian_opt} ${debian_security_snapshot} trixie-security main")
    ;;
  ubuntu2604)
    image=$ubuntu_2604_image
    apt_sources=$(printf '%s\n' \
      "deb ${ubuntu_opt} ${ubuntu_snapshot} resolute main universe" \
      "deb ${ubuntu_opt} ${ubuntu_snapshot} resolute-updates main universe" \
      "deb ${ubuntu_opt} ${ubuntu_snapshot} resolute-security main universe")
    ;;
  *) echo "build_image" >&2; exit 1 ;;
esac

cp "$src/scripts/enforcement_proof_lab.sh" "$out_dir/enforcement_proof_lab.sh"
bash -n "$out_dir/enforcement_proof_lab.sh"
sha256sum "$out_dir/enforcement_proof_lab.sh" | awk '{print $1}' > "$out_dir/script.sha256"

binstall_url="https://github.com/cargo-bins/cargo-binstall/releases/download/${binstall_tag}/cargo-binstall-x86_64-unknown-linux-musl.tgz"
bpf_linker_url="https://github.com/aya-rs/bpf-linker/releases/download/v${bpf_linker_version}/bpf-linker-x86_64-unknown-linux-musl.tar.zst"
rustup_url="https://static.rust-lang.org/rustup/archive/${rustup_version}/x86_64-unknown-linux-gnu/rustup-init"
docker run --rm \
  -e "BINSTALL_URL=${binstall_url}" \
  -e "BINSTALL_SHA256=${binstall_sha256}" \
  -e "BPF_LINKER_URL=${bpf_linker_url}" \
  -e "BPF_LINKER_SHA256=${bpf_linker_sha256}" \
  -e "RUSTUP_URL=${rustup_url}" \
  -e "RUSTUP_SHA256=${rustup_sha256}" \
  -e "RUSTUP_TOOLCHAIN=${rustup_toolchain}" \
  -e "APT_SOURCES=${apt_sources}" \
  -v "$src:$src:ro" \
  -v "$out_dir:/out" \
  -w "$src" \
  "$image" \
  bash -c 'set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
rm -rf /etc/apt/sources.list.d
mkdir -p /etc/apt/sources.list.d
printf "Acquire::Check-Valid-Until \"false\";\n" > /etc/apt/apt.conf.d/99snapshot
printf "%s\n" "$APT_SOURCES" > /etc/apt/sources.list
apt-get update
apt-get install -y --no-install-recommends build-essential ca-certificates curl pkg-config libssl-dev zstd
curl -L --proto "=https" --tlsv1.2 -fsS -o /tmp/rustup-init "$RUSTUP_URL"
printf "%s  %s\n" "$RUSTUP_SHA256" /tmp/rustup-init | sha256sum -c -
chmod 0755 /tmp/rustup-init
/tmp/rustup-init -y --default-toolchain "$RUSTUP_TOOLCHAIN" --component rust-src --default-host x86_64-unknown-linux-gnu --no-modify-path
. "$HOME/.cargo/env"
export RUSTUP_TOOLCHAIN
curl -L --proto "=https" --tlsv1.2 -fsS -o /tmp/cargo-binstall.tgz "$BINSTALL_URL"
printf "%s  %s\n" "$BINSTALL_SHA256" /tmp/cargo-binstall.tgz | sha256sum -c -
tar -tzf /tmp/cargo-binstall.tgz | grep -qx cargo-binstall
tar -C "$HOME/.cargo/bin" -xzf /tmp/cargo-binstall.tgz cargo-binstall
curl -L --proto "=https" --tlsv1.2 -fsS -o /tmp/bpf-linker.tar.zst "$BPF_LINKER_URL"
printf "%s  %s\n" "$BPF_LINKER_SHA256" /tmp/bpf-linker.tar.zst | sha256sum -c -
tar --zstd -tf /tmp/bpf-linker.tar.zst | grep -qx bpf-linker
tar --zstd -C "$HOME/.cargo/bin" -xf /tmp/bpf-linker.tar.zst bpf-linker
chmod 0755 "$HOME/.cargo/bin/cargo-binstall" "$HOME/.cargo/bin/bpf-linker"
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
