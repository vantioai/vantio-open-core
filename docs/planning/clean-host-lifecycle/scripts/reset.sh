#!/usr/bin/env bash
# Wipe the disposable HOME and open a new cycle. Retention directories stay.
set -euo pipefail
umask 077

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

abandon=0
for arg in "$@"; do
  clean_host_refuse_stranger_token "$arg"
  case "$arg" in
    --abandon) abandon=1 ;;
    --stranger|--stranger-host|stranger-host) ;;
    *) clean_host_die 26 "unknown reset argument: $arg" ;;
  esac
done

clean_host_guard
mkdir -p -- "$CLEAN_HOST_LAB_ROOT"
chmod 0700 "$CLEAN_HOST_LAB_ROOT"

if [[ -f "$(clean_host_state_file)" ]]; then
  clean_host_read_state
  if [[ "$CLEAN_HOST_STATUS" == "CAPTURED" && "$abandon" -ne 1 ]]; then
    clean_host_die 26 "cycle ${CLEAN_HOST_CYCLE_ID} is CAPTURED; retain it or reset with --abandon"
  fi
  if [[ "$CLEAN_HOST_STATUS" == "CAPTURED" && "$abandon" -eq 1 ]]; then
    note_dir="$CLEAN_HOST_LAB_ROOT/cycles/$CLEAN_HOST_CYCLE_ID"
    mkdir -p -- "$note_dir"
    printf 'reason=ABANDONED_BEFORE_RETAIN\nclassification=%s\nevidence_tier=%s\nstranger_host=%s\n' \
      "$CLEAN_HOST_CLASSIFICATION" "$CLEAN_HOST_EVIDENCE_TIER" "$CLEAN_HOST_STRANGER_HOST" \
      >"$note_dir/abandoned.txt"
    chmod 0600 "$note_dir/abandoned.txt"
  fi
fi

rm -rf -- "$CLEAN_HOST_LAB_ROOT/home"
mkdir -p -- "$CLEAN_HOST_LAB_ROOT/home" "$CLEAN_HOST_LAB_ROOT/cycles" "$CLEAN_HOST_LAB_ROOT/retention"
chmod 0700 "$CLEAN_HOST_LAB_ROOT/home" "$CLEAN_HOST_LAB_ROOT/cycles" "$CLEAN_HOST_LAB_ROOT/retention"

cycle="$(clean_host_new_cycle_id)"
stamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
commit="$(git -C "$CLEAN_HOST_REPO_ROOT" rev-parse HEAD)"
{
  printf 'classification=%s\n' "$CLEAN_HOST_CLASSIFICATION"
  printf 'evidence_tier=%s\n' "$CLEAN_HOST_EVIDENCE_TIER"
  printf 'stranger_host=%s\n' "$CLEAN_HOST_STRANGER_HOST"
  printf 'phantom_box=%s\n' "$CLEAN_HOST_PHANTOM_BOX"
  printf 'cycle_id=%s\n' "$cycle"
  printf 'created_at=%s\n' "$stamp"
  printf 'source_commit=%s\n' "$commit"
} >"$CLEAN_HOST_LAB_ROOT/home/.clean-host-cycle"
chmod 0600 "$CLEAN_HOST_LAB_ROOT/home/.clean-host-cycle"

cycle_dir="$CLEAN_HOST_LAB_ROOT/cycles/$cycle"
mkdir -p -- "$cycle_dir"
chmod 0700 "$cycle_dir"
cp -f -- "$CLEAN_HOST_LAB_ROOT/home/.clean-host-cycle" "$cycle_dir/cycle.txt"
chmod 0600 "$cycle_dir/cycle.txt"

clean_host_write_state "RESET_READY" "$cycle" ""
clean_host_banner
printf 'status=RESET_READY\n'
printf 'cycle_id=%s\n' "$cycle"
printf 'home=%s\n' "$CLEAN_HOST_LAB_ROOT/home"
printf 'reset_assigns_evidence_tier=false\n'
