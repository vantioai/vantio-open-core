#!/usr/bin/env bash
# Non-mutating gate. Exit 0 means the parent environment may call reset.
# Exit 0 is not an evidence tier.
set -euo pipefail
umask 077

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

clean_host_guard "$@"
clean_host_banner
printf 'lab_root=%s\n' "$CLEAN_HOST_LAB_ROOT"
printf 'repository=%s\n' "$CLEAN_HOST_REPO_ROOT"
printf 'preflight=PASS\n'
printf 'preflight_assigns_evidence_tier=false\n'
