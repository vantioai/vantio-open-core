#!/usr/bin/env bash
# Dispatcher for the clean-host internal-proof lab.
# evidence_tier stays UNSET. stranger-host is refused.
set -euo pipefail
umask 077

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cmd="${1:-}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "$cmd" in
  preflight|reset|capture|retain|stop|expire|status)
    exec "$HERE/$cmd.sh" "$@"
    ;;
  help|-h|--help|"")
    printf '%s\n' \
      "usage: lifecycle.sh <preflight|reset|capture|retain|stop|expire|status> [args]" \
      "classification=CLEAN_HOST_INTERNAL_PROOF" \
      "evidence_tier=UNSET" \
      "stranger_host=NOT_RUN" \
      "phantom_box=EXCLUDED"
    ;;
  --stranger|--stranger-host|stranger-host)
    printf 'clean-host: stop: stranger-host was requested; this lab does not run it\n' >&2
    printf 'clean-host: classification=CLEAN_HOST_INTERNAL_PROOF evidence_tier=UNSET stranger_host=NOT_RUN phantom_box=EXCLUDED\n' >&2
    exit 20
    ;;
  *)
    printf 'clean-host: stop: unknown command\n' >&2
    exit 26
    ;;
esac
