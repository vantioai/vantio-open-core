#!/bin/bash
# Prints one marker line and writes the same facts under /var/lib/vantio-lab.
# The seal and pin arguments are 64 hex characters. This script does not read secrets.
set -euo pipefail
seal=${1:?}
pin=${2:?}
if ! printf '%s' "$seal" | grep -Eq '^[0-9a-f]{64}$'; then
  exit 2
fi
if ! printf '%s' "$pin" | grep -Eq '^[0-9a-f]{64}$'; then
  exit 2
fi
mkdir -p /var/lib/vantio-lab
printf '%s\n' "{\"seal\":\"${seal}\",\"pin\":\"${pin}\"}" > /var/lib/vantio-lab/marker.json
line="vantio-lab-marker seal=${seal} pin=${pin}"
printf '%s\n' "$line"
if [ -w /dev/console ]; then
  printf '%s\n' "$line" > /dev/console || true
fi
logger -t vantio-lab "$line" || true
