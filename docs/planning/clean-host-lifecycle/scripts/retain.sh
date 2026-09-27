#!/usr/bin/env bash
# Copy the accepted run file into the retention directory and write a manifest.
# The manifest evidence_tier is UNSET. The copy is not a product seal.
set -euo pipefail
umask 077

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

for arg in "$@"; do
  clean_host_refuse_stranger_token "$arg"
  case "$arg" in
    --stranger|--stranger-host|stranger-host) ;;
    *) clean_host_die 26 "unknown retain argument: $arg" ;;
  esac
done

clean_host_guard
clean_host_read_state
if [[ "$CLEAN_HOST_STATUS" != "CAPTURED" ]]; then
  clean_host_die 26 "retain requires CAPTURED; current status is ${CLEAN_HOST_STATUS}"
fi
[[ -n "$CLEAN_HOST_RUN_FILE" ]] || clean_host_die 26 "captured cycle has no run file name"

src="$CLEAN_HOST_LAB_ROOT/home/.vantio/runs/$CLEAN_HOST_RUN_FILE"
[[ -f "$src" ]] || clean_host_die 27 "captured run file is missing"
node "$HERE/inspect-run.mjs" "$src" >/dev/null

dest_dir="$CLEAN_HOST_LAB_ROOT/retention/$CLEAN_HOST_CYCLE_ID"
if [[ -e "$dest_dir" ]]; then
  clean_host_die 26 "retention directory already exists for ${CLEAN_HOST_CYCLE_ID}"
fi
mkdir -p -- "$dest_dir/runs"
chmod 0700 "$dest_dir" "$dest_dir/runs"
cp -f -- "$src" "$dest_dir/runs/$CLEAN_HOST_RUN_FILE"
chmod 0600 "$dest_dir/runs/$CLEAN_HOST_RUN_FILE"
node "$HERE/inspect-run.mjs" "$dest_dir/runs/$CLEAN_HOST_RUN_FILE" >/dev/null

commit="$(git -C "$CLEAN_HOST_REPO_ROOT" rev-parse HEAD)"
if [[ -n "$(git -C "$CLEAN_HOST_REPO_ROOT" status --porcelain)" ]]; then
  dirty="true"
else
  dirty="false"
fi
node "$HERE/emit-cycle-manifest.mjs" \
  "$CLEAN_HOST_CYCLE_ID" \
  "$commit" \
  "$dirty" \
  "$dest_dir/runs/$CLEAN_HOST_RUN_FILE" \
  "$dest_dir/manifest.json" \
  "$CLEAN_HOST_REPO_ROOT/packages/vantio-cli/package.json" >/dev/null

python_absent=1
if [[ -e "$CLEAN_HOST_LAB_ROOT/home/.vantio/config.json" || -e "$CLEAN_HOST_LAB_ROOT/home/.vantio/telemetry-id" ]]; then
  # These files are not copied. Their presence in the disposable home is recorded
  # only as a count so the operator can see the writer created them.
  python_absent=0
fi
if [[ -e "$dest_dir/runs/config.json" || -e "$dest_dir/telemetry-id" || -e "$dest_dir/runs/telemetry-id" ]]; then
  clean_host_die 27 "retention copied a file outside the run-file allowlist"
fi

clean_host_write_state "RETAINED" "$CLEAN_HOST_CYCLE_ID" "$CLEAN_HOST_RUN_FILE"
clean_host_banner
printf 'status=RETAINED\n'
printf 'cycle_id=%s\n' "$CLEAN_HOST_CYCLE_ID"
printf 'retention=%s\n' "$dest_dir"
printf 'local_identity_file_present=%s\n' "$([[ "$python_absent" -eq 0 ]] && printf yes || printf no)"
printf 'retain_assigns_evidence_tier=false\n'
