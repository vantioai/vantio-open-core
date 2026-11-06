#!/bin/bash
# Build vantio-loader from the pinned Phantom Engine commit.
# This does not run scripts/enforcement_proof_lab.sh. bash -n does not attach a program.
# The guest is an e2-micro. The compile runs in an ubuntu:24.04 container so the
# binary matches that guest's glibc. The git tip is not a seal digest.
#
# Rust and bpf-linker are pinned. bpf-linker 0.12.0 is built against the LLVM
# in nightly-2026-10-13. The checkout's rust-toolchain.toml says "nightly";
# RUSTUP_TOOLCHAIN and cargo + override that file.
set -euo pipefail

root=${1:?}
out=${2:?}
pin=${3:?}
expected=864289cb2c9c4135d74233c74c6655087de3f20d
RUST_TOOLCHAIN=nightly-2026-10-13
BPF_LINKER_VERSION=0.12.0

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
head=$(git -C "$src" rev-parse HEAD)
if [[ "$head" != "$expected" ]]; then
  echo "pe_head" >&2
  exit 1
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
if worktree_dirty "$src"; then
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

docker run --rm \
  -e "HOST_UID=$(id -u)" \
  -e "HOST_GID=$(id -g)" \
  -e "RUST_TOOLCHAIN=${RUST_TOOLCHAIN}" \
  -e "BPF_LINKER_VERSION=${BPF_LINKER_VERSION}" \
  -v "$src:$src:ro" \
  -v "$writable:$src/target" \
  -v "$out_dir:/out" \
  -w "$src" \
  ubuntu:24.04 \
  bash -c 'set -euo pipefail
cleanup_target() {
  if [ -n "${HOST_UID:-}" ] && [ -n "${HOST_GID:-}" ]; then
    chown -R "${HOST_UID}:${HOST_GID}" "$(pwd)/target" /out >/dev/null 2>&1 || true
  fi
}
trap cleanup_target EXIT
export DEBIAN_FRONTEND=noninteractive
export RUSTUP_TOOLCHAIN="${RUST_TOOLCHAIN}"
apt-get update
apt-get install -y --no-install-recommends build-essential ca-certificates curl pkg-config libssl-dev
curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain "${RUST_TOOLCHAIN}" --component rust-src --profile minimal
. "$HOME/.cargo/env"
curl -L --proto "=https" --tlsv1.2 -sSf https://raw.githubusercontent.com/cargo-bins/cargo-binstall/main/install-from-binstall-release.sh | bash
cargo binstall --no-confirm "bpf-linker@${BPF_LINKER_VERSION}"
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
} > /out/toolchain.txt
export CARGO_HOME=/tmp/cargo
export CARGO_TARGET_DIR=/tmp/target
cargo +"${RUST_TOOLCHAIN}" build -p vantio-loader --release
install -m 0755 /tmp/target/release/vantio-loader /out/vantio-loader
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
