#!/usr/bin/env bash
# Clean-host internal-proof lab guards.
# Sourced by the lifecycle scripts. Does not run a cycle by itself.
# Audience: INTERNAL_RESTRICTED
# environment_class: CLEAN_HOST_INTERNAL_PROOF
# evidence_tier: UNSET
# stranger_host: NOT_RUN
# phantom_box: EXCLUDED

if [[ -z "${CLEAN_HOST_LIB_LOADED:-}" ]]; then
  CLEAN_HOST_LIB_LOADED=1
fi

set -euo pipefail
umask 077

CLEAN_HOST_CLASSIFICATION="CLEAN_HOST_INTERNAL_PROOF"
CLEAN_HOST_EVIDENCE_TIER="UNSET"
CLEAN_HOST_STRANGER_HOST="NOT_RUN"
CLEAN_HOST_PHANTOM_BOX="EXCLUDED"
CLEAN_HOST_CUSTOMER_VALIDATION="UNSET"
CLEAN_HOST_INDEPENDENT_VERIFIER="UNSET"

_clean_host_lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLEAN_HOST_REPO_ROOT="$(cd "${_clean_host_lib_dir}/../../../.." && pwd)"
CLEAN_HOST_REPO_ROOT="$(realpath -m -- "$CLEAN_HOST_REPO_ROOT")"

if [[ -z "${CLEAN_HOST_OPERATOR_HOME:-}" ]]; then
  CLEAN_HOST_OPERATOR_HOME="${HOME}"
fi
CLEAN_HOST_OPERATOR_HOME="$(realpath -m -- "$CLEAN_HOST_OPERATOR_HOME")"

clean_host_die() {
  local code="$1"
  shift
  printf 'clean-host: stop: %s\n' "$*" >&2
  printf 'clean-host: classification=%s evidence_tier=%s stranger_host=%s phantom_box=%s\n' \
    "$CLEAN_HOST_CLASSIFICATION" \
    "$CLEAN_HOST_EVIDENCE_TIER" \
    "$CLEAN_HOST_STRANGER_HOST" \
    "$CLEAN_HOST_PHANTOM_BOX" >&2
  exit "$code"
}

clean_host_refuse_stranger_token() {
  case "$1" in
    --stranger|--stranger-host|stranger-host)
      clean_host_die 20 "stranger-host was requested; this lab does not run it"
      ;;
  esac
}

clean_host_refuse_stranger() {
  local arg
  if [[ "${CLEAN_HOST_STRANGER_HOST_REQUEST:-}" == "1" ]]; then
    clean_host_die 20 "stranger-host was requested; this lab does not run it"
  fi
  if [[ "${STRANGER_HOST:-}" == "1" || "${VANTIO_STRANGER_HOST:-}" == "1" ]]; then
    clean_host_die 20 "a stranger-host variable is set; this lab does not run it"
  fi
  for arg in "$@"; do
    clean_host_refuse_stranger_token "$arg"
  done
}

clean_host_url_is_phantom_box() {
  local url="${1:-}"
  [[ "$url" == *":5001"* ]]
}

clean_host_refuse_control_plane() {
  if [[ "${VANTIO_SOAK_LOCAL:-}" == "1" ]]; then
    clean_host_die 21 "VANTIO_SOAK_LOCAL=1 selects the Phantom-Box soak; this lab excludes it"
  fi
  if [[ -n "${VANTIO_API_KEY:-}" ]]; then
    clean_host_die 21 "VANTIO_API_KEY is set; this lab does not load a control plane"
  fi
  if [[ -n "${VANTIO_IDENTITY:-}" ]]; then
    clean_host_die 21 "VANTIO_IDENTITY is set; this lab does not load a control plane"
  fi
  if [[ -n "${VANTIO_INGEST_URL:-}" ]]; then
    if clean_host_url_is_phantom_box "${VANTIO_INGEST_URL}"; then
      clean_host_die 21 "VANTIO_INGEST_URL contains :5001; that port is the Phantom-Box local control plane"
    fi
    clean_host_die 21 "VANTIO_INGEST_URL is set; this lab leaves the control-plane URL unset"
  fi
  if [[ -n "${VANTIO_API_BASE:-}" ]]; then
    clean_host_die 21 "VANTIO_API_BASE is set; this lab does not call a control plane"
  fi
  local cloud="${VANTIO_CLOUD_INGEST:-}"
  local cloud_lc
  cloud_lc="$(printf '%s' "$cloud" | tr '[:upper:]' '[:lower:]')"
  if [[ "$cloud_lc" == "1" || "$cloud_lc" == "true" ]]; then
    clean_host_die 21 "VANTIO_CLOUD_INGEST is set; this lab does not send cloud ingest"
  fi
  if [[ "${VANTIO_AUDIT_MODE:-}" == "1" ]]; then
    clean_host_die 21 "VANTIO_AUDIT_MODE=1 is set; this lab stays on the free observe path"
  fi
}

clean_host_refuse_split_home() {
  if [[ -n "${VANTIO_HOME:-}" ]]; then
    clean_host_die 22 "VANTIO_HOME is set; this lab redirects HOME and leaves VANTIO_HOME unset"
  fi
}

clean_host_refuse_telemetry() {
  if [[ "${VANTIO_TELEMETRY:-}" == "1" ]]; then
    clean_host_die 23 "VANTIO_TELEMETRY=1 would send a usage ping; this lab refuses it"
  fi
}

clean_host_refuse_inherited_scope() {
  if [[ -n "${VANTIO_EXTRA_LLM_HOSTS:-}" ]]; then
    clean_host_die 30 "VANTIO_EXTRA_LLM_HOSTS is set in the parent environment; capture sets the loopback name itself"
  fi
  if [[ -n "${VANTIO_TRACE_ID:-}" ]]; then
    clean_host_die 30 "VANTIO_TRACE_ID is set in the parent environment; capture assigns the cycle id"
  fi
  if [[ -n "${VANTIO_MOCK_LLM_PORT:-}" ]]; then
    clean_host_die 30 "VANTIO_MOCK_LLM_PORT is set in the parent environment; capture assigns the loopback port"
  fi
}

clean_host_require_lab_root() {
  local root="${LAB_ROOT:-}"
  local op="$CLEAN_HOST_OPERATOR_HOME"
  if [[ -z "$root" ]]; then
    clean_host_die 24 "LAB_ROOT is required and must be an absolute path outside this repository and outside the operator data directory"
  fi
  if [[ "$root" != /* ]]; then
    clean_host_die 24 "LAB_ROOT must be absolute"
  fi
  case "$root" in
    *..*)
      clean_host_die 24 "LAB_ROOT must not contain .."
      ;;
  esac
  local canon
  canon="$(realpath -m -- "$root")"
  if [[ "$canon" == "/" || "$canon" == "$op" || "$canon" == "$CLEAN_HOST_REPO_ROOT" ]]; then
    clean_host_die 24 "LAB_ROOT must not be /, the operator home, or the repository root"
  fi
  case "$canon/" in
    "$op/.vantio"/*)
      clean_host_die 24 "LAB_ROOT is inside the operator data directory"
      ;;
    "$CLEAN_HOST_REPO_ROOT"/*)
      clean_host_die 24 "LAB_ROOT is inside the repository"
      ;;
  esac
  local parent
  parent="$(dirname "$canon")"
  if [[ ! -d "$parent" || ! -w "$parent" ]]; then
    clean_host_die 24 "parent of LAB_ROOT must exist and be writable"
  fi
  CLEAN_HOST_LAB_ROOT="$canon"
  LAB_ROOT="$canon"
}

clean_host_require_tools() {
  if [[ ! -f "$CLEAN_HOST_REPO_ROOT/packages/vantio-cli/bin/interceptor.cjs" ]]; then
    clean_host_die 25 "repository interceptor was not found"
  fi
  if [[ ! -f "$CLEAN_HOST_REPO_ROOT/packages/vantio-cli/bin/vantio.js" ]]; then
    clean_host_die 25 "repository CLI was not found"
  fi
  if [[ ! -f "$CLEAN_HOST_REPO_ROOT/scripts/fixtures/minimal-agent.js" ]]; then
    clean_host_die 25 "loopback fixture was not found"
  fi
  command -v node >/dev/null 2>&1 || clean_host_die 25 "node was not found on PATH"
  command -v git >/dev/null 2>&1 || clean_host_die 25 "git was not found on PATH"
  command -v realpath >/dev/null 2>&1 || clean_host_die 25 "realpath was not found on PATH"
  node -e 'const major = Number(process.versions.node.split(".")[0]); if (!Number.isInteger(major) || major < 18) process.exit(1);' \
    || clean_host_die 25 "node 18 or newer is required"
}

clean_host_guard() {
  clean_host_refuse_stranger "$@"
  clean_host_require_tools
  clean_host_refuse_control_plane
  clean_host_refuse_split_home
  clean_host_refuse_telemetry
  clean_host_refuse_inherited_scope
  clean_host_require_lab_root
}

clean_host_state_file() {
  printf '%s\n' "$CLEAN_HOST_LAB_ROOT/state.env"
}

clean_host_write_state() {
  local status="$1"
  local cycle="$2"
  local run_base="${3:-}"
  local file
  file="$(clean_host_state_file)"
  [[ "$status" =~ ^[A-Z_]+$ ]] || clean_host_die 26 "refusing to write a bad status"
  [[ "$cycle" =~ ^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$ ]] || clean_host_die 26 "refusing to write a bad cycle id"
  if [[ -n "$run_base" ]]; then
    [[ "$run_base" =~ ^[A-Za-z0-9_-]{1,80}\.json$ ]] || clean_host_die 26 "refusing to write a bad run file name"
  fi
  local tmp="${file}.tmp"
  {
    printf 'status=%s\n' "$status"
    printf 'cycle_id=%s\n' "$cycle"
    printf 'run_file=%s\n' "$run_base"
    printf 'classification=%s\n' "$CLEAN_HOST_CLASSIFICATION"
    printf 'evidence_tier=%s\n' "$CLEAN_HOST_EVIDENCE_TIER"
    printf 'stranger_host=%s\n' "$CLEAN_HOST_STRANGER_HOST"
    printf 'phantom_box=%s\n' "$CLEAN_HOST_PHANTOM_BOX"
    printf 'customer_validation=%s\n' "$CLEAN_HOST_CUSTOMER_VALIDATION"
    printf 'independent_verifier=%s\n' "$CLEAN_HOST_INDEPENDENT_VERIFIER"
  } >"$tmp"
  chmod 0600 "$tmp"
  mv -f "$tmp" "$file"
}

clean_host_field() {
  local key="$1"
  local file
  file="$(clean_host_state_file)"
  [[ -f "$file" ]] || return 1
  local line
  line="$(grep -E "^${key}=" "$file" | head -n 1 || true)"
  printf '%s\n' "${line#"${key}"=}"
}

clean_host_read_state() {
  local file
  file="$(clean_host_state_file)"
  [[ -f "$file" ]] || clean_host_die 26 "lab state is absent; run reset"
  CLEAN_HOST_STATUS="$(clean_host_field status)"
  CLEAN_HOST_CYCLE_ID="$(clean_host_field cycle_id)"
  CLEAN_HOST_RUN_FILE="$(clean_host_field run_file)"
  [[ "$CLEAN_HOST_STATUS" =~ ^(RESET_READY|CAPTURED|RETAINED|STOPPED)$ ]] || clean_host_die 26 "lab state status is not a known value"
  [[ "$CLEAN_HOST_CYCLE_ID" =~ ^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$ ]] || clean_host_die 26 "lab state cycle id is not valid"
  local tier stranger phantom
  tier="$(clean_host_field evidence_tier)"
  stranger="$(clean_host_field stranger_host)"
  phantom="$(clean_host_field phantom_box)"
  [[ "$tier" == "UNSET" ]] || clean_host_die 27 "lab state evidence_tier must stay UNSET"
  [[ "$stranger" == "NOT_RUN" ]] || clean_host_die 20 "lab state stranger_host must stay NOT_RUN"
  [[ "$phantom" == "EXCLUDED" ]] || clean_host_die 21 "lab state phantom_box must stay EXCLUDED"
}

clean_host_new_cycle_id() {
  local stamp suffix
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  suffix="$(node -e 'process.stdout.write(require("node:crypto").randomBytes(4).toString("hex"))')"
  printf '%s-%s\n' "$stamp" "$suffix"
}

clean_host_banner() {
  printf 'classification=%s\n' "$CLEAN_HOST_CLASSIFICATION"
  printf 'evidence_tier=%s\n' "$CLEAN_HOST_EVIDENCE_TIER"
  printf 'stranger_host=%s\n' "$CLEAN_HOST_STRANGER_HOST"
  printf 'phantom_box=%s\n' "$CLEAN_HOST_PHANTOM_BOX"
  printf 'customer_validation=%s\n' "$CLEAN_HOST_CUSTOMER_VALIDATION"
  printf 'independent_verifier=%s\n' "$CLEAN_HOST_INDEPENDENT_VERIFIER"
}

clean_host_operator_snapshot() {
  local dir="$CLEAN_HOST_OPERATOR_HOME/.vantio"
  if [[ ! -e "$dir" ]]; then
    printf 'ABSENT\n'
    return 0
  fi
  find "$dir" -printf '%p %T@ %s\n' | sort | sha256sum | awk '{print $1}'
}

clean_host_isolate_home() {
  local home_dir="$1"
  export HOME="$home_dir"
  unset VANTIO_HOME
  unset VANTIO_API_KEY
  unset VANTIO_IDENTITY
  unset VANTIO_INGEST_URL
  unset VANTIO_API_BASE
  unset VANTIO_SOAK_LOCAL
  unset VANTIO_CLOUD_INGEST
  unset VANTIO_AUDIT_MODE
  unset VANTIO_TELEMETRY
  unset VANTIO_EXTRA_LLM_HOSTS
  unset VANTIO_TRACE_ID
  unset VANTIO_MOCK_LLM_PORT
  unset STRANGER_HOST
  unset VANTIO_STRANGER_HOST
  unset CLEAN_HOST_STRANGER_HOST_REQUEST
  export VANTIO_TELEMETRY_DISABLED=1
  export DO_NOT_TRACK=1
}
