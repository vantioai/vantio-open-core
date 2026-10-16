"""Decision values shared by every T5 case."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str
    enforce_outcome: str
    transmit: bool
    evaluation_failure: bool
    label: str = "Lab-only"

    def as_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "reason": self.reason,
            "enforce_outcome": self.enforce_outcome,
            "transmit": self.transmit,
            "evaluation_failure": self.evaluation_failure,
            "label": self.label,
        }


def allow(reason: str = "policy_permits") -> Decision:
    return Decision("ALLOW", reason, "allow", True, False)


def deny_classified(reason: str, mode: str) -> Decision:
    if mode == "observe":
        return Decision("OBSERVE_WOULD_DENY", reason, "fail_closed", True, False)
    return Decision("DENY", reason, "fail_closed", False, False)


def deny_eval(reason: str) -> Decision:
    return Decision("DENY", reason, "fail_closed", False, True)


def not_in_scope(reason: str) -> Decision:
    return Decision("NOT_IN_SCOPE", reason, "not_applicable", False, False)


def gate_call(enrolled: object, mode: object) -> Decision | None:
    """Enrollment and mode checks. None means the case policy applies."""
    if mode not in ("observe", "enforce"):
        return deny_eval("policy_malformed")
    if not isinstance(enrolled, bool):
        return deny_eval("enrollment_unknown")
    if enrolled is False:
        return not_in_scope("control_not_attached")
    return None
