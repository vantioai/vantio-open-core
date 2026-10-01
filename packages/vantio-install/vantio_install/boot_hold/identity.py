"""Who may change the boot hold."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from vantio_install.boot_hold.constants import SLICE
from vantio_install.boot_hold.errors import BootHoldError


@dataclass(frozen=True)
class Caller:
    euid: int
    pid: int
    comm: str
    cgroup_text: str
    pid1_comm: str

    def refusal(self) -> str | None:
        if self.euid != 0:
            return "This action needs a root operator on the host."
        if self.pid1_comm not in {"systemd", "init"}:
            return "This action was refused because the caller is outside the host init namespace."
        if SLICE in self.cgroup_text:
            return "This action was refused because the caller is an enrolled workload."
        return None


def read_host_caller() -> Caller:
    fixture = os.environ.get("VANTIO_BOOT_HOLD_CALLER_FIXTURE")
    if os.environ.get("VANTIO_BOOT_HOLD_ALLOW_CALLER_FIXTURE") == "1" and fixture:
        data = json.loads(Path(fixture).read_text(encoding="utf-8"))
        return Caller(
            euid=int(data["euid"]),
            pid=int(data.get("pid", 1)),
            comm=str(data.get("comm", "vantio-boot-hold")),
            cgroup_text=str(data.get("cgroup_text", "0::/system.slice/ssh.service")),
            pid1_comm=str(data.get("pid1_comm", "systemd")),
        )
    cgroup = Path("/proc/self/cgroup").read_text(encoding="utf-8", errors="replace")
    pid1 = Path("/proc/1/comm").read_text(encoding="utf-8", errors="replace").strip()
    comm = Path("/proc/self/comm").read_text(encoding="utf-8", errors="replace").strip()
    return Caller(euid=os.geteuid(), pid=os.getpid(), comm=comm or "unknown", cgroup_text=cgroup, pid1_comm=pid1 or "unknown")


def require_operator(caller: Caller) -> None:
    reason = caller.refusal()
    if reason:
        raise BootHoldError(reason, exit_code=4, state="FAILED_SAFE")
