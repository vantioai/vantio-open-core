"""Reason tokens the skb program and the userspace model both use.

Shannon entropy is intentionally absent. Userspace `t5_egress.entropy` remains
the entropy decision.
"""

from __future__ import annotations

REASONS = (
    "policy_permits",
    "policy_malformed",
    "resolver_not_allowed",
    "dns_name_not_allowed",
    "dns_label_too_long",
    "dns_label_not_ldh",
    "dns_unparsable",
    "dns_parse_budget",
    "dns_qdcount",
    "dns_query_volume",
    "dns_transport_not_visible",
    "link_local_not_allowed",
    "icmp_destination_not_allowed",
    "icmp_type_not_allowed",
    "icmp_header_unreadable",
    "loopback_port_not_allowed",
    "loopback_header_unreadable",
    "get_method_not_visible",
    "case_not_applicable",
    "address_not_canonical",
)

PASS = "pass"
CLASSIFIED = "classified"
EVAL = "eval"
SCOPE = "scope"

MAX_NAME_SLOTS = 4
MAX_ADDR_SLOTS = 4
MAX_PORT_SLOTS = 8
MAX_PARSE_STEPS = 16
MAX_LABELS = 8
MAX_HOPS = 4
MAX_LABEL_OCTETS = 63
