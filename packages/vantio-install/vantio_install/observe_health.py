"""Host check for the observe container after docker run returns.

The sealed loader is a long-running process. It pins the known maps, attaches
its programs, prints that Phantom Engine is active, and then loops until it is
stopped. A bootstrap that exits after attach is not this contract.

``docker run -d`` exits 0 when the daemon accepts the container. The same exit
is 0 when that process has already stopped. This check does not read that exit
code. A stopped or dead container is not protected, including when pins from
an earlier process are still on bpffs.

A detached container that is still starting is read again until the contract
below is true, or until the wait ends. The wait is 20 seconds because the
exported loader log from container ``e63160e38f8d`` already contained the
active banner while that container had been up for about a second. The check
returns as soon as the contract is true. The bound is not a longer timeout.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from vantio_install import constants
from vantio_install.pe_apparmor import inspect_is_observe_container, parse_observe_inspect

OBSERVE_READY_WAIT_S = 20.0
OBSERVE_READY_POLL_S = 0.25
PIN_MTIME_SKEW_S = 2.0

_STOPPED = frozenset({"exited", "dead", "removing"})
_STARTING = frozenset({"created", "restarting", "paused"})


def observe_lifecycle(parsed: dict | None) -> str:
    """Return detached, stopped, starting, or unknown from one inspect parse."""
    if not parsed:
        return "unknown"
    status = parsed["status"]
    if status in _STOPPED:
        return "stopped"
    if status == "running" and parsed["running"] and parsed["pid"] > 0:
        return "detached"
    if status in _STARTING:
        return "starting"
    if parsed["pid"] == 0 and not parsed["running"]:
        return "stopped"
    return "unknown"


def observe_sample_from_inspect(text: str | None) -> tuple[str, bool]:
    """Lifecycle and whether the inspect line is a running observe container."""
    parsed = parse_observe_inspect(text or "")
    security_ok = bool(text) and inspect_is_observe_container(text or "")
    return observe_lifecycle(parsed), security_ok


def parse_docker_time(value: str) -> float | None:
    """Parse a Docker timestamp. ``0001-01-01`` and blank values are absent."""
    text = value.strip()
    if not text or text.startswith("0001-"):
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if "." in text:
        head, tail = text.split(".", 1)
        split_at = len(tail)
        for index, char in enumerate(tail):
            if char in "+-":
                split_at = index
                break
        frac = tail[:split_at]
        rest = tail[split_at:]
        text = f"{head}.{(frac + '000000')[:6]}{rest}"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def pins_are_current(mtimes: list[float], started_epoch: float | None) -> bool:
    """True when every known pin was created for this container start.

    A pin left by a previous install has an older mtime. A missing pin is not
    current. The loader replaces pins when it starts, so a running install owns
    the names whose mtimes are at or after ``StartedAt``.
    """
    if started_epoch is None or len(mtimes) != len(constants.BPF_PINS):
        return False
    floor = started_epoch - PIN_MTIME_SKEW_S
    return all(mtime >= floor for mtime in mtimes)


def facts_from_logs(text: str, iface: str) -> dict[str, bool]:
    """Read the sealed loader's own startup lines. Empty logs are not ready."""
    observe_paths = "Path observe maps loaded:" in text
    enforce_paths = "Path enforce maps loaded:" in text
    audit = "AUDIT (log only)" in text
    observe_mode = "observe-only mode" in text
    enforce_on = "NODE-WIDE" in text or "SCOPED (drop enrolled)" in text
    return {
        "paths_active": observe_paths and enforce_paths,
        "policy_loaded": audit and observe_mode and not enforce_on,
        "iface_ok": f"iface '{iface}'" in text,
        "cgroup_attached": "sock owner attached:" in text and "/sys/fs/cgroup" in text,
        "self_check": (
            "Phantom Engine active" in text
            and "press Ctrl-C to stop" in text
            and "failed to pin" not in text
        ),
    }


def ready_observe_sample() -> dict:
    """One sample that satisfies the long-running observe contract."""
    return {
        "lifecycle": "detached",
        "security_ok": True,
        "pins": list(constants.BPF_PINS),
        "pins_error": False,
        "pins_current": True,
        "loader": True,
        "clsact": True,
        "programs": True,
        "cgroup_attached": True,
        "paths_active": True,
        "policy_loaded": True,
        "iface_ok": True,
        "self_check": True,
        "boot_hold": "HELD",
        "exit_code": 0,
    }


def readiness_gaps(sample: dict) -> list[str]:
    """Named failures for the last sample. An empty list is the ready contract."""
    life = sample.get("lifecycle")
    if life == "stopped":
        gaps = ["container-stopped"]
        code = sample.get("exit_code")
        if code not in (None, ""):
            gaps.append(f"exit-code-{code}")
        if sample.get("pins"):
            gaps.append("pins-left-after-stop")
        return gaps
    if life == "starting":
        return ["container-starting"]
    if life != "detached":
        return ["container-state-unknown"]
    gaps: list[str] = []
    if sample.get("security_ok") is not True:
        gaps.append("apparmor-profile")
    if sample.get("loader") is not True:
        gaps.append("loader-not-this-container")
    pins = sample.get("pins")
    if pins != list(constants.BPF_PINS):
        have = set(pins or [])
        missing = [name for name in constants.BPF_PINS if name not in have]
        gaps.append("pins-missing:" + ",".join(missing) if missing else "pins-mismatch")
    if sample.get("pins_current") is not True:
        gaps.append("pins-stale")
    if sample.get("clsact") is not True:
        gaps.append("clsact-missing")
    if sample.get("programs") is not True:
        gaps.append("tc-program-missing")
    if sample.get("paths_active") is not True:
        gaps.append("file-paths-not-loaded")
    if sample.get("policy_loaded") is not True:
        gaps.append("policy-not-loaded")
    if sample.get("iface_ok") is not True:
        gaps.append("iface-mismatch")
    if sample.get("self_check") is not True:
        gaps.append("self-check")
    if sample.get("boot_hold") != "HELD":
        gaps.append("boot-hold")
    return gaps


def host_check_failure_text(op_type: str, sample: dict | None) -> str:
    """Say which contract fact failed. Docker's exit code is not the reason."""
    body = sample or {}
    if body.get("pins_error"):
        detail = "bpffs-unreadable"
    else:
        gaps = readiness_gaps(body)
        detail = "; ".join(gaps) if gaps else "no ready sample"
    return (
        f"{op_type} returned exit 0 and the host check did not verify it ({detail}). "
        "Rollback is required."
    )


def wait_for_observe_host(
    sample_fn: Callable[[], dict],
    *,
    wait_s: float,
    poll_s: float,
    clock: Callable[[], float],
    sleeper: Callable[[float], None],
) -> str:
    """VERIFIED, NOT_VERIFIED, or UNKNOWN. Exit 0 from docker run is not an input."""
    if wait_s < 0:
        wait_s = 0.0
    if poll_s <= 0:
        poll_s = OBSERVE_READY_POLL_S
    started = clock()
    limit = int(wait_s / poll_s) + 2
    last_unknown = True
    for _ in range(limit):
        sample = sample_fn()
        if sample.get("pins_error"):
            return "UNKNOWN"
        life = sample.get("lifecycle")
        if life == "stopped":
            return "NOT_VERIFIED"
        if not readiness_gaps(sample):
            return "VERIFIED"
        last_unknown = life == "unknown"
        if clock() - started >= wait_s:
            return "UNKNOWN" if last_unknown else "NOT_VERIFIED"
        sleeper(poll_s)
    return "UNKNOWN" if last_unknown else "NOT_VERIFIED"
