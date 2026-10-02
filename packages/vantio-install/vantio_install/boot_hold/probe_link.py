"""Local deny-probe endpoint. Documentation range, not RFC1918, removed after the check."""

from __future__ import annotations

import socket
import subprocess
import time
from dataclasses import dataclass

NS = "vantio-deny-probe"
HOST_IFACE = "vantio-probe"
PEER_IFACE = "vantio-probe-peer"
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


@dataclass
class LocalProbe:
    host: str
    port: int
    ready: bool
    detail: str
    _proc: subprocess.Popen[str] | None

    def close(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        subprocess.run(["ip", "netns", "del", NS], check=False, capture_output=True, text=True)
        subprocess.run(["ip", "link", "del", HOST_IFACE], check=False, capture_output=True, text=True)


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, check=False, capture_output=True, text=True)


def _reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def open_local_probe() -> LocalProbe:
    """Stand up a listener the unenrolled path can reach. Failure leaves nothing behind."""

    _run(["ip", "netns", "del", NS])
    _run(["ip", "link", "del", HOST_IFACE])
    steps = (
        ["ip", "netns", "add", NS],
        ["ip", "link", "add", HOST_IFACE, "type", "veth", "peer", "name", PEER_IFACE],
        ["ip", "link", "set", PEER_IFACE, "netns", NS],
        ["ip", "addr", "add", HOST_CIDR, "dev", HOST_IFACE],
        ["ip", "link", "set", HOST_IFACE, "up"],
        ["ip", "netns", "exec", NS, "ip", "addr", "add", PEER_CIDR, "dev", PEER_IFACE],
        ["ip", "netns", "exec", NS, "ip", "link", "set", PEER_IFACE, "up"],
        ["ip", "netns", "exec", NS, "ip", "link", "set", "lo", "up"],
    )
    for argv in steps:
        completed = _run(argv)
        if completed.returncode != 0:
            probe = LocalProbe(PROBE_HOST, PROBE_PORT, False, " ".join(argv), None)
            probe.close()
            return probe
    proc = subprocess.Popen(
        ["ip", "netns", "exec", NS, "python3", "-c", _LISTENER],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            probe = LocalProbe(PROBE_HOST, PROBE_PORT, False, "listener-exited", proc)
            probe.close()
            return probe
        if _reachable(PROBE_HOST, PROBE_PORT):
            return LocalProbe(PROBE_HOST, PROBE_PORT, True, "ready", proc)
        time.sleep(0.05)
    probe = LocalProbe(PROBE_HOST, PROBE_PORT, False, "listener-unreachable", proc)
    probe.close()
    return probe
