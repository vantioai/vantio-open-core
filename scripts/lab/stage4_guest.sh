#!/bin/bash
# Stage 4 guest steps. The runner copies this file and a built loader.
# This script does not build the loader and does not download packages.
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
  local desired="$1" dropin
  install -d /etc/default/grub.d
  dropin=/etc/default/grub.d/99-vantio-stage4-lsm.cfg
  DESIRED_LSM="$desired" python3 "$plan" grub-dropin > "$dropin"
  bash -n "$dropin"
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
  local image uname_now lsm rc expected_lsm cmdline
  image="$(metadata_image)"
  uname_now="$(uname -r)"
  lsm="$(lsm_list)"
  cmdline="$(cat /proc/cmdline)"
  expected_lsm="-"
  if [[ -f "$marker" ]]; then
    expected_lsm="$(cat "$marker")"
  fi
  set +e
  python3 "$plan" guest-preflight \
    "$image" "$uname_now" "$lsm" \
    "${EXPECTED_IMAGE:?}" "${EXPECTED_UNAME:?}" "${BPF_MODE:?}" \
    "$expected_lsm" "$cmdline"
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
  desired="$(LSM_LIST="$lsm" BPF_MODE="${BPF_MODE:?}" python3 "$plan" desired-lsm)"
  note "lsm_desired=${desired}"
  write_lsm "$desired"
  printf '%s' "$desired" > "$marker"
  note "reboot=scheduled"
  reboot_once
  return 10
}

refuse_case() {
  local before after log rc listed
  before="$(mktemp)"
  after="$(mktemp)"
  log="$log_dir/refuse.txt"
  list_programs() {
    listed=0
    if command -v bpftool >/dev/null 2>&1; then
      bpftool prog show
      listed=1
    fi
    if [[ -d /sys/fs/bpf ]]; then
      find /sys/fs/bpf -print
      listed=1
    fi
    if [[ "$listed" -ne 1 ]]; then
      printf '%s\n' "listing=unavailable"
    fi
  }
  list_programs | sort > "$before"
  set +e
  /var/lib/vantio-lab/guest/vantio-loader --enforce >"$log" 2>&1
  rc=$?
  set -e
  list_programs | sort > "$after"
  python3 "$plan" refusal-check "$log" "$before" "$after" "$rc"
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

case "$mode" in
  preflight) preflight ;;
  refuse) refuse_case ;;
  soak) soak ;;
  ds) ds ;;
  build|pack)
    note "guest_build"
    exit 2
    ;;
  *)
    note "mode"
    exit 2
    ;;
esac
