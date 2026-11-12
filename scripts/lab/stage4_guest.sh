#!/bin/bash
# Stage 4 guest steps. The runner copies this file to the VM.
# live_enforcement stays NOT_PROVEN. This script does not print a run go.
# The DS mode records the unwired hold and does not run a check.
set -euo pipefail

mode="${1:?}"
plan="${STAGE4_PLAN:-/tmp/stage4_plan.py}"
marker="/var/lib/vantio-stage4/lsm-attempted"
log_dir="${STAGE4_LOG_DIR:-/var/lib/vantio-stage4}"
mkdir -p "$log_dir" /var/lib/vantio-stage4

note() {
  printf '%s\n' "$*" | tee -a "$log_dir/guest.txt"
}

lsm_list() {
  tr -d '[:space:]' < /sys/kernel/security/lsm
}

metadata_image() {
  curl -fsS -H "Metadata-Flavor: Google" \
    http://metadata.google.internal/computeMetadata/v1/instance/image
}

write_lsm() {
  local desired="$1"
  install -d /etc/default/grub.d
  cat > /etc/default/grub.d/99-vantio-stage4-lsm.cfg <<EOF
GRUB_CMDLINE_LINUX="\$GRUB_CMDLINE_LINUX lsm=${desired}"
EOF
  if command -v update-grub >/dev/null 2>&1; then
    update-grub
  else
    grub-mkconfig -o /boot/grub/grub.cfg
  fi
}

reboot_once() {
  # The lab network can leave google-shutdown-scripts stop-job running.
  # Mask it, then schedule a forced reboot after this SSH command returns.
  systemctl mask --now google-shutdown-scripts.service >/dev/null 2>&1 || true
  sync
  if ! systemd-run --on-active=8s --unit=vantio-stage4-reboot systemctl reboot --force; then
    systemctl reboot --force || true
  fi
}

preflight() {
  local image uname_now lsm rc
  image="$(metadata_image)"
  uname_now="$(uname -r)"
  lsm="$(lsm_list)"
  set +e
  python3 "$plan" guest-preflight \
    "$image" "$uname_now" "$lsm" \
    "${EXPECTED_IMAGE:?}" "${EXPECTED_UNAME:?}" "${BPF_MODE:?}"
  rc=$?
  set -e
  if [[ "$rc" -eq 0 ]]; then
    note "preflight=pass"
    note "live_enforcement=NOT_PROVEN"
    return 0
  fi
  if [[ "$rc" -ne 10 ]]; then
    note "preflight=fail"
    return "$rc"
  fi
  if [[ -f "$marker" ]]; then
    note "lsm_change=failed"
    return 2
  fi
  local desired
  desired="$(python3 - "$lsm" "$BPF_MODE" <<'PY'
import sys
tokens = [token.strip() for token in sys.argv[1].split(",") if token.strip() and token.strip() != "bpf"]
if sys.argv[2] == "require":
    tokens.append("bpf")
print(",".join(tokens))
PY
)"
  note "lsm_desired=${desired}"
  write_lsm "$desired"
  touch "$marker"
  note "reboot=scheduled"
  reboot_once
  return 10
}

build_loader() {
  local root="${PE_ROOT:?}"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y build-essential pkg-config libssl-dev clang llvm curl ca-certificates
  if [[ ! -x "${HOME}/.cargo/bin/cargo" ]]; then
    curl --proto '=https' --tlsv1.2 -fsS https://sh.rustup.rs | \
      sh -s -- -y --profile minimal
  fi
  # shellcheck disable=SC1091
  . "${HOME}/.cargo/env"
  (cd "$root" && rustup show)
  if ! command -v bpf-linker >/dev/null 2>&1; then
    local installer
    installer="$(mktemp)"
    curl -L --proto '=https' --tlsv1.2 -fsS \
      https://raw.githubusercontent.com/cargo-bins/cargo-binstall/v1.26.0/install-from-binstall-release.sh \
      -o "$installer"
    echo "d3a93702160e0ec03e2a4e996855db1f01adee801fb84a43add24e0877ef8eae  $installer" \
      | sha256sum -c -
    bash "$installer"
    cargo binstall --no-confirm --disable-strategies compile bpf-linker@0.12.0
  fi
  (cd "$root" && cargo build -p vantio-loader --release)
  install -d /var/lib/vantio-lab/loader
  install -m 0755 "$root/target/release/vantio-loader" /var/lib/vantio-lab/loader/vantio-loader
  install -m 0755 "$root/scripts/enforcement_proof_lab.sh" /var/lib/vantio-lab/loader/enforcement_proof_lab.sh
  ldd /var/lib/vantio-lab/loader/vantio-loader > /var/lib/vantio-lab/loader/ldd.txt || true
  sha256sum /var/lib/vantio-lab/loader/vantio-loader | awk '{print $1}' > /var/lib/vantio-lab/loader/loader.sha256
  sha256sum /var/lib/vantio-lab/loader/enforcement_proof_lab.sh | awk '{print $1}' > /var/lib/vantio-lab/loader/script.sha256
  note "loader=built"
}

refuse_case() {
  local before after log
  before="$(mktemp)"
  after="$(mktemp)"
  if [[ -d /sys/fs/bpf/vantio_persist ]]; then
    find /sys/fs/bpf/vantio_persist -type f | sort > "$before"
  else
    : > "$before"
  fi
  log="$log_dir/refuse.txt"
  set +e
  /var/lib/vantio-lab/loader/vantio-loader --enforce >"$log" 2>&1
  set -e
  if [[ -d /sys/fs/bpf/vantio_persist ]]; then
    find /sys/fs/bpf/vantio_persist -type f | sort > "$after"
  else
    : > "$after"
  fi
  python3 "$plan" refusal-check "$log" "$before" "$after"
  note "refusal=held"
}

health_once() {
  python3 "$plan" guest-preflight \
    "$(metadata_image)" "$(uname -r)" "$(lsm_list)" \
    "${EXPECTED_IMAGE:?}" "${EXPECTED_UNAME:?}" require >/dev/null
  awk '{print $1}' /proc/loadavg >/dev/null
}

soak() {
  local minutes seconds end
  minutes="$(python3 "$plan" soak-minutes "${SOAK_MINUTES:?}")"
  seconds=$((minutes * 60))
  end=$((SECONDS + seconds))
  while (( SECONDS < end )); do
    health_once
    note "health=ok t=${SECONDS}"
    local remaining=$((end - SECONDS))
    if (( remaining > 60 )); then
      sleep 60
    elif (( remaining > 0 )); then
      sleep "$remaining"
    fi
  done
  note "health_soak=done"
  note "soak_pass=false"
  note "live_enforcement=NOT_PROVEN"
}

ds() {
  python3 "$plan" ds-hold
  note "ds_hold=recorded"
}

pack() {
  tar -C /var/lib/vantio-lab/loader -cf /tmp/loader-pack.tar \
    vantio-loader enforcement_proof_lab.sh ldd.txt loader.sha256 script.sha256
  chmod 0644 /tmp/loader-pack.tar
  note "loader=packed"
}

case "$mode" in
  preflight) preflight ;;
  build) build_loader ;;
  pack) pack ;;
  refuse) refuse_case ;;
  soak) soak ;;
  ds) ds ;;
  *)
    note "mode"
    exit 2
    ;;
esac
