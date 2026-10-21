"""Host gate for the T5 lab program.

The gate does not issue the bpf syscall. A caller can pass a fake call to
prove the gate opened. Attaching on a host that is not the Vantio lab
project is refused before that call.
"""

from __future__ import annotations

import importlib.util
import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from t5_kernel.decide import KernelMaps


def _load_seal():
    origin = Path(__file__).resolve().parent
    for parent in (origin, *origin.parents):
        for candidate in (parent / "pe_canonical_seal.py", parent / "scripts" / "release" / "pe_canonical_seal.py"):
            if not candidate.is_file():
                continue
            cached = sys.modules.get("pe_canonical_seal")
            if cached is not None:
                return cached
            spec = importlib.util.spec_from_file_location("pe_canonical_seal", candidate)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules["pe_canonical_seal"] = module
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError("pe_canonical_seal.py")


_SEAL = _load_seal()
LANE_SEAL = _SEAL.lane_seal()
PUBLIC_PIN = _SEAL.public_pin()
LAB_PROJECT = "vantio-lab-oct08"
HOST_CLASS = "vantio-owned"
CGROUP_PREFIX = "/sys/fs/cgroup/vantio-t5-lab.slice/"
CFG_STRUCT = struct.Struct("<Q10I")

FORBIDDEN_CGROUPS = (
    "/sys/fs/cgroup",
    "/sys/fs/cgroup/",
    "/sys/fs/cgroup/system.slice",
    "/sys/fs/cgroup/user.slice",
    "/sys/fs/cgroup/vantio-enrolled.slice",
    "/sys/fs/cgroup/vantio.slice/vantio-enrolled.slice",
)


@dataclass(frozen=True)
class AttachRequest:
    host_class: str
    project: str
    cgroup: str
    hostname: str = ""
    seal: str = ""
    public_pin: str = ""
    execute: bool = False
    maps: KernelMaps | None = None


def pack_cfg(maps: KernelMaps) -> bytes:
    """Match struct t5_cfg in the bpf program."""
    return CFG_STRUCT.pack(
        maps.window_ns,
        1 if maps.enforce else 0,
        maps.max_label,
        maps.max_queries,
        maps.entropy_min_length,
        maps.entropy_userspace,
        len(maps.names),
        len(maps.resolvers),
        len(maps.icmp_destinations),
        len(maps.ports),
        0,
    )


def _partner_markers() -> tuple[str, ...]:
    """VANTIO_PARTNER_MARKERS lists deployment-partner substrings. Unset means none."""
    raw = os.environ.get("VANTIO_PARTNER_MARKERS", "")
    return tuple(item.strip().lower() for item in raw.split(",") if item.strip())


def _dirty(*values: str) -> bool:
    markers = _partner_markers()
    return any(marker in value.lower() for value in values for marker in markers)


def refusal(request: AttachRequest) -> str | None:
    if _dirty(request.host_class, request.project, request.cgroup, request.hostname, request.seal):
        return "partner"
    if request.host_class != HOST_CLASS:
        return "host_class"
    if request.project != LAB_PROJECT:
        return "project"
    cgroup = request.cgroup
    if cgroup in FORBIDDEN_CGROUPS or not cgroup.startswith(CGROUP_PREFIX):
        return "cgroup"
    if cgroup.rstrip("/") == CGROUP_PREFIX.rstrip("/"):
        return "cgroup"
    leaf = cgroup[len(CGROUP_PREFIX) :]
    if not leaf or "/" in leaf or leaf in {".", ".."}:
        return "cgroup"
    if request.public_pin and request.public_pin != PUBLIC_PIN:
        return "public_pin"
    if request.seal and request.seal != LANE_SEAL:
        return "seal"
    if request.seal == PUBLIC_PIN:
        return "seal"
    maps = request.maps
    if maps is None or maps.entropy_userspace != 1:
        return "entropy_userspace"
    return None


def attach_decision(request: AttachRequest, bpf_call=None) -> dict[str, object]:
    reason = refusal(request)
    if reason is not None:
        return {
            "attached": False,
            "reason": reason,
            "label": "Roadmap",
            "bpf_calls": 0,
            "project": LAB_PROJECT,
        }
    if not request.execute:
        return {
            "attached": False,
            "reason": "not_dispatched",
            "label": "Roadmap",
            "bpf_calls": 0,
            "project": LAB_PROJECT,
        }
    if bpf_call is None:
        return {
            "attached": False,
            "reason": "syscall_not_issued",
            "label": "Roadmap",
            "bpf_calls": 0,
            "project": LAB_PROJECT,
        }
    reported = bpf_call(request)
    loaded = isinstance(reported, dict) and reported.get("loaded") is True
    return {
        "attached": loaded,
        "reason": "load_attempted",
        "label": "Lab-only" if loaded else "Roadmap",
        "bpf_calls": 1,
        "verifier": "caller_reported",
        "project": LAB_PROJECT,
    }
