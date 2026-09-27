#!/usr/bin/env bash
# Delete one retained cycle by id and leave a tombstone with no run bytes.
set -euo pipefail
umask 077

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

cycle=""
while [[ $# -gt 0 ]]; do
  clean_host_refuse_stranger_token "$1"
  case "$1" in
    --cycle)
      cycle="${2:-}"
      shift 2
      ;;
    --cycle=*)
      cycle="${1#--cycle=}"
      shift
      ;;
    --all|*)
      if [[ "$1" == "--all" ]]; then
        clean_host_die 29 "expire refuses --all; pass one --cycle id"
      fi
      clean_host_die 26 "unknown expire argument: $1"
      ;;
  esac
done

[[ "$cycle" =~ ^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$ ]] || clean_host_die 29 "expire requires one cycle id"

clean_host_guard
dest="$CLEAN_HOST_LAB_ROOT/retention/$cycle"
[[ -d "$dest" ]] || clean_host_die 29 "retention cycle ${cycle} was not found"

if [[ -f "$(clean_host_state_file)" ]]; then
  clean_host_read_state
  if [[ "$CLEAN_HOST_CYCLE_ID" == "$cycle" && "$CLEAN_HOST_STATUS" == "CAPTURED" ]]; then
    clean_host_die 29 "cycle ${cycle} is CAPTURED and has not been retained as a finished bundle"
  fi
  if [[ "$CLEAN_HOST_CYCLE_ID" == "$cycle" && "$CLEAN_HOST_STATUS" != "RETAINED" && "$CLEAN_HOST_STATUS" != "STOPPED" ]]; then
    clean_host_die 29 "cycle ${cycle} is ${CLEAN_HOST_STATUS}; expire applies to a retained bundle"
  fi
fi

rm -rf -- "$dest"
{
  printf 'cycle_id=%s\n' "$cycle"
  printf 'expired_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'run_bytes=removed\n'
  printf 'classification=%s\n' "$CLEAN_HOST_CLASSIFICATION"
  printf 'evidence_tier=%s\n' "$CLEAN_HOST_EVIDENCE_TIER"
  printf 'stranger_host=%s\n' "$CLEAN_HOST_STRANGER_HOST"
} >"$CLEAN_HOST_LAB_ROOT/retention/${cycle}.expired"
chmod 0600 "$CLEAN_HOST_LAB_ROOT/retention/${cycle}.expired"

if [[ -f "$(clean_host_state_file)" ]]; then
  current="$(clean_host_field cycle_id)"
  if [[ "$current" == "$cycle" ]]; then
    clean_host_write_state "STOPPED" "$cycle" ""
    printf 'reason=EXPIRED\n' >"$CLEAN_HOST_LAB_ROOT/cycles/$cycle/stop.txt"
    chmod 0600 "$CLEAN_HOST_LAB_ROOT/cycles/$cycle/stop.txt"
  fi
fi

clean_host_banner
printf 'status=EXPIRED\n'
printf 'cycle_id=%s\n' "$cycle"
printf 'expire_removes_one_cycle=true\n'
