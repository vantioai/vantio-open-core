"""DNS allow-list, tunnel signals, volume, and delegation."""

from __future__ import annotations

from t5_egress.address import address_class, listed_address, parse_address
from t5_egress.decision import Decision, allow, deny_classified, deny_eval, gate_call
from t5_egress.dns_wire import WireFail, _LABEL_OK, parse_question, parse_response
from t5_egress.entropy import shannon_bits
from t5_egress.names import longest_match
from t5_egress.policy import Policy
from t5_egress.volume import VolumeGate


def _fold_label(label: str) -> str:
    return "".join(ch.lower() if "A" <= ch <= "Z" else ch for ch in label)


def _labels_text(labels: tuple[bytes, ...]) -> Decision | tuple[str, ...]:
    text: list[str] = []
    for label in labels:
        if not label or len(label) > 63 or any(byte not in _LABEL_OK for byte in label):
            return deny_eval("dns_label_not_ldh")
        try:
            decoded = label.decode("ascii")
        except UnicodeError:
            return deny_eval("dns_label_not_ldh")
        text.append(_fold_label(decoded))
    return tuple(text)


def _tunnel_reason(labels: tuple[str, ...], matched: tuple[str, ...], policy: Policy) -> str | None:
    if len(labels) == len(matched):
        return None
    left = labels[: len(labels) - len(matched)]
    total = 0
    for label in left:
        if len(label) > policy.dns.max_label_length:
            return "dns_label_too_long"
        total += len(label)
    if total > policy.dns.max_label_length:
        return "dns_label_too_long"
    blob = "".join(left).encode("ascii")
    if len(blob) >= policy.dns.entropy_min_length and shannon_bits(blob) > policy.dns.entropy_bits_max:
        return "dns_label_entropy"
    return None


def decide_dns_query(
    packet: bytes,
    resolver: object,
    policy: Policy,
    mode: object,
    enrolled: object,
    gate: VolumeGate | None,
    workload_id: object = "workload",
    now_ns: int | None = None,
) -> Decision:
    early = gate_call(enrolled, mode)
    if early is not None:
        return early
    assert isinstance(mode, str)
    if policy.malformed:
        return deny_eval("policy_malformed")
    try:
        question = parse_question(packet)
    except WireFail as exc:
        return deny_eval(exc.reason)
    if gate is None:
        return deny_eval("dns_query_volume")
    status = gate.hit(workload_id, now_ns)
    if status == "failure":
        return deny_eval("dns_query_volume")
    labels = _labels_text(question.labels)
    if isinstance(labels, Decision):
        return labels
    resolver_addr = parse_address(resolver)
    if resolver_addr is None:
        return deny_eval("address_not_canonical")
    if address_class(resolver_addr) == "link_local":
        return deny_classified("link_local_not_allowed", mode)
    if not listed_address(resolver_addr, policy.dns.allowed_resolvers):
        return deny_classified("resolver_not_allowed", mode)
    for label in labels:
        if len(label) > policy.dns.max_label_length:
            return deny_classified("dns_label_too_long", mode)
    matched = longest_match(labels, policy.dns.allowed_names)
    if matched is None:
        return deny_classified("dns_name_not_allowed", mode)
    tunnel = _tunnel_reason(labels, matched, policy)
    if tunnel is not None:
        return deny_classified(tunnel, mode)
    if status == "over":
        return deny_classified("dns_query_volume", mode)
    return allow()


def decide_dns_response(packet: bytes, policy: Policy, mode: object, enrolled: object) -> Decision:
    early = gate_call(enrolled, mode)
    if early is not None:
        return early
    assert isinstance(mode, str)
    if policy.malformed:
        return deny_eval("policy_malformed")
    try:
        view = parse_response(packet)
    except WireFail as exc:
        return deny_eval(exc.reason)
    ns_records = [record for record in view.authority if record.rtype == 2 and record.rdata_name]
    if not ns_records:
        return deny_classified("delegation_unresolved", mode)
    for record in ns_records:
        target = _labels_text(record.rdata_name or ())
        if isinstance(target, Decision):
            return target
        if longest_match(target, policy.dns.allowed_names) is None:
            return deny_classified("delegation_unknown", mode)
        glue = []
        for item in view.additional:
            if item.rtype not in (1, 28) or not item.rdata_addr:
                continue
            owner = _labels_text(item.owner)
            if isinstance(owner, tuple) and owner == target:
                glue.append(item.rdata_addr)
        if not glue:
            return deny_classified("delegation_unresolved", mode)
        for addr_text in glue:
            parsed = parse_address(addr_text)
            if parsed is None:
                return deny_eval("address_not_canonical")
            if address_class(parsed) == "link_local":
                return deny_classified("link_local_not_allowed", mode)
            if not listed_address(parsed, policy.dns.allowed_resolvers):
                return deny_classified("delegation_unknown", mode)
    return allow()
