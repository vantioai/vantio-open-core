"""Decision behavior for DNS, ICMP, GET, and loopback."""

from __future__ import annotations

import unittest

import support

from t5_egress.entropy import shannon_bits
from t5_egress.fixtures import dns_ns_response, dns_query, icmp_message, ipv4_icmp, ipv6_icmp
from t5_egress.policy import load_policy
from t5_egress.skb_signal import skb_label_signal
from t5_egress.volume import VolumeGate
from t5_egress.decide import decide_dns_query, decide_dns_response, decide_get, decide_icmp, decide_loopback


def policy():
    return load_policy(support.POLICY)


class DnsTests(unittest.TestCase):
    def test_allow_and_unlisted(self) -> None:
        loaded = policy()
        gate = VolumeGate(30, 10, "workload")
        allowed = decide_dns_query(dns_query("api.allowed.example"), "127.0.0.1", loaded, "enforce", True, gate)
        self.assertEqual(allowed.action, "ALLOW")
        blocked = decide_dns_query(dns_query("api.other.example"), "127.0.0.1", loaded, "enforce", True, gate)
        self.assertEqual(blocked.reason, "dns_name_not_allowed")
        self.assertFalse(blocked.transmit)

    def test_suffix_does_not_match_a_lookalike(self) -> None:
        loaded = policy()
        gate = VolumeGate(30, 10, "workload")
        decision = decide_dns_query(dns_query("notallowed.example"), "127.0.0.1", loaded, "enforce", True, gate)
        self.assertEqual(decision.reason, "dns_name_not_allowed")

    def test_long_label_and_split_sum(self) -> None:
        loaded = policy()
        gate = VolumeGate(30, 10, "workload")
        long_name = ("a" * 33) + ".allowed.example"
        decision = decide_dns_query(dns_query(long_name), "127.0.0.1", loaded, "observe", True, gate)
        self.assertEqual(decision.reason, "dns_label_too_long")
        self.assertTrue(decision.transmit)
        split = ("b" * 11) + "." + ("c" * 11) + "." + ("d" * 11) + ".allowed.example"
        split_decision = decide_dns_query(dns_query(split), "127.0.0.1", loaded, "enforce", True, gate)
        self.assertEqual(split_decision.reason, "dns_label_too_long")
        self.assertFalse(split_decision.transmit)

    def test_entropy_high_and_low(self) -> None:
        loaded = policy()
        gate = VolumeGate(30, 10, "workload")
        high = "qmzjxkwpvnrtyshl.allowed.example"
        high_decision = decide_dns_query(dns_query(high), "127.0.0.1", loaded, "enforce", True, gate)
        self.assertEqual(high_decision.reason, "dns_label_entropy")
        low = ("a" * 16) + ".allowed.example"
        low_decision = decide_dns_query(dns_query(low), "127.0.0.1", loaded, "enforce", True, gate)
        self.assertEqual(low_decision.action, "ALLOW")

    def test_volume_window_and_second_workload(self) -> None:
        loaded = load_policy({**support.POLICY, "dns": {**support.POLICY["dns"], "max_queries": 2}})
        gate = VolumeGate(2, 10, "workload")
        start = 10_000_000_000_000
        first = decide_dns_query(dns_query("api.allowed.example"), "127.0.0.1", loaded, "enforce", True, gate, now_ns=start)
        second = decide_dns_query(dns_query("api.allowed.example"), "127.0.0.1", loaded, "enforce", True, gate, now_ns=start + 1)
        third = decide_dns_query(dns_query("api.allowed.example"), "127.0.0.1", loaded, "observe", True, gate, now_ns=start + 2)
        self.assertEqual(first.action, "ALLOW")
        self.assertEqual(second.action, "ALLOW")
        self.assertEqual(third.reason, "dns_query_volume")
        self.assertFalse(third.evaluation_failure)
        self.assertTrue(third.transmit)
        self.assertLessEqual(gate.stored(), 2)
        later = decide_dns_query(
            dns_query("api.allowed.example"),
            "127.0.0.1",
            loaded,
            "enforce",
            True,
            gate,
            now_ns=start + 2 + 10_000_000_000 + 1,
        )
        self.assertEqual(later.action, "ALLOW")
        other = decide_dns_query(dns_query("api.allowed.example"), "127.0.0.1", loaded, "observe", True, gate, workload_id="other")
        self.assertTrue(other.evaluation_failure)
        self.assertFalse(other.transmit)

    def test_unknown_delegation_and_listed_glue(self) -> None:
        loaded = policy()
        unknown = dns_ns_response("allowed.example", "ns.allowed.example", "198.51.100.8")
        decision = decide_dns_response(unknown, loaded, "enforce", True)
        self.assertEqual(decision.reason, "delegation_unknown")
        listed = dns_ns_response("allowed.example", "ns.allowed.example", "127.0.0.1")
        allowed = decide_dns_response(listed, loaded, "enforce", True)
        self.assertEqual(allowed.action, "ALLOW")
        glue_less = dns_ns_response("allowed.example", "ns.allowed.example", None)
        missing = decide_dns_response(glue_less, loaded, "observe", True)
        self.assertEqual(missing.reason, "delegation_unresolved")
        self.assertTrue(missing.transmit)

    def test_pointer_budget_and_bad_resolver(self) -> None:
        loaded = policy()
        gate = VolumeGate(30, 10, "workload")
        packet = b"\x00\x01\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\xc0\x0c\x00\x01\x00\x01"
        decision = decide_dns_query(packet, "127.0.0.1", loaded, "observe", True, gate)
        self.assertEqual(decision.reason, "dns_unparsable")
        self.assertTrue(decision.evaluation_failure)
        self.assertFalse(decision.transmit)
        odd = decide_dns_query(dns_query("api.allowed.example"), "127.1", loaded, "enforce", True, gate)
        self.assertEqual(odd.reason, "address_not_canonical")
        self.assertTrue(odd.evaluation_failure)

    def test_empty_allow_list_denies(self) -> None:
        data = {**support.POLICY, "dns": {**support.POLICY["dns"], "allowed_names": []}}
        loaded = load_policy(data)
        self.assertFalse(loaded.malformed)
        gate = VolumeGate(30, 10, "workload")
        decision = decide_dns_query(dns_query("api.allowed.example"), "127.0.0.1", loaded, "enforce", True, gate)
        self.assertEqual(decision.reason, "dns_name_not_allowed")


class IcmpTests(unittest.TestCase):
    def test_echo_allow_and_other_dest(self) -> None:
        loaded = policy()
        echo = ipv4_icmp("198.51.100.1", "198.51.100.9", icmp_message(8))
        allowed = decide_icmp(echo, loaded, "enforce", True)
        self.assertEqual(allowed.action, "ALLOW")
        other = ipv4_icmp("198.51.100.1", "198.51.100.10", icmp_message(8))
        denied = decide_icmp(other, loaded, "observe", True)
        self.assertEqual(denied.reason, "icmp_destination_not_allowed")
        self.assertTrue(denied.transmit)
        kind = ipv4_icmp("198.51.100.1", "198.51.100.9", icmp_message(13))
        typed = decide_icmp(kind, loaded, "enforce", True)
        self.assertEqual(typed.reason, "icmp_type_not_allowed")

    def test_truncated_and_icmpv6(self) -> None:
        loaded = policy()
        short = decide_icmp(b"\x45\x00", loaded, "enforce", True)
        self.assertEqual(short.reason, "icmp_header_unreadable")
        self.assertTrue(short.evaluation_failure)
        v6 = decide_icmp(ipv6_icmp((0, 0, 0, 0, 0, 0, 0, 1), 128), loaded, "observe", True)
        self.assertEqual(v6.reason, "icmp_type_not_allowed")
        link = ipv4_icmp("198.51.100.1", "169.254.169.254", icmp_message(8))
        local = decide_icmp(link, loaded, "enforce", True)
        self.assertEqual(local.reason, "link_local_not_allowed")


class GetTests(unittest.TestCase):
    def _call(self, **kwargs):
        fields = {
            "method_visible": True,
            "method": "GET",
            "host": "allowed.example",
            "path": "/v1/models",
            "query": "limit=10",
            "body_length": 0,
            "header_bytes": 40,
            "policy": policy(),
            "mode": "enforce",
            "enrolled": True,
            "connected_address": "198.51.100.10",
        }
        fields.update(kwargs)
        return decide_get(**fields)

    def test_benign_and_writes(self) -> None:
        self.assertEqual(self._call().action, "ALLOW")
        self.assertEqual(self._call(body_length=4).reason, "get_body_write")
        self.assertEqual(self._call(query="data=1").reason, "get_query_write_key")
        self.assertEqual(self._call(path="/Upload/x", query="").reason, "get_path_write")
        self.assertEqual(self._call(query="n=" + ("a" * 200)).reason, "get_query_too_long")
        hidden = self._call(path="/v1/%2e%2e/secret", query="")
        self.assertEqual(hidden.reason, "get_path_not_normalized")
        self.assertTrue(hidden.evaluation_failure)
        self.assertFalse(hidden.transmit)

    def test_loopback_host_and_metadata_rebinding(self) -> None:
        loop = self._call(host="127.0.0.1", connected_address=None)
        self.assertEqual(loop.reason, "case_not_applicable")
        odd = self._call(host="127.1", connected_address=None)
        self.assertEqual(odd.reason, "address_not_canonical")
        self.assertTrue(odd.evaluation_failure)
        rebound = self._call(connected_address="169.254.169.254")
        self.assertEqual(rebound.reason, "link_local_not_allowed")
        missing = self._call(method_visible=False)
        self.assertEqual(missing.reason, "get_method_not_visible")
        self.assertFalse(missing.transmit)


class LoopbackTests(unittest.TestCase):
    def test_aliases_and_allow_port(self) -> None:
        loaded = policy()
        allowed = decide_loopback("127.0.0.1", 18080, "tcp", loaded, "enforce", True)
        self.assertEqual(allowed.action, "ALLOW")
        for dest in ("127.0.0.1", "0.0.0.0", "::ffff:127.0.0.1", "::1"):
            decision = decide_loopback(dest, 22, "tcp", loaded, "enforce", True)
            self.assertEqual(decision.reason, "loopback_port_not_allowed", dest)
            self.assertFalse(decision.transmit)
        udp = decide_loopback("127.0.0.1", 22, "udp", loaded, "observe", True)
        self.assertEqual(udp.action, "OBSERVE_WOULD_DENY")
        external = decide_loopback("198.51.100.9", 22, "tcp", loaded, "enforce", True)
        self.assertEqual(external.reason, "case_not_applicable")
        decimal = decide_loopback("2130706433", 22, "tcp", loaded, "enforce", True)
        self.assertEqual(decimal.reason, "address_not_canonical")
        self.assertTrue(decimal.evaluation_failure)


class PolicyTests(unittest.TestCase):
    def test_model_grant_and_cidr_are_malformed(self) -> None:
        granted = dict(support.POLICY)
        granted["model_grant"] = True
        self.assertTrue(load_policy(granted).malformed)
        cidr = {**support.POLICY, "icmp": {"allowed_destinations": ["198.51.100.0/24"], "allowed_types": [8]}}
        self.assertTrue(load_policy(cidr).malformed)
        empty = {**support.POLICY, "loopback": {**support.POLICY["loopback"], "allowed_ports": [""]}}
        self.assertTrue(load_policy(empty).malformed)


class SkbTests(unittest.TestCase):
    def test_digit_ratio_disagrees_with_shannon_inputs(self) -> None:
        digits = "12345678901234567890"
        letters = "qmzjxkwpvnrtyshlbdca"
        self.assertTrue(skb_label_signal(digits))
        self.assertLess(shannon_bits(digits.encode("ascii")), 3.5)
        self.assertFalse(skb_label_signal(letters))
        self.assertGreater(shannon_bits(letters.encode("ascii")), 3.5)


if __name__ == "__main__":
    unittest.main()
