"""Contract tests for the T5 kernel model. They do not load eBPF."""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT / "packages" / "t5-egress-drills"),
    str(ROOT / "packages" / "t5-egress-kernel"),
]

from t5_egress.entropy import shannon_bits  # noqa: E402
from t5_kernel.compile_bpf import compile_object  # noqa: E402
from t5_kernel.decide import FixedWindow, KernelMaps, kernel_connect, kernel_packet  # noqa: E402
from t5_kernel.loader import (  # noqa: E402
    LANE_SEAL,
    PUBLIC_PIN,
    AttachRequest,
    attach_decision,
    pack_cfg,
)
from t5_kernel.reasons import REASONS  # noqa: E402

SOURCE = ROOT / "packages" / "t5-egress-kernel" / "bpf" / "t5_egress.bpf.c"


def maps(**overrides: object) -> KernelMaps:
    base = dict(
        enforce=True,
        max_label=32,
        max_queries=30,
        entropy_min_length=12,
        entropy_userspace=1,
        window_ns=10_000_000_000,
        names=("allowed.example",),
        resolvers=("127.0.0.1",),
        icmp_destinations=("198.51.100.9",),
        ports=(18080,),
    )
    base.update(overrides)
    return KernelMaps(**base)  # type: ignore[arg-type]


def dns_packet(name: str, dest: str = "127.0.0.1") -> bytes:
    labels = name.split(".")
    qname = b"".join(bytes([len(label)]) + label.encode("ascii") for label in labels) + b"\x00"
    payload = struct.pack(">HHHHHH", 0, 0, 1, 0, 0, 0) + qname + struct.pack(">HH", 1, 1)
    return udp_packet(dest, 53, payload)


def udp_packet(dest: str, dport: int, payload: bytes, protocol: int = 17) -> bytes:
    header = bytearray(20)
    header[0] = 0x45
    total = 20 + (8 if protocol in (6, 17) else 0) + len(payload)
    header[2:4] = total.to_bytes(2, "big")
    header[8] = 64
    header[9] = protocol
    header[16:20] = bytes(int(part) for part in dest.split("."))
    if protocol == 1:
        return bytes(header) + payload
    transport = bytearray(8)
    transport[0:2] = (12345).to_bytes(2, "big")
    transport[2:4] = dport.to_bytes(2, "big")
    transport[4:6] = (8 + len(payload)).to_bytes(2, "big")
    return bytes(header) + bytes(transport) + payload


def ipv6_icmp() -> bytes:
    header = bytearray(40)
    header[0] = 0x60
    header[6] = 58
    return bytes(header) + b"\x80\x00"


class DecisionTests(unittest.TestCase):
    def test_listed_name_is_allowed_without_an_entropy_score(self) -> None:
        decision = kernel_packet(dns_packet("allowed.example"), maps(), "enforce", FixedWindow(), 1)
        self.assertEqual(decision.action, "ALLOW")
        self.assertFalse(decision.entropy_deferred)
        self.assertTrue(decision.transmit)

    def test_high_entropy_label_stays_allowed_in_the_kernel(self) -> None:
        label = "q7w8e9r0t1y2u3i4o5pq"
        blob = label.encode("ascii")
        self.assertGreater(shannon_bits(blob), 3.5)
        self.assertGreaterEqual(len(label), 12)
        decision = kernel_packet(dns_packet(f"{label}.allowed.example"), maps(), "enforce", FixedWindow(), 1)
        self.assertEqual(decision.reason, "policy_permits")
        self.assertTrue(decision.entropy_deferred)
        self.assertTrue(decision.transmit)

    def test_unlisted_name_transmits_only_in_observe(self) -> None:
        packet = dns_packet("other.example")
        observe = kernel_packet(packet, maps(), "observe", FixedWindow(), 1)
        enforce = kernel_packet(packet, maps(), "enforce", FixedWindow(), 2)
        self.assertEqual(observe.action, "OBSERVE_WOULD_DENY")
        self.assertTrue(observe.transmit)
        self.assertEqual(enforce.action, "DENY")
        self.assertFalse(enforce.transmit)

    def test_overlong_label_is_classified(self) -> None:
        decision = kernel_packet(dns_packet(("a" * 33) + ".allowed.example"), maps(), "enforce", FixedWindow(), 1)
        self.assertEqual(decision.reason, "dns_label_too_long")
        self.assertFalse(decision.transmit)

    def test_fixed_window_resets_on_its_boundary(self) -> None:
        window = FixedWindow()
        policy = maps(max_queries=2, window_ns=10)
        first = kernel_packet(dns_packet("allowed.example"), policy, "enforce", window, 100)
        second = kernel_packet(dns_packet("allowed.example"), policy, "enforce", window, 101)
        third = kernel_packet(dns_packet("allowed.example"), policy, "enforce", window, 102)
        later = kernel_packet(dns_packet("allowed.example"), policy, "enforce", window, 112)
        self.assertEqual(first.reason, "policy_permits")
        self.assertEqual(second.reason, "policy_permits")
        self.assertEqual(third.reason, "dns_query_volume")
        self.assertFalse(third.transmit)
        self.assertEqual(later.reason, "policy_permits")

    def test_clock_step_backwards_is_an_evaluation_failure(self) -> None:
        window = FixedWindow()
        policy = maps()
        kernel_packet(dns_packet("allowed.example"), policy, "observe", window, 50)
        decision = kernel_packet(dns_packet("allowed.example"), policy, "observe", window, 10)
        self.assertEqual(decision.reason, "dns_query_volume")
        self.assertTrue(decision.as_dict()["reason"])
        self.assertFalse(decision.transmit)

    def test_bad_qdcount_does_not_transmit_in_observe(self) -> None:
        payload = struct.pack(">HHHHHH", 0, 0, 2, 0, 0, 0) + b"\x00" + struct.pack(">HH", 1, 1)
        decision = kernel_packet(udp_packet("127.0.0.1", 53, payload), maps(), "observe", FixedWindow(), 1)
        self.assertEqual(decision.reason, "dns_qdcount")
        self.assertFalse(decision.transmit)

    def test_icmp_allow_and_denies(self) -> None:
        echo = udp_packet("198.51.100.9", 0, b"\x08\x00\x00\x00", protocol=1)
        other = udp_packet("198.51.100.8", 0, b"\x08\x00\x00\x00", protocol=1)
        kind = udp_packet("198.51.100.9", 0, b"\x03\x00\x00\x00", protocol=1)
        link = udp_packet("169.254.169.254", 0, b"\x08\x00\x00\x00", protocol=1)
        self.assertEqual(kernel_packet(echo, maps(), "enforce", FixedWindow(), 1).reason, "policy_permits")
        self.assertEqual(kernel_packet(other, maps(), "enforce", FixedWindow(), 1).reason, "icmp_destination_not_allowed")
        self.assertEqual(kernel_packet(kind, maps(), "enforce", FixedWindow(), 1).reason, "icmp_type_not_allowed")
        self.assertEqual(kernel_packet(link, maps(), "enforce", FixedWindow(), 1).reason, "link_local_not_allowed")
        v6 = kernel_packet(ipv6_icmp(), maps(), "observe", FixedWindow(), 1)
        self.assertEqual(v6.reason, "icmp_type_not_allowed")
        self.assertTrue(v6.transmit)

    def test_hidden_tcp_is_an_evaluation_failure(self) -> None:
        http = udp_packet("198.51.100.9", 80, b"GET / HTTP/1.0\r\n", protocol=6)
        dns_tcp = udp_packet("127.0.0.1", 53, b"\x00\x01", protocol=6)
        http_decision = kernel_packet(http, maps(), "observe", FixedWindow(), 1)
        dns_decision = kernel_packet(dns_tcp, maps(), "observe", FixedWindow(), 1)
        self.assertEqual(http_decision.reason, "get_method_not_visible")
        self.assertFalse(http_decision.transmit)
        self.assertEqual(dns_decision.reason, "dns_transport_not_visible")
        self.assertFalse(dns_decision.transmit)

    def test_loopback_port_and_resolver_connect(self) -> None:
        policy = maps()
        self.assertEqual(kernel_connect("127.0.0.1", 18080, "tcp", policy, "enforce").reason, "policy_permits")
        denied = kernel_connect("127.0.0.1", 22, "tcp", policy, "enforce")
        self.assertEqual(denied.reason, "loopback_port_not_allowed")
        self.assertFalse(denied.transmit)
        self.assertEqual(kernel_connect("127.0.0.1", 53, "udp", policy, "enforce").reason, "policy_permits")
        self.assertEqual(kernel_connect("198.51.100.9", 443, "tcp", policy, "observe").reason, "case_not_applicable")
        self.assertFalse(kernel_connect("198.51.100.9", 443, "tcp", policy, "observe").transmit)
        link = kernel_connect("169.254.169.254", 80, "tcp", policy, "observe")
        self.assertEqual(link.reason, "link_local_not_allowed")
        self.assertTrue(link.transmit)
        self.assertFalse(kernel_connect("169.254.169.254", 80, "tcp", policy, "enforce").transmit)
        mapped = kernel_connect("::ffff:127.0.0.1", 2375, "tcp", policy, "enforce")
        self.assertEqual(mapped.reason, "loopback_port_not_allowed")

    def test_entropy_flag_off_is_malformed(self) -> None:
        decision = kernel_packet(dns_packet("allowed.example"), maps(entropy_userspace=0), "enforce", FixedWindow(), 1)
        self.assertEqual(decision.reason, "policy_malformed")
        self.assertFalse(decision.transmit)


class ProgramSourceTests(unittest.TestCase):
    def test_reason_tokens_and_entropy_stay_out_of_the_object_source(self) -> None:
        text = SOURCE.read_text(encoding="utf-8")
        for reason in REASONS:
            self.assertIn(f"reason:{reason}", text)
        self.assertNotIn("shannon", text.lower())
        self.assertNotIn("log2", text)
        self.assertIn("cgroup_skb/egress", text)
        self.assertIn("cgroup/connect4", text)
        self.assertIn("cgroup/connect6", text)
        self.assertIn("GPL-2.0-only", text)
        self.assertNotIn("navera", text.lower())

    def test_clang_compiles_without_loading(self) -> None:
        destination = ROOT / "packages" / "t5-egress-kernel" / "bpf" / "t5_egress.bpf.o"
        result = compile_object(destination)
        if result["status"] == "skipped":
            self.skipTest(str(result["reason"]))
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["attached"])
        self.assertEqual(result["label"], "Lab-only")
        destination.unlink(missing_ok=True)


class LoaderGateTests(unittest.TestCase):
    def _request(self, **overrides: object) -> AttachRequest:
        base = dict(
            host_class="vantio-owned",
            project="vantio-lab-oct08",
            cgroup="/sys/fs/cgroup/vantio-t5-lab.slice/t5-drill",
            hostname="lab",
            seal=LANE_SEAL,
            public_pin=PUBLIC_PIN,
            execute=False,
            maps=maps(),
        )
        base.update(overrides)
        return AttachRequest(**base)  # type: ignore[arg-type]

    def test_gates_do_not_call_bpf(self) -> None:
        calls: list[str] = []

        def boom(_request: AttachRequest) -> dict[str, object]:
            calls.append("called")
            return {"loaded": True}

        for request in (
            self._request(project="vantio-lab-navera"),
            self._request(hostname="navera-vm"),
            self._request(cgroup="/sys/fs/cgroup/vantio-enrolled.slice"),
            self._request(cgroup="/sys/fs/cgroup/vantio-t5-lab.slice"),
            self._request(host_class="customer"),
            self._request(project="other"),
            self._request(seal=PUBLIC_PIN),
            self._request(maps=maps(entropy_userspace=0)),
        ):
            decision = attach_decision(request, boom)
            self.assertFalse(decision["attached"])
            self.assertEqual(decision["bpf_calls"], 0)
        self.assertEqual(calls, [])

    def test_open_gate_still_does_not_issue_a_syscall_by_default(self) -> None:
        decision = attach_decision(self._request(execute=True))
        self.assertFalse(decision["attached"])
        self.assertEqual(decision["reason"], "syscall_not_issued")
        self.assertEqual(decision["label"], "Roadmap")

    def test_injected_call_runs_only_after_the_gate(self) -> None:
        def fake(_request: AttachRequest) -> dict[str, object]:
            return {"loaded": True}

        decision = attach_decision(self._request(execute=True), fake)
        self.assertEqual(decision["bpf_calls"], 1)
        self.assertTrue(decision["attached"])
        self.assertEqual(decision["label"], "Lab-only")
        self.assertEqual(decision["verifier"], "caller_reported")

    def test_cfg_image_matches_the_c_struct(self) -> None:
        image = pack_cfg(maps())
        self.assertEqual(len(image), 48)
        self.assertNotEqual(LANE_SEAL, PUBLIC_PIN)


if __name__ == "__main__":
    unittest.main()
