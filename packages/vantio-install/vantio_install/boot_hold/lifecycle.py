"""Enforcement lifecycle. Observe-ready is not a protected host."""

from __future__ import annotations

OBSERVE_READY = "OBSERVE_READY"
ENFORCEMENT_LOADING = "ENFORCEMENT_LOADING"
ENFORCEMENT_ATTACHED_NOT_PROVED = "ENFORCEMENT_ATTACHED_NOT_PROVED"
ENFORCEMENT_READY = "ENFORCEMENT_READY"
HELD = "HELD"
DEGRADED = "DEGRADED"
BREAK_GLASS = "BREAK_GLASS"
OPTED_OUT = "OPTED_OUT"
FAILED_SAFE = "FAILED_SAFE"

LIFECYCLE_STATES = (
    OBSERVE_READY,
    ENFORCEMENT_LOADING,
    ENFORCEMENT_ATTACHED_NOT_PROVED,
    ENFORCEMENT_READY,
    HELD,
    DEGRADED,
    BREAK_GLASS,
    OPTED_OUT,
    FAILED_SAFE,
)


def enforcement_lifecycle(
    *,
    opted_out: bool = False,
    break_glass: bool = False,
    failed_safe: bool = False,
    hold_active: bool = False,
    observe_ready: bool = False,
    ready: dict | None = None,
) -> str:
    """Pick one lifecycle state. An observe sample does not become enforcement."""

    verdict = ready if isinstance(ready, dict) else {}
    if failed_safe:
        return FAILED_SAFE
    if opted_out:
        return OPTED_OUT
    if break_glass:
        return BREAK_GLASS
    if verdict.get("enforce_ready") is True:
        return ENFORCEMENT_READY
    if verdict.get("reason") == "audit-not-enforce" and observe_ready:
        return OBSERVE_READY
    if verdict.get("program_attached") is True and verdict.get("loader_up") is True:
        return ENFORCEMENT_ATTACHED_NOT_PROVED
    if verdict.get("loader_up") is True and verdict.get("program_loaded") is not True:
        return ENFORCEMENT_LOADING
    if observe_ready and verdict.get("enforce_ready") is not True:
        return OBSERVE_READY
    if hold_active:
        return HELD
    return DEGRADED
