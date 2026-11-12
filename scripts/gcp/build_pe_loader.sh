#!/bin/bash
# Build vantio-loader from an allowlisted Phantom Engine commit.
# This does not run scripts/enforcement_proof_lab.sh. bash -n does not attach a program.
# The guest is an e2-micro. The compile runs in an ubuntu:24.04 container so the
# binary matches that guest's glibc. The git tip is not a seal digest.
# pe-git-sha-allowlist.txt is the same list enforcement_proof.py reads.
set -euo pipefail

root=${1:?}
out=${2:?}
pin=${3:?}
allowlist=$(dirname "$0")/pe-git-sha-allowlist.txt

if [[ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" || -n "${GCP_SA_KEY:-}" ]]; then
  echo "static_credentials" >&2
  exit 1
fi
if [[ ! "$pin" =~ ^[0-9a-f]{40}$ ]] || [[ ! -f "$allowlist" ]]; then
  echo "pe_git_sha" >&2
  exit 1
fi
pin_ok=0
seen=0
seen_shas=" "
while IFS= read -r line || [[ -n "$line" ]]; do
  line=${line%$'\r'}
  case "$line" in
    ""|\#*) continue ;;
  esac
  if [[ ! "$line" =~ ^[0-9a-f]{40}$ ]]; then
    echo "pe_git_sha" >&2
    exit 1
  fi
  case "$seen_shas" in
    *" $line "*) echo "pe_git_sha" >&2; exit 1 ;;
  esac
  seen_shas="$seen_shas$line "
  seen=1
  if [[ "$line" == "$pin" ]]; then
    pin_ok=1
  fi
done < "$allowlist"
if [[ "$seen" -ne 1 || "$pin_ok" -ne 1 ]]; then
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
if [[ "$head" != "$pin" ]]; then
  echo "pe_head" >&2
  exit 1
fi
if ! git -C "$src" merge-base --is-ancestor "$head" origin/main; then
  echo "pe_ancestor" >&2
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
cp "$src/scripts/enforcement_proof_lab.sh" "$out_dir/enforcement_proof_lab.sh"
printf '%s\n' "$head" > "$out_dir/build-sha"
bash -n "$out_dir/enforcement_proof_lab.sh"
sha256sum "$out_dir/enforcement_proof_lab.sh" | awk '{print $1}' > "$out_dir/script.sha256"

# The checkout is mounted read-only. The nested eBPF build writes
# $src/target, and the loader build writes CARGO_TARGET_DIR. Both have to
# be writable directories outside that mount. RUNNER_TEMP is writable on
# the GitHub runner; the out directory is the local fallback.
writable_root=${RUNNER_TEMP:-$out_dir}
cargo_host=$writable_root/vantio-cargo-target
ebpf_host=$writable_root/vantio-ebpf-target
mkdir -p "$cargo_host" "$ebpf_host" "$src/target"

docker run --rm \
  -v "$src:$src:ro" \
  -v "$ebpf_host:$src/target" \
  -v "$cargo_host:/cargo-target" \
  -v "$out_dir:/out" \
  -w "$src" \
  ubuntu:24.04 \
  bash -c 'set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends build-essential ca-certificates curl pkg-config libssl-dev
curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain nightly --component rust-src
. "$HOME/.cargo/env"
curl -L --proto "=https" --tlsv1.2 -sSf https://raw.githubusercontent.com/cargo-bins/cargo-binstall/main/install-from-binstall-release.sh | bash
cargo binstall --no-confirm bpf-linker
export CARGO_HOME=/tmp/cargo
export CARGO_TARGET_DIR=/cargo-target
cargo build -p vantio-loader --release
install -m 0755 /cargo-target/release/vantio-loader /out/vantio-loader
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
