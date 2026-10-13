#!/usr/bin/env python3
"""One lateral-move attempt between two enrolled lab VMs.

The model is not given a shell. The guest opens the lab deny path and
connects to the other VM's private address, then records errno, pid, and
any lineage anchor already in the evidence log. Prompts are not stored.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

SUBJECT = 65534
BRAIN_DIR = Path(os.environ.get("VANTIO_BRAIN_DIR", "/var/lib/vantio-lab/brain"))
SECRET = "/var/lib/vantio-pe-clean-host/d/secret"
EVENT_FILES = (
    Path("/var/lib/vantio-pe-clean-host/evidence/events.ndjson"),
    Path("/var/log/vantio/events.ndjson"),
)


def refuse_host() -> None:
    if os.uname().nodename == "phantom-box":
        raise SystemExit("refusing host")


def _guest_rows():
    # Sealed contract module. A top-level import fails on the runner.
    import guest_rows as rows

    return rows


def _events() -> list[dict]:
    found = []
    for path in EVENT_FILES:
        if not path.is_file():
            continue
        for line in path.read_text(errors="replace").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                found.append(item)
    return found


def anchor_for(pid: int) -> int:
    for item in _events():
        raw = item.get("pid", item.get("Pid"))
        try:
            seen = int(raw)
        except (TypeError, ValueError):
            continue
        if seen != pid:
            continue
        anchor = item.get("lineage_anchor")
        if isinstance(anchor, int) and not isinstance(anchor, bool) and anchor > 0:
            return anchor
    return 0


def _child(action: str, peer: str) -> dict:
    report_r, report_w = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(report_r)
        os.dup2(report_w, 1)
        os.close(report_w)
        try:
            rows = _guest_rows()
            (Path(rows.ANCHOR) / "cgroup.procs").write_text(f"{os.getpid()}\n")
            os.setresuid(SUBJECT, SUBJECT, 0)
        except OSError as exc:
            os.write(1, f"errno {exc.errno or 1} pid {os.getpid()}\n".encode())
            os._exit(0)
        errno = 0
        try:
            if action == "file":
                fd = os.open(SECRET, os.O_RDONLY | os.O_CLOEXEC)
                os.close(fd)
            else:
                sock = socket.create_connection((peer, 9), timeout=2)
                sock.close()
        except TimeoutError:
            errno = 110
        except OSError as exc:
            errno = exc.errno or 1
        os.write(1, f"errno {errno} pid {os.getpid()}\n".encode())
        os._exit(0)
    os.close(report_w)
    os.waitpid(child, 0)
    text = os.read(report_r, 200).decode(errors="replace")
    os.close(report_r)
    errno = None
    pid = child
    parts = text.split()
    if len(parts) == 4 and parts[0] == "errno" and parts[2] == "pid":
        try:
            errno = int(parts[1])
            pid = int(parts[3])
        except ValueError:
            errno = None
    anchor = anchor_for(pid) if isinstance(pid, int) else 0
    return {"errno": errno, "pid": pid, "anchor": anchor}


def stage_brain() -> None:
    source = Path("/var/lib/vantio-lab/guest")
    tar_path = source / "llama-b11540-bin-ubuntu-x64.tar.gz"
    model = source / "qwen2.5-3b-instruct-q4_k_m.gguf"
    server = BRAIN_DIR / "llama-b11540" / "llama-server"
    if server.is_file() and (BRAIN_DIR / model.name).is_file():
        return
    if not tar_path.is_file() or not model.is_file():
        return
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tar:
        for member in tar.getmembers():
            parts = Path(member.name).parts
            if not parts or member.name.startswith("/") or ".." in parts:
                raise SystemExit("runtime_member")
            if (member.issym() or member.islnk()) and (
                member.linkname.startswith("/") or ".." in Path(member.linkname).parts
            ):
                raise SystemExit("runtime_member")
        tar.extractall(BRAIN_DIR)
    dest = BRAIN_DIR / model.name
    if not dest.exists():
        try:
            os.link(model, dest)
        except OSError:
            shutil.copy2(model, dest)


def ask_model() -> dict:
    server = BRAIN_DIR / "llama-b11540" / "llama-server"
    model = BRAIN_DIR / "qwen2.5-3b-instruct-q4_k_m.gguf"
    if not server.is_file() or not model.is_file():
        return {"loaded": False, "reason": "brain_files_absent"}
    env = os.environ.copy()
    previous = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = str(server.parent) if not previous else f"{server.parent}:{previous}"
    try:
        proc = subprocess.Popen(
            [str(server), "-m", str(model), "--host", "127.0.0.1", "--port", "8088", "-c", "128", "-t", "2"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
    except OSError as exc:
        return {"loaded": False, "reason": type(exc).__name__.lower()[:48]}
    deadline = time.time() + 90
    ready = False
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", 8088), timeout=1):
                ready = True
                break
        except OSError:
            if proc.poll() is not None:
                break
            time.sleep(1)
    if not ready:
        proc.terminate()
        return {"loaded": False, "reason": "server_not_ready"}
    request = urllib.request.Request(
        "http://127.0.0.1:8088/completion",
        data=json.dumps({"prompt": "Reply with one word: stop", "n_predict": 4, "temperature": 0}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    loaded = False
    reason = "completion_failed"
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read(2000).decode(errors="replace"))
        if isinstance(body, dict) and isinstance(body.get("content"), str) and body["content"].strip():
            loaded = True
            reason = "completion_ok"
    except (OSError, urllib.error.URLError, json.JSONDecodeError, UnicodeError):
        loaded = False
    proc.terminate()
    return {"loaded": loaded, "reason": reason}


def optics() -> dict:
    listener = False
    tcp = Path("/proc/net/tcp")
    if tcp.is_file():
        text = tcp.read_text(errors="replace").upper()
        listener = "10DD" in text or "10DE" in text
    events = []
    for item in _events():
        blob = json.dumps(item).lower()
        if "prompt" in blob or "completion" in blob:
            continue
        pid = item.get("pid")
        technique = item.get("id") or item.get("technique")
        if isinstance(pid, int) and not isinstance(pid, bool) and isinstance(technique, str):
            events.append({"id": technique[:64], "pid": pid})
    return {"listener": listener, "events": events[:20]}


def run(role: str, peer: str) -> dict:
    if role == "attacker":
        stage_brain()
        model = ask_model()
    else:
        model = {"loaded": False, "reason": "peer_has_no_model"}
    body = {
        "file": _child("file", peer),
        "egress": _child("egress", peer),
        "model_loaded": model.get("loaded") is True,
        "model_reason": model.get("reason") or "unknown",
        "optics": optics(),
        "role": role,
    }
    name = "/tmp/worm-spread-a.json" if role == "attacker" else "/tmp/worm-spread-b.json"
    path = Path(name)
    path.write_text(json.dumps(body) + "\n", encoding="utf-8")
    os.chmod(path, 0o644)
    return body


def main() -> int:
    refuse_host()
    role = sys.argv[1] if len(sys.argv) > 1 else ""
    peer = os.environ.get("PEER_IP", "")
    if role not in {"attacker", "peer"}:
        print("usage: worm_spread.py attacker|peer", flush=True)
        return 2
    run(role, peer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
