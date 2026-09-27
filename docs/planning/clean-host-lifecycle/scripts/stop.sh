#!/usr/bin/env bash
# Record a stop. Retention already copied is left in place.
set -euo pipefail
umask 077

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

reason=""
while [[ $# -gt 0 ]]; do
  clean_host_refuse_stranger_token "$1"
  case "$1" in
    --reason)
      reason="${2:-}"
      shift 2
      ;;
    --reason=*)
      reason="${1#--reason=}"
      shift
      ;;
    --stranger|--stranger-host|stranger-host)
      shift
      ;;
    *)
      clean_host_die 26 "unknown stop argument: $1"
      ;;
  esac
done

[[ "$reason" =~ ^[A-Z][A-Z0-9_]{0,79}$ ]] || clean_host_die 26 "stop --reason must be an uppercase token"

clean_host_guard
clean_host_read_state
note_dir="$CLEAN_HOST_LAB_ROOT/cycles/$CLEAN_HOST_CYCLE_ID"
mkdir -p -- "$note_dir"
{
  printf 'reason=%s\n' "$reason"
  printf 'previous_status=%s\n' "$CLEAN_HOST_STATUS"
  printf 'classification=%s\n' "$CLEAN_HOST_CLASSIFICATION"
  printf 'evidence_tier=%s\n' "$CLEAN_HOST_EVIDENCE_TIER"
  printf 'stranger_host=%s\n' "$CLEAN_HOST_STRANGER_HOST"
  printf 'phantom_box=%s\n' "$CLEAN_HOST_PHANTOM_BOX"
  printf 'stopped_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >"$note_dir/stop.txt"
chmod 0600 "$note_dir/stop.txt"
clean_host_write_state "STOPPED" "$CLEAN_HOST_CYCLE_ID" "$CLEAN_HOST_RUN_FILE"
clean_host_banner
printf 'status=STOPPED\n'
printf 'cycle_id=%s\n' "$CLEAN_HOST_CYCLE_ID"
printf 'reason=%s\n' "$reason"
printf 'stop_deletes_retention=false\n'
