"""Fixture proc trees for the agent inventory. No container runtime."""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "optics-agent-inventory" / "src"))

CANARY = "CANARYPROMPTT39F3C2A"
BTIME = 1700000000


def ipv4(ip: str, port: int) -> str:
    parts = bytes(int(piece) for piece in ip.split("."))
    return f"{parts[::-1].hex().upper()}:{port:04X}"


def stat_text(pid: int, comm: str, ppid: int, flags: int = 0, start: int = 100) -> str:
    fields = ["S", str(ppid), "0", "0", "0", "-1", str(flags), *["0"] * 12, str(start), *["0"] * 8]
    return f"{pid} ({comm}) " + " ".join(fields) + "\n"


class ProcTree:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.proc = root / "proc"
        self.proc.mkdir()
        (self.proc / "stat").write_text(f"btime {BTIME}\n", encoding="utf-8")
        self_dir = self.proc / "self"
        self_dir.mkdir()
        (self_dir / "status").write_text("NSpid:\t1\n", encoding="utf-8")
        self.mountinfo = root / "mountinfo"
        self.mountinfo.write_text("36 35 0:1 / /proc rw,nosuid - proc proc rw\n", encoding="utf-8")
        self._bins = root / "bins"
        self._bins.mkdir()

    def add(
        self,
        pid: int,
        *,
        ppid: int = 1,
        comm: str = "sleep",
        exe: str = "sleep",
        argv: list[str] | None = None,
        cgroup: str = "0::/user.slice/session.scope\n",
        environ: dict[str, str] | None = None,
        tcp: str = "",
        sockets: list[str] | None = None,
        hosts: str | None = None,
        hostname: str | None = None,
        mcp_rel: str | None = None,
        mcp_body: dict | None = None,
        flags: int = 0,
        start: int = 100,
        nspid: str = "1",
        omit_exe: bool = False,
    ) -> Path:
        proc = self.proc / str(pid)
        proc.mkdir()
        (proc / "status").write_text(
            f"Name:\t{comm}\nPPid:\t{ppid}\nNSpid:\t{nspid}\n",
            encoding="utf-8",
        )
        (proc / "stat").write_text(stat_text(pid, comm, ppid, flags, start), encoding="utf-8")
        tokens = argv if argv is not None else [comm]
        (proc / "cmdline").write_bytes(b"\0".join(token.encode() for token in tokens) + b"\0")
        env_blob = b"".join(f"{key}={value}\0".encode() for key, value in (environ or {}).items())
        (proc / "environ").write_bytes(env_blob)
        (proc / "cgroup").write_text(cgroup, encoding="utf-8")
        if not omit_exe:
            folder = self._bins / str(pid)
            folder.mkdir()
            binary = folder / exe
            binary.write_text("bin", encoding="utf-8")
            (proc / "exe").symlink_to(binary)
        fd_dir = proc / "fd"
        fd_dir.mkdir()
        for index, inode in enumerate(sockets or []):
            (fd_dir / str(index)).symlink_to(f"socket:[{inode}]")
        net = proc / "net"
        net.mkdir()
        header = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
        (net / "tcp").write_text(header + tcp, encoding="utf-8")
        root_dir = self.root / f"root-{pid}"
        etc = root_dir / "etc"
        etc.mkdir(parents=True)
        (etc / "hosts").write_text(hosts or "127.0.0.1 localhost\n", encoding="utf-8")
        if hostname:
            (etc / "hostname").write_text(hostname + "\n", encoding="utf-8")
        (proc / "root").symlink_to(root_dir)
        cwd = self.root / f"cwd-{pid}"
        cwd.mkdir()
        if mcp_rel and mcp_body is not None:
            target = cwd / mcp_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(mcp_body), encoding="utf-8")
        (proc / "cwd").symlink_to(cwd)
        return proc

    def deny(self, path: Path) -> None:
        os.chmod(path, 0)
        if os.geteuid() != 0:
            subprocess.run(["sudo", "-n", "chown", "root:root", str(path)], check=True)
            subprocess.run(["sudo", "-n", "chmod", "700", str(path)], check=True)


def tcp_row(local: str, remote: str, state: str, inode: str) -> str:
    return f"   0: {local} {remote} {state} 00000000:00000000 00:00000000 00000000 1000 0 {inode} 1 0 20 4 30 10 -1\n"


def enrollment(host_id: str = "lab-runner", containers: list[str] | None = None, host_processes: bool = False) -> dict:
    return {
        "schema": "vantio.optics.enrollment.v1",
        "host_id": host_id,
        "host_processes": host_processes,
        "containers": containers or [],
    }


def write_json(path: Path, body: dict) -> None:
    path.write_text(json.dumps(body), encoding="utf-8")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
