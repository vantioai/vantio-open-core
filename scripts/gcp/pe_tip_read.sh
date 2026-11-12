#!/bin/bash
# Read-only check that the allowlisted Phantom Engine commits are fetchable.
# Uses PE_READ_TOKEN. Does not create a VM, call a cloud CLI, or print the token.
set -euo pipefail

if [[ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" || -n "${GCP_SA_KEY:-}" ]]; then
  echo "static_credentials" >&2
  exit 1
fi
if [[ -z "${PE_READ_TOKEN:-}" || "$PE_READ_TOKEN" == *$'\n'* ]]; then
  echo "pe_read=token_missing"
  exit 1
fi

here=$(cd "$(dirname "$0")" && pwd)
auth=$(printf 'x-access-token:%s' "$PE_READ_TOKEN" | base64 -w0)
unset PE_READ_TOKEN
repo=https://github.com/vantioai/vantio-phantom-engine.git
err=$(mktemp)
out=$(mktemp)
cleanup() {
  rm -f "$err" "$out"
  unset auth || true
}
trap cleanup EXIT

report_git_failure() {
  if grep -Eqi '404|not found|repository not found' "$err"; then
    echo "pe_read=404"
  elif grep -Eqi 'authentication failed|401|403' "$err"; then
    echo "pe_read=auth_failed"
  else
    echo "pe_read=failed"
  fi
}

if ! git -c "http.extraheader=AUTHORIZATION: basic ${auth}" ls-remote "$repo" refs/heads/main >"$out" 2>"$err"; then
  report_git_failure
  exit 1
fi
echo "pe_read=ls-remote"
cat "$out"

mapfile -t shas < <(PYTHONPATH="$here" python3 -c 'import enforcement_proof as ep
for sha in sorted(ep.read_allowlist()):
    print(sha)')
if [[ "${#shas[@]}" -eq 0 ]]; then
  echo "pe_read=allowlist_empty"
  exit 1
fi

for sha in "${shas[@]}"; do
  if [[ ! "$sha" =~ ^[0-9a-f]{40}$ ]]; then
    echo "pe_read=allowlist_sha" >&2
    exit 1
  fi
  dir=$(mktemp -d)
  git -C "$dir" init -q
  if ! git -C "$dir" -c "http.extraheader=AUTHORIZATION: basic ${auth}" fetch --depth=1 "$repo" "$sha" >"$out" 2>"$err"; then
    report_git_failure
    echo "pe_read_sha=$sha"
    exit 1
  fi
  head=$(git -C "$dir" rev-parse FETCH_HEAD)
  if [[ "$head" != "$sha" ]]; then
    echo "pe_read=head_mismatch"
    exit 1
  fi
  echo "pe_read=ok sha=$sha"
  rm -rf "$dir"
done
