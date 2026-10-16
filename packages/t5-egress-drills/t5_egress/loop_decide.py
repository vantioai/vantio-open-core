"""Loopback-class port default-deny."""

from __future__ import annotations

from t5_egress.address import address_class, parse_address
from t5_egress.decision import Decision, allow, deny_classified, deny_eval, gate_call, not_in_scope
from t5_egress.policy import Policy


def decide_loopback(
    destination: object,
    port: object,
    protocol: object,
    policy: Policy,
    mode: object,
    enrolled: object,
) -> Decision:
    early = gate_call(enrolled, mode)
    if early is not None:
        return early
    assert isinstance(mode, str)
    if policy.malformed:
        return deny_eval("policy_malformed")
    if protocol not in ("tcp", "udp"):
        return deny_eval("loopback_header_unreadable")
    parsed = parse_address(destination)
    if parsed is None:
        return deny_eval("address_not_canonical")
    kind = address_class(parsed)
    if kind == "link_local":
        return deny_classified("link_local_not_allowed", mode)
    if kind != "loopback":
        return not_in_scope("case_not_applicable")
    if isinstance(port, bool) or not isinstance(port, int) or port < 0 or port > 65535:
        return deny_eval("loopback_header_unreadable")
    if port not in policy.loopback.allowed_ports:
        return deny_classified("loopback_port_not_allowed", mode)
    return allow()
