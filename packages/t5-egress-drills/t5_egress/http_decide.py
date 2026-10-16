"""GET write signals for external hosts. Loopback is a different case."""

from __future__ import annotations

from t5_egress.address import address_class, listed_address, parse_address
from t5_egress.decision import Decision, allow, deny_classified, deny_eval, gate_call, not_in_scope
from t5_egress.names import NameRejected, longest_match, prepare_candidate_name
from t5_egress.policy import Policy

_BAD = ("%", "..", "//", "\\", ";")


def _fold(text: str) -> str:
    return "".join(ch.lower() if "A" <= ch <= "Z" else ch for ch in text)


def _int_field(value: object, reason: str) -> Decision | int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return deny_eval(reason)
    return value


def _address_shaped(host: str) -> bool:
    body = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    if body.lower().startswith("0x") or body.isdigit():
        return True
    if ":" in body:
        return True
    parts = body.split(".")
    return len(parts) > 1 and all(part.isdigit() for part in parts)


def _host_class(host: str) -> str | None:
    if not _address_shaped(host):
        return None
    parsed = parse_address(host)
    if parsed is None:
        return "bad"
    return address_class(parsed)


def _class_decision(kind: str, mode: str) -> Decision:
    if kind == "loopback":
        return not_in_scope("case_not_applicable")
    if kind == "link_local":
        return deny_classified("link_local_not_allowed", mode)
    if kind == "bad":
        return deny_eval("address_not_canonical")
    return deny_eval("address_not_canonical")


def decide_get(
    method_visible: object,
    method: object,
    host: object,
    path: object,
    query: object,
    body_length: object,
    header_bytes: object,
    policy: Policy,
    mode: object,
    enrolled: object,
    connected_address: object = None,
) -> Decision:
    early = gate_call(enrolled, mode)
    if early is not None:
        return early
    assert isinstance(mode, str)
    if policy.malformed:
        return deny_eval("policy_malformed")
    if method_visible is not True:
        return deny_eval("get_method_not_visible")
    if not isinstance(method, str) or _fold(method) != "get":
        return not_in_scope("case_not_applicable")
    if not isinstance(host, str) or host == "":
        return deny_eval("get_host_not_allowed")
    host_kind = _host_class(host)
    if host_kind is not None:
        if host_kind != "external":
            return _class_decision(host_kind, mode)
        parsed_host = parse_address(host)
        if parsed_host is None or not listed_address(parsed_host, policy.http_get.allowed_host_addrs):
            return deny_classified("get_host_not_allowed", mode)
    else:
        candidate = prepare_candidate_name(host)
        if isinstance(candidate, NameRejected):
            return deny_eval(candidate.reason if candidate.reason != "policy_malformed" else "dns_label_not_ldh")
        if longest_match(candidate, policy.http_get.allowed_hosts) is None:
            return deny_classified("get_host_not_allowed", mode)
    if connected_address is not None:
        connected = parse_address(connected_address)
        if connected is None:
            return deny_eval("address_not_canonical")
        kind = address_class(connected)
        if kind == "loopback":
            return not_in_scope("case_not_applicable")
        if kind == "link_local":
            return deny_classified("link_local_not_allowed", mode)
    length = _int_field(body_length, "get_body_length_unknown")
    if isinstance(length, Decision):
        return length
    headers = _int_field(header_bytes, "get_header_length_unknown")
    if isinstance(headers, Decision):
        return headers
    if headers > policy.http_get.max_header_bytes:
        return deny_classified("get_headers_too_long", mode)
    if not isinstance(path, str) or not isinstance(query, str):
        return deny_eval("get_path_not_normalized")
    raw = path + "?" + query
    if any(ord(ch) > 127 for ch in raw) or any(token in raw for token in _BAD):
        return deny_eval("get_path_not_normalized")
    if len(path.encode("utf-8")) > policy.http_get.max_path_length:
        return deny_eval("get_path_too_long")
    if len(query.encode("utf-8")) > policy.http_get.max_query_length:
        return deny_classified("get_query_too_long", mode)
    if length > 0:
        return deny_classified("get_body_write", mode)
    folded_path = _fold(path)
    for prefix in policy.http_get.write_path_prefixes:
        if folded_path.startswith(prefix):
            return deny_classified("get_path_write", mode)
    if query:
        for piece in query.split("&"):
            key = _fold(piece.split("=", 1)[0])
            if key in policy.http_get.write_query_keys:
                return deny_classified("get_query_write_key", mode)
    return allow()

