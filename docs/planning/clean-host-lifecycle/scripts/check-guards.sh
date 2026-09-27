#!/usr/bin/env bash
# Exercise refusals, reset, one temporary loopback cycle, retain, and expire.
# Deletes the temporary lab root before exit.
# Exit 0 does not assign an evidence tier and does not run stranger-host.
set -euo pipefail
umask 077

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIFE="$HERE/lifecycle.sh"
WORK="$(mktemp -d /tmp/clean-host-guard-XXXXXX)"
chmod 0700 "$WORK"
trap 'rm -rf -- "$WORK"' EXIT

fail() {
  printf 'check-guards: %s\n' "$*" >&2
  exit 1
}

expect_code() {
  local want="$1"
  shift
  local out="$WORK/out" err="$WORK/err"
  set +e
  "$@" >"$out" 2>"$err"
  local got=$?
  set -e
  if [[ "$got" -ne "$want" ]]; then
    printf 'check-guards: expected exit %s got %s for:' "$want" "$got" >&2
    printf ' %q' "$@" >&2
    printf '\n' >&2
    cat "$err" >&2 || true
    exit 1
  fi
}

expect_stdout() {
  local needle="$1"
  grep -F -q -- "$needle" "$WORK/out" || fail "stdout missing ${needle}"
}

unset VANTIO_API_KEY VANTIO_IDENTITY VANTIO_INGEST_URL VANTIO_API_BASE \
  VANTIO_SOAK_LOCAL VANTIO_CLOUD_INGEST VANTIO_AUDIT_MODE VANTIO_HOME \
  VANTIO_TELEMETRY VANTIO_EXTRA_LLM_HOSTS VANTIO_TRACE_ID VANTIO_MOCK_LLM_PORT \
  STRANGER_HOST VANTIO_STRANGER_HOST CLEAN_HOST_STRANGER_HOST_REQUEST || true

ROOT="$WORK/lab"
export LAB_ROOT="$ROOT"
operator_before="$HOME/.vantio"
if [[ -e "$operator_before" ]]; then
  before_sum="$(find "$operator_before" -printf '%p %T@ %s\n' | sort | sha256sum | awk '{print $1}')"
else
  before_sum="ABSENT"
fi

expect_code 20 "$LIFE" stranger-host
expect_code 20 env CLEAN_HOST_STRANGER_HOST_REQUEST=1 "$LIFE" preflight
expect_code 21 env VANTIO_SOAK_LOCAL=1 "$LIFE" preflight
expect_code 21 env VANTIO_API_KEY=synthetic "$LIFE" preflight
expect_code 21 env VANTIO_INGEST_URL=http://127.0.0.1:5001 "$LIFE" preflight
expect_code 21 env VANTIO_INGEST_URL=http://127.0.0.1:5001/api "$LIFE" preflight
expect_code 21 env VANTIO_INGEST_URL=http://example.invalid "$LIFE" preflight
expect_code 21 env VANTIO_IDENTITY=synthetic "$LIFE" preflight
expect_code 21 env VANTIO_CLOUD_INGEST=true "$LIFE" preflight
expect_code 23 env VANTIO_TELEMETRY=1 "$LIFE" preflight
expect_code 22 env VANTIO_HOME=/tmp/not-the-lab "$LIFE" preflight
expect_code 30 env VANTIO_EXTRA_LLM_HOSTS=api.openai.com "$LIFE" preflight
expect_code 24 env LAB_ROOT="$HOME" "$LIFE" preflight
expect_code 24 env LAB_ROOT="$HERE/../../../.." "$LIFE" preflight
expect_code 24 env LAB_ROOT=relative/lab "$LIFE" preflight

expect_code 0 "$LIFE" preflight
expect_stdout "classification=CLEAN_HOST_INTERNAL_PROOF"
expect_stdout "evidence_tier=UNSET"
expect_stdout "stranger_host=NOT_RUN"
expect_stdout "phantom_box=EXCLUDED"
expect_stdout "preflight_assigns_evidence_tier=false"

expect_code 0 "$LIFE" reset
expect_stdout "status=RESET_READY"
expect_stdout "reset_assigns_evidence_tier=false"
[[ -d "$ROOT/home" ]] || fail "reset did not create home"
[[ ! -e "$ROOT/home/.vantio" ]] || fail "reset created a data directory before capture"

expect_code 0 "$LIFE" capture
expect_stdout "status=CAPTURED"
expect_stdout "capture_assigns_evidence_tier=false"
[[ -d "$ROOT/home/.vantio/runs" ]] || fail "capture did not write a disposable run"
[[ ! -e "$ROOT/home/.vantio/config.json" ]] || fail "capture wrote config.json"

expect_code 26 "$LIFE" capture

expect_code 0 "$LIFE" retain
expect_stdout "status=RETAINED"
expect_stdout "retain_assigns_evidence_tier=false"
manifest="$(find "$ROOT/retention" -mindepth 2 -maxdepth 2 -type f -name manifest.json | head -n 1)"
[[ -n "$manifest" && -f "$manifest" ]] || fail "manifest missing"
node -e '
const fs = require("node:fs");
const path = process.argv[1];
const body = JSON.parse(fs.readFileSync(path, "utf8"));
const required = {
  environment_class: "CLEAN_HOST_INTERNAL_PROOF",
  evidence_tier: "UNSET",
  stranger_host: "NOT_RUN",
  phantom_box: "EXCLUDED",
  customer_validation: "UNSET",
  independent_verifier: "UNSET",
  requirement_status_label: "INTERNAL_PROOF",
  product_seal: false,
  bookkeeping_sha256_is_a_seal: false,
};
for (const [key, value] of Object.entries(required)) {
  if (body[key] !== value) {
    process.stderr.write(`manifest ${key} = ${JSON.stringify(body[key])}\n`);
    process.exit(1);
  }
}
if (!body.run_file || typeof body.run_file.sha256 !== "string" || body.run_file.sha256.length !== 64) {
  process.exit(1);
}
' "$manifest" || fail "manifest fields"

run_copy="$(find "$ROOT/retention" -mindepth 3 -maxdepth 3 -type f -name '*.json' ! -name manifest.json | head -n 1)"
[[ -n "$run_copy" ]] || fail "retained run missing"
node "$HERE/inspect-run.mjs" "$run_copy" >/dev/null || fail "retained run failed shape check"
if find "$ROOT/retention" -type f \( -name telemetry-id -o -name config.json \) | grep -q .; then
  fail "retention copied an excluded file"
fi

cycle="$(sed -n 's/^cycle_id=//p' "$ROOT/state.env")"
expect_code 29 "$LIFE" expire --all
expect_code 0 "$LIFE" expire --cycle "$cycle"
[[ ! -d "$ROOT/retention/$cycle" ]] || fail "expire left the bundle"
[[ -f "$ROOT/retention/${cycle}.expired" ]] || fail "expire left no tombstone"
if grep -q 'request_bytes\|"calls"' "$ROOT/retention/${cycle}.expired"; then
  fail "tombstone contains run bytes"
fi

expect_code 0 "$LIFE" reset
expect_stdout "status=RESET_READY"

if [[ "$before_sum" == "ABSENT" ]]; then
  [[ ! -e "$operator_before" ]] || fail "operator data directory appeared"
else
  after_sum="$(find "$operator_before" -printf '%p %T@ %s\n' | sort | sha256sum | awk '{print $1}')"
  [[ "$before_sum" == "$after_sum" ]] || fail "operator data directory changed"
fi

printf 'check_guards=PASS\n'
printf 'evidence_tier=UNSET\n'
printf 'stranger_host=NOT_RUN\n'
printf 'phantom_box=EXCLUDED\n'
printf 'temporary_lab_removed_on_exit=true\n'
