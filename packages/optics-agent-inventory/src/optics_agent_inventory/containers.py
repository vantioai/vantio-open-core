"""Container identity from a cgroup line. Names are optional and never required."""

from __future__ import annotations

import re

_PATTERNS = (
    re.compile(r"docker-([0-9a-f]{64})\.scope"),
    re.compile(r"/docker/([0-9a-f]{64})"),
    re.compile(r"libpod-([0-9a-f]{64})"),
    re.compile(r"cri-containerd-([0-9a-f]{64})"),
    re.compile(r"crio-([0-9a-f]{64})\.scope"),
)
_MARKERS = ("kubepods", "crio-", "containerd", "lxc", "machine.slice", "libpod", "docker")
_HEX64 = re.compile(r"[0-9a-f]{64}")


def parse_cgroup(text: str | None) -> tuple[str, str | None]:
    """Return (signal, container_id). signal is present, missing, or host_process."""
    if text is None:
        return "missing", None
    lowered = text.lower()
    for pattern in _PATTERNS:
        match = pattern.search(lowered)
        if match:
            return "present", match.group(1)
    if any(marker in lowered for marker in _MARKERS) or _HEX64.search(lowered):
        return "missing", None
    return "host_process", None
