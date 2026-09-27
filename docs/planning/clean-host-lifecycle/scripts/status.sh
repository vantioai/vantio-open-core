#!/usr/bin/env bash
# Print lab classification and state. Does not mutate the lab.
set -euo pipefail
umask 077

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

for arg in "$@"; do
  clean_host_refuse_stranger_token "$arg"
  case "$arg" in
    --stranger|--stranger-host|stranger-host) ;;
    *) clean_host_die 26 "unknown status argument: $arg" ;;
  esac
done

clean_host_guard
clean_host_banner
if [[ ! -f "$(clean_host_state_file)" ]]; then
  printf 'status=ABSENT\n'
  exit 0
fi
clean_host_read_state
printf 'status=%s\n' "$CLEAN_HOST_STATUS"
printf 'cycle_id=%s\n' "$CLEAN_HOST_CYCLE_ID"
printf 'run_file=%s\n' "${CLEAN_HOST_RUN_FILE:-}"
printf 'lab_root=%s\n' "$CLEAN_HOST_LAB_ROOT"
