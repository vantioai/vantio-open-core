"""MCP stdio awareness for Python children of `vantio run`.

The Node library evaluates a copy of each complete line. This module does
not listen and does not replace the child process. Observe forwards the
original line. Enforce withholds a blocked line.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_HELPER = Path(__file__).resolve().parent.parent / "mcp-awareness-frame.js"
_LOG_MAX = 1024 * 1024


def install() -> None:
    if os.environ.get("VANTIO_MCP_AWARENESS") not in ("on", "1"):
        return
    if getattr(subprocess, "_vantio_mcp_installed", False):
        return
    subprocess._vantio_mcp_installed = True  # type: ignore[attr-defined]
    mode = os.environ.get("VANTIO_MCP_MODE") if os.environ.get("VANTIO_MCP_MODE") == "enforce" else "observe"
    injection = "block" if os.environ.get("VANTIO_MCP_INJECTION") == "block" else "log"
    rug = "block" if os.environ.get("VANTIO_MCP_RUG_PULL") == "block" else "log"
    sys.stderr.write(
        f"[ ∅ VANTIO ] mcp awareness mode={mode} injection={injection} rug_pull={rug}\n"
    )
    original = subprocess.Popen

    def wrapped(*args, **kwargs):
        proc = original(*args, **kwargs)
        try:
            _attach(proc, args, original)
        except Exception:
            pass
        return proc

    subprocess.Popen = wrapped  # type: ignore[misc]


def _attach(proc: subprocess.Popen, args: tuple, original) -> None:
    stdin = proc.stdin
    if stdin is None or not hasattr(stdin, "write"):
        return
    command = ""
    if args and isinstance(args[0], (list, tuple)) and args[0]:
        command = str(args[0][0])
    elif args and isinstance(args[0], str):
        command = args[0]
    server_id = _server_id(command)
    orig_write = stdin.write
    orig_close = stdin.close
    pending = bytearray()

    def write(data):
        if isinstance(data, str):
            data = data.encode()
        pending.extend(data)
        while b"\n" in pending:
            line, _, rest = bytes(pending).partition(b"\n")
            del pending[: len(line) + 1]
            _emit(proc, server_id, line + b"\n", orig_write, original, stdin)
        return len(data)

    def close():
        if pending:
            tail = bytes(pending)
            pending.clear()
            _emit(proc, server_id, tail, orig_write, original, stdin)
        return orig_close()

    stdin.write = write  # type: ignore[method-assign]
    stdin.close = close  # type: ignore[method-assign]


def _emit(proc, server_id: str, line: bytes, orig_write, original, stdin) -> None:
    verdict = _ask(line, server_id, original)
    records = verdict.get("records") if isinstance(verdict, dict) else []
    if isinstance(records, list):
        _log(records)
    error = verdict.get("error") if isinstance(verdict, dict) else None
    if error:
        _inject(proc, error if isinstance(error, str) else str(error))
        return
    orig_write(_as_stream(line.decode("utf-8", errors="replace"), stdin) if _text(stdin) else line)


def _inject(proc, error: str) -> None:
    """Put the fixed error on the pipe the workload reads. The child keeps the write end."""
    stdout = proc.stdout
    if stdout is None or not hasattr(stdout, "read"):
        return
    bucket = getattr(stdout, "_vantio_inject", None)
    if bucket is None:
        bucket = bytearray()
        stdout._vantio_inject = bucket  # type: ignore[attr-defined]
        orig_read = stdout.read

        def read(*args, **kwargs):
            prefix = bytes(bucket)
            bucket.clear()
            data = orig_read(*args, **kwargs)
            if isinstance(data, str):
                return prefix.decode("utf-8") + (data or "")
            return prefix + (data or b"")

        stdout.read = read  # type: ignore[method-assign]
    bucket.extend(error.encode("utf-8"))


def _text(stream) -> bool:
    return getattr(stream, "encoding", None) not in (None, "")


def _as_stream(text: str, stream):
    if _text(stream):
        return text
    return text.encode("utf-8")


def _ask(line: bytes, server_id: str, original) -> dict:
    node = shutil.which("node")
    enforce = os.environ.get("VANTIO_MCP_MODE") == "enforce"
    if node is None or not _HELPER.is_file():
        return {"records": [], "error": _fixed_error() if enforce else None}
    env = dict(os.environ)
    try:
        proc = original(
            [node, str(_HELPER), server_id],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        out, _err = proc.communicate(line, timeout=5)
    except Exception:
        return {"records": [], "error": _fixed_error() if enforce else None}
    try:
        parsed = json.loads(out.decode("utf-8") if out else "{}")
    except (UnicodeError, json.JSONDecodeError):
        return {"records": [], "error": _fixed_error() if enforce else None}
    if not isinstance(parsed, dict):
        return {"records": [], "error": _fixed_error() if enforce else None}
    return parsed


def _log(records: list) -> None:
    root = os.environ.get("VANTIO_HOME") or str(Path.home() / ".vantio")
    path = Path(root) / "mcp-observations.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        size = path.stat().st_size if path.is_file() else 0
        with path.open("a", encoding="utf-8") as handle:
            for record in records:
                if not isinstance(record, dict) or record.get("schema") != "vantio.mcp_observation.v1":
                    continue
                reason = (record.get("decision") or {}).get("reason")
                if reason in ("ignored_non_json", "empty"):
                    continue
                line = json.dumps(record, separators=(",", ":")) + "\n"
                if size >= _LOG_MAX:
                    return
                handle.write(line)
                size += len(line.encode("utf-8"))
    except OSError:
        return


def _server_id(command: str) -> str:
    base = command.replace("\\", "/").rsplit("/", 1)[-1]
    if base.endswith(".exe"):
        base = base[:-4]
    if base and all(ch.isalnum() or ch in "_.:-" for ch in base) and len(base) <= 64:
        return base
    return "child"


def _fixed_error() -> str:
    return (
        '{"jsonrpc":"2.0","id":null,"error":{"code":-32001,'
        '"message":"vantio_mcp_policy_block","data":{"finding":"policy"}}}\n'
    )
