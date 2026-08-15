#!/usr/bin/env bash
# Sight Loop offline prove path — Vantio Optics (observe only, no API key).
# Wrap → capture → export without hitting real LLM endpoints.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INTERCEPTOR="${ROOT}/packages/vantio-cli/bin/interceptor.cjs"
AGENT="${ROOT}/scripts/fixtures/minimal-agent.js"
PROVE="${ROOT}/packages/vantio-cli/bin/vantio.js"

if [[ ! -f "$INTERCEPTOR" || ! -f "$AGENT" || ! -f "$PROVE" ]]; then
  echo "sight-loop-prove: run from vantio-open-core checkout" >&2
  exit 1
fi

PORT_FILE="$(mktemp)"
trap 'rm -f "$PORT_FILE"; kill "$MOCK_PID" 2>/dev/null || true' EXIT

PORT_FILE="$PORT_FILE" node -e "
const http = require('http');
const fs = require('fs');
const portFile = process.env.PORT_FILE;
const server = http.createServer((req, res) => {
  const body = JSON.stringify({ id: 'sight-loop-fixture', choices: [{ message: { content: 'ok' } }] });
  res.writeHead(200, { 'content-type': 'application/json', 'content-length': Buffer.byteLength(body) });
  res.end(body);
});
server.listen(0, '127.0.0.1', () => {
  fs.writeFileSync(portFile, String(server.address().port));
});
" &
MOCK_PID=$!

for _ in $(seq 1 50); do
  [[ -s "$PORT_FILE" ]] && break
  sleep 0.1
done

MOCK_PORT="$(cat "$PORT_FILE")"
if [[ -z "$MOCK_PORT" ]]; then
  echo "sight-loop-prove: mock LLM server failed to start" >&2
  exit 1
fi
MOCK_HOST="127.0.0.1:${MOCK_PORT}"
TRACE_ID="0x$(openssl rand -hex 8 2>/dev/null || echo sightloop00000001)"

echo "== Sight Loop prove (Vantio Optics · observe only) =="
echo "   mock LLM host: ${MOCK_HOST} (registered via VANTIO_EXTRA_LLM_HOSTS=127.0.0.1)"
echo "   trace_id:      ${TRACE_ID}"
echo

# Step 1–2: wrap + capture (direct interceptor inject — no saved Pro key)
# VANTIO_EXTRA_LLM_HOSTS uses hostname only (matches URL.hostname in interceptor).
VANTIO_TRACE_ID="$TRACE_ID" \
VANTIO_SUMMARY=1 \
VANTIO_EXTRA_LLM_HOSTS="127.0.0.1" \
VANTIO_MOCK_LLM_PORT="$MOCK_PORT" \
node --require "$INTERCEPTOR" "$AGENT"

echo
echo "== Step 3: export (vantio prove) =="
node "$PROVE" prove --run="$TRACE_ID" --format=md

echo
echo "== Step 3b: inspect (search / tail) =="
node "$PROVE" search --run="$TRACE_ID" --json | head -c 2000
echo
node "$PROVE" tail --run="$TRACE_ID" -n 5 --json | head -c 2000
echo

echo
echo "✓ Sight Loop prove path complete (OBSERVED events only — no enforce)"
