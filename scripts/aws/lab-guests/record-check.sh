#!/bin/bash
# Record one soak check on the guest and copy the same line to the console.
# The EC2 console log is off the guest disk, so a shutdown does not erase it.
# Arguments: seq name result [detail]. Detail is letters, digits, and . _ : -
set -euo pipefail
seq=${1:?}
name=${2:?}
result=${3:?}
detail=${4:-}
case "$seq" in
  ''|*[!0-9]*) exit 2 ;;
esac
case "$name" in
  ''|*[!A-Za-z0-9_-]*) exit 2 ;;
esac
case "$result" in
  pass|fail|skip) ;;
  *) exit 2 ;;
esac
case "$detail" in
  *[!A-Za-z0-9_.:-]*) exit 2 ;;
esac
payload=$(printf '{"detail":"%s","name":"%s","result":"%s","seq":%s}' "$detail" "$name" "$result" "$seq")
hash=$(printf '%s' "$payload" | sha256sum | awk '{print $1}')
line="vantio-lab-check seq=${seq} name=${name} result=${result} sha256=${hash}"
mkdir -p /var/lib/vantio-lab/checks
printf '%s\n' "$payload" > "/var/lib/vantio-lab/checks/$(printf '%06d' "$seq").json"
printf '%s\n' "$line" >> /var/lib/vantio-lab/checks.ndjson
printf '%s\n' "$line"
if [ -w /dev/console ]; then
  printf '%s\n' "$line" > /dev/console || true
fi
logger -t vantio-lab "$line" || true
