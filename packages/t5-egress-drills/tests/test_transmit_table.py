"""Section 6 transmit table, both modes."""

from __future__ import annotations

import unittest

import support

from t5_egress.fixtures import dns_query, icmp_message, ipv4_icmp
from t5_egress.policy import load_policy
from t5_egress.volume import VolumeGate
from t5_egress.decide import decide_dns_query, decide_get, decide_icmp, decide_loopback


class TransmitTableTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load_policy(support.POLICY)

    def _pair(self, call, reason: str, evaluation_failure: bool) -> None:
        observe = call("observe")
        enforce = call("enforce")
        self.assertEqual(observe.reason, reason)
        self.assertEqual(enforce.reason, reason)
        self.assertEqual(observe.evaluation_failure, evaluation_failure)
        self.assertEqual(enforce.evaluation_failure, evaluation_failure)
        self.assertEqual(observe.enforce_outcome, "fail_closed")
        self.assertEqual(enforce.enforce_outcome, "fail_closed")
        if evaluation_failure:
            self.assertEqual(observe.action, "DENY")
            self.assertFalse(observe.transmit)
        else:
            self.assertEqual(observe.action, "OBSERVE_WOULD_DENY")
            self.assertTrue(observe.transmit)
        self.assertEqual(enforce.action, "DENY")
        self.assertFalse(enforce.transmit)

    def test_classified_and_evaluation_rows(self) -> None:
        gate = VolumeGate(30, 10, "workload")
        rows = [
            (
                "dns_name_not_allowed",
                False,
                lambda mode: decide_dns_query(dns_query("api.other.example"), "127.0.0.1", self.policy, mode, True, gate),
            ),
            (
                "address_not_canonical",
                True,
                lambda mode: decide_dns_query(dns_query("api.allowed.example"), "127.1", self.policy, mode, True, gate),
            ),
            (
                "get_method_not_visible",
                True,
                lambda mode: decide_get(False, None, "allowed.example", "/v1/models", "", 0, 10, self.policy, mode, True),
            ),
            (
                "get_body_write",
                False,
                lambda mode: decide_get(True, "GET", "allowed.example", "/v1/models", "limit=10", 3, 20, self.policy, mode, True),
            ),
            (
                "icmp_header_unreadable",
                True,
                lambda mode: decide_icmp(b"\x45", self.policy, mode, True),
            ),
            (
                "icmp_destination_not_allowed",
                False,
                lambda mode: decide_icmp(ipv4_icmp("198.51.100.1", "198.51.100.10", icmp_message(8)), self.policy, mode, True),
            ),
            (
                "loopback_port_not_allowed",
                False,
                lambda mode: decide_loopback("0.0.0.0", 2375, "tcp", self.policy, mode, True),
            ),
            (
                "enrollment_unknown",
                True,
                lambda mode: decide_loopback("127.0.0.1", 18080, "tcp", self.policy, mode, None),
            ),
        ]
        for reason, evaluation_failure, call in rows:
            with self.subTest(reason=reason):
                self._pair(call, reason, evaluation_failure)

    def test_scope_tokens_do_not_transmit(self) -> None:
        unenrolled = decide_get(True, "GET", "allowed.example", "/", "", 0, 10, self.policy, "observe", False)
        self.assertEqual(unenrolled.reason, "control_not_attached")
        self.assertEqual(unenrolled.action, "NOT_IN_SCOPE")
        self.assertFalse(unenrolled.transmit)
        routed = decide_get(True, "GET", "127.0.0.1", "/", "", 0, 10, self.policy, "enforce", True)
        self.assertEqual(routed.reason, "case_not_applicable")
        self.assertFalse(routed.transmit)

    def test_volume_over_cap_is_not_an_evaluation_failure(self) -> None:
        loaded = load_policy({**support.POLICY, "dns": {**support.POLICY["dns"], "max_queries": 1}})
        gate = VolumeGate(1, 10, "workload")
        start = 50_000_000_000_000
        first = decide_dns_query(dns_query("api.allowed.example"), "127.0.0.1", loaded, "enforce", True, gate, now_ns=start)
        second = decide_dns_query(dns_query("api.allowed.example"), "127.0.0.1", loaded, "observe", True, gate, now_ns=start + 1)
        self.assertEqual(first.action, "ALLOW")
        self.assertEqual(second.reason, "dns_query_volume")
        self.assertFalse(second.evaluation_failure)
        self.assertTrue(second.transmit)
        failed = decide_dns_query(dns_query("api.allowed.example"), "127.0.0.1", loaded, "observe", True, gate, workload_id="other")
        self.assertEqual(failed.reason, "dns_query_volume")
        self.assertTrue(failed.evaluation_failure)
        self.assertFalse(failed.transmit)


if __name__ == "__main__":
    unittest.main()
