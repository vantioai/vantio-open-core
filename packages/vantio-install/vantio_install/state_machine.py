"""Stage A transaction transitions. Illegal hops fail closed."""

from __future__ import annotations

from vantio_install.errors import InstallError

# APPLIED → INTERRUPTED, re-verify hops, and VERIFYING_REMOVAL → FAILED_SAFE
# are fail-closed extensions so a dead process or an UNKNOWN probe cannot
# sit in a success-shaped state.
TRANSITIONS: dict[str, set[str]] = {
    "CREATED": {"PREFLIGHTING"},
    "PREFLIGHTING": {
        "PREFLIGHT_READY",
        "PREFLIGHT_READY_WITH_LIMITATIONS",
        "PREFLIGHT_BLOCKED",
        "UNSUPPORTED",
        "FAILED_SAFE",
        "INTERRUPTED",
    },
    "PREFLIGHT_READY": {"PLANNED", "APPLYING"},
    "PREFLIGHT_READY_WITH_LIMITATIONS": {"PLANNED", "APPLYING"},
    "PREFLIGHT_BLOCKED": {"PREFLIGHTING", "CREATED"},
    "UNSUPPORTED": set(),
    "PLANNED": {"APPLYING", "CREATED"},
    "APPLYING": {"APPLIED", "FAILED_SAFE", "INTERRUPTED", "ROLLING_BACK"},
    "APPLIED": {"HEALTHY", "DEGRADED", "FAILED_SAFE", "INTERRUPTED"},
    "HEALTHY": {"ROLLING_BACK", "UNINSTALLING"},
    "DEGRADED": {"ROLLING_BACK", "UNINSTALLING", "HEALTHY"},
    "FAILED_SAFE": {"ROLLING_BACK", "UNINSTALLING", "CREATED"},
    "ROLLING_BACK": {"ROLLED_BACK", "FAILED_SAFE", "INTERRUPTED"},
    "ROLLED_BACK": {"VERIFYING_REMOVAL", "CREATED"},
    "UNINSTALLING": {"UNINSTALLED", "FAILED_SAFE", "INTERRUPTED"},
    "UNINSTALLED": {"VERIFYING_REMOVAL"},
    "VERIFYING_REMOVAL": {"VERIFIED_REMOVED", "RESIDUAL_PRESENT", "RESIDUAL_FOUND", "FAILED_SAFE"},
    "VERIFIED_REMOVED": {"VERIFYING_REMOVAL"},
    "RESIDUAL_PRESENT": {"VERIFYING_REMOVAL"},
    "RESIDUAL_FOUND": {"VERIFYING_REMOVAL"},
    "INTERRUPTED": {
        "APPLYING",
        "ROLLING_BACK",
        "UNINSTALLING",
        "FAILED_SAFE",
        "PREFLIGHTING",
    },
}

TRANSIENT = frozenset(
    {
        "PREFLIGHTING",
        "APPLYING",
        "ROLLING_BACK",
        "UNINSTALLING",
        "VERIFYING_REMOVAL",
    }
)

SUCCESS_INSTALL_STATES = frozenset({"HEALTHY", "DEGRADED"})


def transition(current: str, target: str) -> None:
    allowed = TRANSITIONS.get(current)
    if allowed is None or target not in allowed:
        raise InstallError(
            f"Cannot move transaction from {current} to {target}.",
            exit_code=10,
            state=current or "FAILED_SAFE",
        )
