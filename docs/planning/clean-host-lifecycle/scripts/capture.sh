#!/usr/bin/env bash
# One loopback observe cycle inside the disposable HOME.
# A zero exit code means the fixture process and the shape check finished.
# It does not assign an evidence tier and it does not run stranger-host.
set -euo pipefail
umask 077

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

for arg in "$@"; do
  clean_host_refuse_stranger_token "$arg"
  case "$arg" in
    --stranger|--stranger-host|stranger-host) ;;
    *) clean_host_die 26 "unknown capture argument: $arg" ;;
  esac
done

clean_host_guard
clean_host_read_state
if [[ "$CLEAN_HOST_STATUS" != "RESET_READY" ]]; then
  clean_host_die 26 "capture requires RESET_READY; current status is ${CLEAN_HOST_STATUS}"
fi

home_dir="$CLEAN_HOST_LAB_ROOT/home"
marker="$home_dir/.clean-host-cycle"
[[ -f "$marker" ]] || clean_host_die 26 "reset marker is missing"
marker_cycle="$(sed -n 's/^cycle_id=//p' "$marker")"
[[ "$marker_cycle" == "$CLEAN_HOST_CYCLE_ID" ]] || clean_host_die 26 "reset marker cycle does not match state"

before="$(clean_host_operator_snapshot)"
cycle_dir="$CLEAN_HOST_LAB_ROOT/cycles/$CLEAN_HOST_CYCLE_ID"
mkdir -p -- "$cycle_dir"
port_file="$cycle_dir/port"
rm -f -- "$port_file"

clean_host_isolate_home "$home_dir"
if [[ "$HOME" != "$home_dir" ]]; then
  clean_host_die 28 "HOME did not redirect to the disposable lab home"
fi
if [[ -n "${VANTIO_HOME:-}" || -n "${VANTIO_API_KEY:-}" || -n "${VANTIO_SOAK_LOCAL:-}" || -n "${VANTIO_INGEST_URL:-}" ]]; then
  clean_host_die 21 "isolation left a control-plane variable set"
fi

mock_pid=""
cleanup() {
  if [[ -n "$mock_pid" ]]; then
    kill "$mock_pid" 2>/dev/null || true
    wait "$mock_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

PORT_FILE="$port_file" node -e '
const http = require("node:http");
const fs = require("node:fs");
const portFile = process.env.PORT_FILE;
const server = http.createServer((req, res) => {
  const body = JSON.stringify({ id: "clean-host-fixture", choices: [{ message: { content: "ok" } }] });
  res.writeHead(200, { "content-type": "application/json", "content-length": Buffer.byteLength(body) });
  res.end(body);
});
server.listen(0, "127.0.0.1", () => {
  fs.writeFileSync(portFile, String(server.address().port));
});
' &
mock_pid=$!

ready=0
for _ in $(seq 1 50); do
  if [[ -s "$port_file" ]]; then
    ready=1
    break
  fi
  sleep 0.1
done
if [[ "$ready" -ne 1 ]]; then
  clean_host_write_state "STOPPED" "$CLEAN_HOST_CYCLE_ID" ""
  printf 'reason=CAPTURE_FAILED\n' >"$cycle_dir/stop.txt"
  chmod 0600 "$cycle_dir/stop.txt"
  clean_host_die 26 "loopback fixture server did not start"
fi

port="$(tr -cd '0-9' <"$port_file")"
[[ "$port" =~ ^[0-9]+$ ]] || clean_host_die 26 "loopback port was not numeric"

interceptor="$CLEAN_HOST_REPO_ROOT/packages/vantio-cli/bin/interceptor.cjs"
agent="$CLEAN_HOST_REPO_ROOT/scripts/fixtures/minimal-agent.js"
cd "$CLEAN_HOST_LAB_ROOT"

set +e
VANTIO_TRACE_ID="$CLEAN_HOST_CYCLE_ID" \
VANTIO_EXTRA_LLM_HOSTS="127.0.0.1" \
VANTIO_MOCK_LLM_PORT="$port" \
VANTIO_TELEMETRY_DISABLED=1 \
DO_NOT_TRACK=1 \
node --require "$interceptor" "$agent" >"$cycle_dir/agent.out" 2>"$cycle_dir/agent.err"
agent_code=$?
set -e
chmod 0600 "$cycle_dir/agent.out" "$cycle_dir/agent.err" || true

if [[ "$agent_code" -ne 0 ]]; then
  clean_host_write_state "STOPPED" "$CLEAN_HOST_CYCLE_ID" ""
  printf 'reason=CAPTURE_FAILED\nagent_exit=%s\n' "$agent_code" >"$cycle_dir/stop.txt"
  chmod 0600 "$cycle_dir/stop.txt"
  clean_host_die 26 "fixture process exited ${agent_code}"
fi

after="$(clean_host_operator_snapshot)"
if [[ "$before" != "$after" ]]; then
  clean_host_write_state "STOPPED" "$CLEAN_HOST_CYCLE_ID" ""
  printf 'reason=OPERATOR_HOME_TOUCHED\n' >"$cycle_dir/stop.txt"
  chmod 0600 "$cycle_dir/stop.txt"
  clean_host_die 28 "operator data directory changed during capture"
fi

runs_dir="$home_dir/.vantio/runs"
[[ -d "$runs_dir" ]] || {
  clean_host_write_state "STOPPED" "$CLEAN_HOST_CYCLE_ID" ""
  printf 'reason=RUN_SHAPE_REJECTED\n' >"$cycle_dir/stop.txt"
  chmod 0600 "$cycle_dir/stop.txt"
  clean_host_die 27 "disposable runs directory is missing"
}

mapfile -t run_files < <(find "$runs_dir" -maxdepth 1 -type f -name '*.json' | sort)
if [[ "${#run_files[@]}" -ne 1 ]]; then
  clean_host_write_state "STOPPED" "$CLEAN_HOST_CYCLE_ID" ""
  printf 'reason=RUN_SHAPE_REJECTED\n' >"$cycle_dir/stop.txt"
  chmod 0600 "$cycle_dir/stop.txt"
  clean_host_die 27 "capture expected one run file"
fi

run_path="${run_files[0]}"
run_base="$(basename "$run_path")"
expected="${CLEAN_HOST_CYCLE_ID}.json"
if [[ "$run_base" != "$expected" ]]; then
  clean_host_write_state "STOPPED" "$CLEAN_HOST_CYCLE_ID" ""
  printf 'reason=RUN_SHAPE_REJECTED\n' >"$cycle_dir/stop.txt"
  chmod 0600 "$cycle_dir/stop.txt"
  clean_host_die 27 "run file name does not match the cycle id"
fi

canon_run="$(realpath -m -- "$run_path")"
case "$canon_run/" in
  "$home_dir/.vantio/runs"/*) ;;
  *)
    clean_host_write_state "STOPPED" "$CLEAN_HOST_CYCLE_ID" ""
    printf 'reason=RUN_SHAPE_REJECTED\n' >"$cycle_dir/stop.txt"
    chmod 0600 "$cycle_dir/stop.txt"
    clean_host_die 27 "run file is outside the disposable runs directory"
    ;;
esac

if ! node "$HERE/inspect-run.mjs" "$run_path" >"$cycle_dir/inspect.out"; then
  clean_host_write_state "STOPPED" "$CLEAN_HOST_CYCLE_ID" ""
  printf 'reason=RUN_SHAPE_REJECTED\n' >"$cycle_dir/stop.txt"
  chmod 0600 "$cycle_dir/stop.txt"
  clean_host_die 27 "run file failed the internal shape check"
fi
chmod 0600 "$cycle_dir/inspect.out"

clean_host_write_state "CAPTURED" "$CLEAN_HOST_CYCLE_ID" "$run_base"
clean_host_banner
printf 'status=CAPTURED\n'
printf 'cycle_id=%s\n' "$CLEAN_HOST_CYCLE_ID"
printf 'run_file=%s\n' "$run_base"
printf 'capture_assigns_evidence_tier=false\n'
