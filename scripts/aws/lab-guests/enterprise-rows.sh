#!/bin/bash
# Verify the policy-allow seal and run the bundled Enterprise row script.
# The runner copies seal.oci.tar and contract.tar into this directory over
# the Instance Connect session. This script does not fetch either file and
# it does not read a token.
set -euo pipefail
seal=${1:?}
here=$(cd "$(dirname "$0")" && pwd)
stage=/opt/vantio-enterprise
image_name=vantio-phantom-engine:carry-3f5fcb1
trust_sha=2e4a1da7bf44f0bddfc2a3ce3eda007fa6cc1455332f26769bd346fafc297876
if ! printf '%s' "$seal" | grep -Eq '^[0-9a-f]{64}$'; then
  exit 2
fi
test -f "$here/seal.oci.tar"
test -f "$here/contract.tar"
echo "${seal}  ${here}/seal.oci.tar" | sha256sum -c -
if tar -tzf "$here/contract.tar" | grep -E '(^/|(^|/)\.<BS>wait
