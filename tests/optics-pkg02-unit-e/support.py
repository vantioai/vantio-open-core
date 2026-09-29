"""Shared helpers for Unit E tests."""

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FUTURE_SRC = ROOT / "packages" / "vantio-agent-sdk-py-future" / "src"
SDK_31 = ROOT / "packages" / "vantio-agent-sdk-py"
NODE_ADAPTER = ROOT / "packages" / "optics-node-adapter" / "src" / "index.cjs"
NODE_CANONICAL = ROOT / "packages" / "optics-record-vocabulary" / "src" / "canonical-json.cjs"
SHARED_FIXTURE = ROOT / "packages" / "vantio-agent-sdk-py-future" / "fixtures" / "shared-semantic-observation.json"
START = "dd3344dcc636136ed22df75e8df3866c993efd27"

if str(FUTURE_SRC) not in sys.path:
    sys.path.insert(0, str(FUTURE_SRC))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def do_GET(self):
        status = 404 if self.path.startswith("/err") else self.server.status_code
        body = b"{}"
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


class LoopbackServer:
    def __init__(self, status):
        self._status = status
        self._server = None
        self._thread = None

    def __enter__(self):
        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._server.status_code = self._status
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.05},
            daemon=True,
        )
        self._thread.start()
        port = self._server.server_address[1]
        return f"http://127.0.0.1:{port}"

    def __exit__(self, exc_type, exc, tb):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)
        return False


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def node_adapter_canonical(value):
    completed = subprocess.run(
        [
            "node",
            "-e",
            "const fs=require('fs');"
            "const {adaptNodeCopy}=require(process.argv[1]);"
            "const {canonicalJson}=require(process.argv[2]);"
            "const input=JSON.parse(fs.readFileSync(0,'utf8'));"
            "const reading=adaptNodeCopy(input);"
            "if(!reading.record){process.stderr.write('no record');process.exit(1);}"
            "process.stdout.write(canonicalJson(reading.record));",
            str(NODE_ADAPTER),
            str(NODE_CANONICAL),
        ],
        input=json.dumps(value),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return completed.stdout


def node_canonical(value):
    completed = subprocess.run(
        [
            "node",
            "-e",
            "const {canonicalJson}=require(process.argv[1]);"
            "process.stdout.write(canonicalJson(JSON.parse(require('fs').readFileSync(0,'utf8'))))",
            str(NODE_CANONICAL),
        ],
        input=json.dumps(value),
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def forbidden_names(value, found=None):
    names = {
        "workflow",
        "status_labels",
        "plane",
        "data_note",
        "residual",
        "prompt",
        "prompts",
        "machine",
        "cost",
        "est_spend_usd",
        "provider_id",
        "opticsStatus",
    }
    if found is None:
        found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in names:
                found.append(key)
            forbidden_names(item, found)
    elif isinstance(value, list):
        for item in value:
            forbidden_names(item, found)
    return found
