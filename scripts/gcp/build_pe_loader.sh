#!/bin/bash
# Build vantio-loader from the pinned Phantom Engine commit.
# This does not run scripts/enforcement_proof_lab.sh. bash -n does not attach a program.
# The guest is an e2-micro. The compile runs in a digest-pinned ubuntu:24.04
# container so the binary matches that guest's glibc. The git tip is not a seal digest.
#
# bpf-linker stays at 0.12.0. Rust stays nightly-2026-10-13. A dated channel
# in rust-toolchain.toml is recorded and not used. Apt packages come from
# Ubuntu snapshot 20261110T000000Z. SOURCE_DATE_EPOCH=0. --remap-path-prefix
# and -ffile-prefix-map rewrite the checkout (/vantio-src), the cargo home
# (/cargo), the rustc sysroot (/rustc), and the host prefixes /usr, /lib,
# /opt, /tmp, and /root. vantio-loader/build.rs replaces RUSTFLAGS for the
# eBPF crate and only remaps the first three, so the container wraps rustc
# and appends the host prefixes. That is what keeps .BTF strings off this machine.
set -euo pipefail

root=${1:?}
out=${2:?}
pin=${3:?}
# The expected tip is the single line in pe-pin.txt, next to this script.
# A new tree is a new line in that file plus this script's first argument.
# BASH_SOURCE, not pwd. A caller can override pwd without moving this file.
pin_file="${BASH_SOURCE[0]%/*}/pe-pin.txt"
expected="$(tr -d '[:space:]' < "$pin_file")"
RUST_TOOLCHAIN=nightly-2026-10-13
BPF_LINKER_VERSION=0.12.0
UBUNTU_IMAGE=ubuntu:24.04@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852
APT_SNAPSHOT=20261110T000000Z

writable=""
cleanup_writable() {
  if [[ -z "${writable:-}" || ! -d "$writable" ]]; then
    return 0
  fi
  chown -R "$(id -u):$(id -g)" "$writable" >/dev/null 2>&1 || true
  rm -rf "$writable" >/dev/null 2>&1 || true
}
# The trap is installed before the guards so a failed pin, dirty tree, or
# compile still chowns and removes the writable target.
trap cleanup_writable EXIT

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
if git -C "$src" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  head=$(git -C "$src" rev-parse HEAD)
  if [[ "$head" != "$expected" ]]; then
    echo "pe_head" >&2
    exit 1
  fi
else
  # The attached tree had remotes stripped and no .git. The pin argument
  # already matched expected. A real checkout still has to match HEAD.
  echo "pe_snapshot=1"
  echo "pe_head_unverified=${expected}"
fi
# assume-unchanged and skip-worktree hide edits from a status listing.
# Lowercase ls-files tags are assume-unchanged. S is skip-worktree. A fresh
# index from read-tree does not carry those bits, so diff still sees the edit.
worktree_dirty() {
  local src="$1"
  local flags index_file
  flags="$(git -C "$src" ls-files -v)" || return 0
  if printf '%s\n' "$flags" | awk '
    BEGIN { found = 0 }
    {
      tag = substr($0, 1, 1)
      if (tag ~ /[a-z]/ || tag == "S") found = 1
    }
    END { exit found ? 0 : 1 }
  '; then
    return 0
  fi
  index_file="$(mktemp)"
  if ! GIT_INDEX_FILE="$index_file" git -C "$src" read-tree HEAD; then
    rm -f "$index_file" || true
    return 0
  fi
  if ! GIT_INDEX_FILE="$index_file" git -C "$src" diff --no-ext-diff --exit-code HEAD --; then
    rm -f "$index_file" || true
    return 0
  fi
  rm -f "$index_file" || true
  if [[ -n "$(git -C "$src" ls-files --others --exclude-standard)" ]]; then
    return 0
  fi
  return 1
}
if git -C "$src" rev-parse --is-inside-work-tree >/dev/null 2>&1 && worktree_dirty "$src"; then
  echo "pe_dirty" >&2
  exit 1
fi
test -f "$src/Cargo.toml"
test -f "$src/rust-toolchain.toml"
# The checkout channel is logged. It does not select the compiler.
file_channel="$(awk -F'"' '/^[[:space:]]*channel[[:space:]]*=/ { print $2; exit }' "$src/rust-toolchain.toml")"
echo "rust_toolchain_file=${file_channel}"
test -f "$src/vantio-loader/src/main.rs"
test -f "$src/scripts/enforcement_proof_lab.sh"
mkdir -p "$out"
out_dir=$(cd "$out" && pwd -P)
case "$out_dir" in
  /*) ;;
  *) echo "pe_out" >&2; exit 1 ;;
esac
cp "$src/scripts/enforcement_proof_lab.sh" "$out_dir/enforcement_proof_lab.sh"
bash -n "$out_dir/enforcement_proof_lab.sh"
sha256sum "$out_dir/enforcement_proof_lab.sh" | awk '{print $1}' > "$out_dir/script.sha256"

# build.rs writes the eBPF object under $src/target. The checkout mount is
# read-only, so that path has to exist and a writable directory is mounted on it.
mkdir -p "$src/target"
writable=$(mktemp -d /tmp/pe-target.XXXXXX)
case "$writable" in
  "$src"|"$src"/*) echo "pe_target" >&2; exit 1 ;;
  /*) ;;
  *) echo "pe_target" >&2; exit 1 ;;
esac
case "$src" in
  "$writable"|"$writable"/*) echo "pe_target" >&2; exit 1 ;;
esac

cache_args=()
if [[ -n "${PE_BUILD_CACHE:-}" ]]; then
  mkdir -p "${PE_BUILD_CACHE}/rustup" "${PE_BUILD_CACHE}/cargo"
  cache_args+=(-v "${PE_BUILD_CACHE}/rustup:/root/.rustup" -v "${PE_BUILD_CACHE}/cargo:/root/.cargo")
fi
docker run --rm \
  "${cache_args[@]}" \
  -e "HOST_UID=$(id -u)" \
  -e "HOST_GID=$(id -g)" \
  -e "RUST_TOOLCHAIN=${RUST_TOOLCHAIN}" \
  -e "BPF_LINKER_VERSION=${BPF_LINKER_VERSION}" \
  -e "APT_SNAPSHOT=${APT_SNAPSHOT}" \
  -v "$src:$src:ro" \
  -v "$writable:$src/target" \
  -v "$out_dir:/out" \
  -w "$src" \
  "$UBUNTU_IMAGE" \
  bash -c 'set -euo pipefail
cleanup_target() {
  if [ -n "${HOST_UID:-}" ] && [ -n "${HOST_GID:-}" ]; then
    chown -R "${HOST_UID}:${HOST_GID}" "$(pwd)/target" /out >/dev/null 2>&1 || true
  fi
}
trap cleanup_target EXIT
export DEBIAN_FRONTEND=noninteractive
export RUSTUP_TOOLCHAIN="${RUST_TOOLCHAIN}"
export CARGO_INCREMENTAL=0
apt-get update
apt-get install -y --no-install-recommends ca-certificates
rm -f /etc/apt/sources.list.d/*
printf "%s\n" \
  "deb https://snapshot.ubuntu.com/ubuntu/${APT_SNAPSHOT} noble main universe restricted multiverse" \
  "deb https://snapshot.ubuntu.com/ubuntu/${APT_SNAPSHOT} noble-updates main universe restricted multiverse" \
  "deb https://snapshot.ubuntu.com/ubuntu/${APT_SNAPSHOT} noble-security main universe restricted multiverse" \
  > /etc/apt/sources.list
apt-get update
apt-get install -y --no-install-recommends build-essential curl pkg-config libssl-dev
curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain "${RUST_TOOLCHAIN}" --component rust-src --profile minimal
. "$HOME/.cargo/env"
curl -L --proto "=https" --tlsv1.2 -sSf https://raw.githubusercontent.com/cargo-bins/cargo-binstall/main/install-from-binstall-release.sh | bash
# binstall asks the GitHub API, which answers 403 when the quota is spent
# and then compiles bpf-linker from source. That compile needs llvm-config,
# which this image does not have, and a source build is not the 0.12.0
# release binary. On that failure, take the musl release asset directly.
if ! timeout 60 cargo binstall --no-confirm "bpf-linker@${BPF_LINKER_VERSION}"; then
  apt-get install -y --no-install-recommends zstd
  curl -L --proto "=https" --tlsv1.2 -fsS \
    -o /tmp/bpf-linker.tar.zst \
    "https://github.com/aya-rs/bpf-linker/releases/download/v${BPF_LINKER_VERSION}/bpf-linker-x86_64-unknown-linux-musl.tar.zst"
  tar -C "$HOME/.cargo/bin" --zstd -xf /tmp/bpf-linker.tar.zst
  chmod 0755 "$HOME/.cargo/bin/bpf-linker"
fi
active="$(rustup show active-toolchain)"
case "$active" in
  "${RUST_TOOLCHAIN}"*) ;;
  *) echo rust_toolchain >&2; exit 1 ;;
esac
linker_line="$(bpf-linker --version 2>&1 || true)"
case "$linker_line" in
  *"${BPF_LINKER_VERSION}"*) ;;
  *) echo bpf_linker_version >&2; exit 1 ;;
esac
{
  printf "rust_toolchain=%s\n" "$active"
  printf "bpf_linker=%s\n" "$linker_line"
  printf "apt_snapshot=%s\n" "${APT_SNAPSHOT}"
} > /out/toolchain.txt
export CARGO_HOME=/tmp/cargo
export CARGO_TARGET_DIR="$(pwd)/target"
export SOURCE_DATE_EPOCH=0
sysroot="$(rustc +"${RUST_TOOLCHAIN}" --print sysroot)"
# build.rs sets RUSTFLAGS itself and drops the host prefixes. The wrapper
# appends them on every compile, including the eBPF crate that emits .BTF.
# A cached toolchain must not wrap the wrapper. That loop never returns.
if grep -q vantio-rustc-wrapper "${sysroot}/bin/rustc.real" 2>/dev/null; then
  rustup toolchain uninstall "${RUST_TOOLCHAIN}"
  rustup toolchain install "${RUST_TOOLCHAIN}" --component rust-src --profile minimal
  sysroot="$(rustc +"${RUST_TOOLCHAIN}" --print sysroot)"
fi
if [ ! -e "${sysroot}/bin/rustc.real" ]; then
  mv "${sysroot}/bin/rustc" "${sysroot}/bin/rustc.real"
fi
{
  echo "#!/bin/bash"
  echo "# vantio-rustc-wrapper"
  echo "set -euo pipefail"
  echo "real=\"\$(dirname \"\$0\")/rustc.real\""
  echo "case \"\${1:-}\" in"
  echo "  --version|-vV|--print) exec \"\$real\" \"\$@\" ;;"
  echo "esac"
  echo "exec \"\$real\" \"\$@\" --remap-path-prefix=/usr=/sysroot-usr --remap-path-prefix=/lib=/sysroot-lib --remap-path-prefix=/opt=/sysroot-opt --remap-path-prefix=/tmp=/build-tmp --remap-path-prefix=/root=/home-root"
} > "${sysroot}/bin/rustc"
chmod 0755 "${sysroot}/bin/rustc"
cargo_home="${CARGO_HOME}"
checkout="$(pwd)"
remap="--remap-path-prefix=${checkout}=/vantio-src --remap-path-prefix=${cargo_home}=/cargo --remap-path-prefix=${sysroot}=/rustc --remap-path-prefix=/usr=/sysroot-usr --remap-path-prefix=/lib=/sysroot-lib --remap-path-prefix=/opt=/sysroot-opt --remap-path-prefix=/tmp=/build-tmp --remap-path-prefix=/root=/home-root"
export RUSTFLAGS="${remap}"
# ring compiles C and assembly. RUSTFLAGS do not rewrite those .file paths.
export CFLAGS="-ffile-prefix-map=${checkout}=/vantio-src -ffile-prefix-map=${cargo_home}=/cargo -ffile-prefix-map=${sysroot}=/rustc -ffile-prefix-map=/usr=/sysroot-usr -ffile-prefix-map=/lib=/sysroot-lib -ffile-prefix-map=/opt=/sysroot-opt -ffile-prefix-map=/tmp=/build-tmp -ffile-prefix-map=/root=/home-root -fdebug-prefix-map=/usr=/sysroot-usr -fmacro-prefix-map=/usr=/sysroot-usr -frandom-seed=vantio-loader"
export CXXFLAGS="${CFLAGS}"
cargo +"${RUST_TOOLCHAIN}" build -p vantio-loader --release --locked
install -m 0755 "$(pwd)/target/release/vantio-loader" /out/vantio-loader
ebpf="$(pwd)/target/bpfel-unknown-none/release/vantio-phantom-engine"
if [ -f "$ebpf" ]; then
  install -m 0644 "$ebpf" /out/vantio-phantom-engine
fi
if ldd /out/vantio-loader | grep -E "libssl|libcrypto"; then
  echo loader_libs >&2
  exit 1
fi
ldd /out/vantio-loader > /out/ldd.txt || true
if [ -n "${HOST_UID:-}" ] && [ -n "${HOST_GID:-}" ]; then
  chown -R "${HOST_UID}:${HOST_GID}" "$(pwd)/target" /out
fi
'

if ! python3 -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); d=p.read_bytes(); sys.exit(0 if d[:4]==b"\x7fELF" and b"libssl" not in pathlib.Path(sys.argv[2]).read_bytes() else 1)' "$out_dir/vantio-loader" "$out_dir/ldd.txt"; then
  echo "loader_libs" >&2
  exit 1
fi
sha256sum "$out_dir/vantio-loader" | awk '{print $1}' > "$out_dir/loader.sha256"
echo "rust_toolchain=${RUST_TOOLCHAIN}"
echo "bpf_linker=${BPF_LINKER_VERSION}"
echo "loader_built=1"
