#!/bin/bash
# Operator preflight. Stops on the first missing control.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
exec python3 "$here/stranger_host.py" preflight "$@"
