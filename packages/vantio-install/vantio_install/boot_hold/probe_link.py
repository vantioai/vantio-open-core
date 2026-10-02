"""Local deny-probe endpoint. Documentation range, not RFC1918, removed after the check."""

from __future__ import annotations

import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

NS = "vantio-deny-probe"
HOST_IFACE = "vantio-probe"
PEER_IFACE = "vantio-peer"
HOST_CIDR = "198.51.100.1/30"
PEER_CIDR = "198.51.100.2/30"
PROBE_HOST = "198.51.100.2"
PROBE_PORT = 18080

_LISTENER = (
    "import socket\n"
    "import time\n"
    "s=socket.socket()\n"
    "s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
    f"s.bind(({PROBE_HOST!r}, {PROBE_PORT}))\n"
    "s.listen(8)\n"
    "s.settimeout(0.5)\n"
    "end=time.monotonic()+20\n"
    "while time.monotonic()<end:\n"
    "    try:\n"
    "        c, _ = s.accept()\n"
    "        c.close()\n"
    "    except OSError:\n"
    "        continue\n"
)


def _note(detail: str) -> None:
    path = Path("/run/vantio/probe-setup.txt")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(detail + "\n", encoding="utf-8")
    except OSError:
        return


@dataclass
class LocalProbe:
    host: str
    port: int
    ready: bool
    detail: str
    _proc: subprocess.Popen[str] | None
    _sleeper: subprocess.Popen[str] | None = None

    def close(self) -> None:
        for proc in (self._proc, self._sleeper):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
        self._proc = None
        self._sleeper = None
        ip = _ip()
        subprocess.run([ip, "link", "del", HOST_IFACE], check=False, capture_output=True, text=True)
        link = Path("/run/netns") / NS
        try:
            link.unlink()
        except OSError:
            return


def _ip() -> str:
    if Path("/usr/sbin/ip").is_file():
        return "/usr/sbin/ip"
    if Path("/sbin/ip").is_file():
        return "/sbin/ip"
    return "ip"


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, check=False, capture_output=True, text=True)


def _reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def _fail(detail: str, sleeper: subprocess.Popen[str] | None) -> LocalProbe:
    _note(detail)
    probe = LocalProbe(PROBE_HOST, PROBE_PORT, False, detail[:400], None, sleeper)
    probe.close()
    return probe


def open_local_probe() -> LocalProbe:
    """Stand up a listener the unenrolled path can reach. Failure leaves nothing behind.

    The namespace is a symlinked process netns, the same shape as the clean-host
    pass. ``ip netns add`` is not required.
    """

    ip = _ip()
    Path("/run/netns").mkdir(parents=True, exist_ok=True)
    _run([ip, "link", "del", HOST_IFACE])
    link = Path("/run/netns") / NS
    try:
        link.unlink()
    except OSError:
        pass
    sleeper = subprocess.Popen(
        ["unshare", "--net", "sleep", "40"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    time.sleep(0.1)
    if sleeper.poll() is not None:
        err = ""
        if sleeper.stderr is not None:
            err = (sleeper.stderr.read() or "").strip()
        return _fail(f"unshare exited {sleeper.returncode} {err}"[:400], None)
    try:
        link.symlink_to(f"/proc/{sleeper.pid}/ns/net")
    except OSError as exc:
        return _fail(f"netns symlink failed: {exc}", sleeper)
    steps = (
        [ip, "link", "add", HOST_IFACE, "type", "veth", "peer", "name", PEER_IFACE],
        [ip, "addr", "add", HOST_CIDR, "dev", HOST_IFACE],
        [ip, "link", "set", HOST_IFACE, "up"],
        [ip, "link", "set", PEER_IFACE, "netns", NS],
        [ip, "netns", "exec", NS, "ip", "link", "set", "lo", "up"],
        [ip, "netns", "exec", NS, "ip", "addr", "add", PEER_CIDR, "dev", PEER_IFACE],
        [ip, "netns", "exec", NS, "ip", "link", "set", PEER_IFACE, "up"],
    )
    for argv in steps:
        completed = _run(argv)
        if completed.returncode != 0:
            detail = ((completed.stderr or completed.stdout or "").strip() or "exit")[:240]
            return _fail(f"{' '.join(argv)} :: {detail}", sleeper)
    proc = subprocess.Popen(
        [ip, "netns", "exec", NS, "/usr/bin/python3", "-c", _LISTENER],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            err = ""
            if proc.stderr is not None:
                err = (proc.stderr.read() or "").strip()[:200]
            return _fail(f"listener-exited {err}".strip(), sleeper)
        if _reachable(PROBE_HOST, PROBE_PORT):
            _note("ready")
            return LocalProbe(PROBE_HOST, PROBE_PORT, True, "ready", proc, sleeper)
        time.sleep(0.05)
    proc.terminate()
    return _fail("listener-unreachable", sleeper)
