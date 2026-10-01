"""Host check for the observe container after docker run returns.

``docker run -d`` exits 0 when the daemon accepts the container. The same exit
is 0 when that process has already stopped. This check reads the container.
A stopped process is not a healthy loader. A detached container that is still
starting is read again until the loader, the known bpffs pins, and clsact are
present, or until the wait ends.
"""

from __future__ import annotations

from collections.abc import Callable

from vantio_install import constants
from vantio_install.pe_apparmor import inspect_is_observe_container, parse_observe_inspect

OBSERVE_READY_WAIT_S = 20.0
OBSERVE_READY_POLL_S = 0.25

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
        if _healthy(sample):
            return "VERIFIED"
        last_unknown = life == "unknown"
        if clock() - started >= wait_s:
            return "UNKNOWN" if last_unknown else "NOT_VERIFIED"
        sleeper(poll_s)
    return "UNKNOWN" if last_unknown else "NOT_VERIFIED"


def _healthy(sample: dict) -> bool:
    return (
        sample.get("lifecycle") == "detached"
        and sample.get("security_ok") is True
        and sample.get("pins") == list(constants.BPF_PINS)
        and sample.get("loader") is True
        and sample.get("clsact") is True
    )
