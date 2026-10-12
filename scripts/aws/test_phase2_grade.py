#!/usr/bin/env python3
"""Host-free checks for the phase batteries. They do not launch an instance."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lab-guests"))

import phase2_grade as grade  # noqa: E402


class Phase2GradeTests(unittest.TestCase):
    def test_baseline_anchor_is_nonzero_before_the_first_open(self) -> None:
        self.assertFalse(grade.anchor_before_open_ok(0))
        self.assertFalse(grade.anchor_before_open_ok(False))
        self.assertFalse(grade.anchor_before_open_ok(None))
        self.assertTrue(grade.anchor_before_open_ok(6884))

    def test_workflow_offers_the_same_phase_names(self) -> None:
        text = Path(__file__).resolve().parents[2].joinpath(
            ".github/workflows/w3-lab-auto-arm.yml"
        ).read_text(encoding="utf-8")
        for name in grade.PHASES:
            self.assertIn(f"- {name}", text)
        self.assertIn("- enterprise", text)
        self.assertIn("- descendant-b1", text)

    def test_same_seal_is_not_an_upgrade(self) -> None:
        body = grade.grade_upgrade(
            seal_sha256=grade.WORKING_SEAL,
            image_before="sha256:abc",
            image_after="sha256:abc",
            deny_before=13,
            deny_after=13,
        )
        self.assertEqual(body["action"], "HOLD")
        self.assertEqual(body["reason"], "same_seal_is_not_an_upgrade")
        self.assertEqual(body["host_rollback"], "NOT_RUN")
        self.assertTrue(body["process_restart_held"])
        self.assertFalse(body["lab_pass"])
        self.assertFalse(body["upgrade_pass"])
        silent = grade.grade_upgrade(
            seal_sha256=grade.WORKING_SEAL,
            image_before="sha256:abc",
            image_after="sha256:abc",
            deny_before=13,
            deny_after=0,
            attributed_before=True,
            attributed_after=False,
        )
        self.assertFalse(silent["process_restart_held"])
        held = grade.grade_upgrade(
            seal_sha256=grade.WORKING_SEAL,
            image_before="sha256:abc",
            image_after="sha256:abc",
            deny_before=13,
            deny_after=13,
            attributed_before=True,
            attributed_after=True,
        )
        self.assertTrue(held["process_restart_held"])
        self.assertTrue(held["restart_attributed"])
        unnamed = grade.grade_upgrade(
            seal_sha256=grade.WORKING_SEAL,
            image_before="sha256:abc",
            image_after="sha256:abc",
            deny_before=13,
            deny_after=13,
            attributed_before=True,
            attributed_after=False,
        )
        self.assertFalse(unnamed["process_restart_held"])

    def test_dead_loader_that_still_allows_enrolled_traffic_fails(self) -> None:
        body = grade.grade_crash(enrolled_errno=0, unenrolled_errno=0)
        self.assertEqual(body["classification"], "silent_weakening")
        self.assertEqual(body["host_result"], "FAIL")
        self.assertFalse(body["lab_pass"])

    def test_dead_loader_fail_closed_is_recorded(self) -> None:
        body = grade.grade_crash(enrolled_errno=1, unenrolled_errno=0)
        self.assertEqual(body["classification"], "fail_closed")
        self.assertTrue(body["expectation_met"])
        self.assertFalse(body["lab_pass"])

    def test_killed_loader_file_open_needs_an_attributed_deny(self) -> None:
        silent = grade.grade_crash(
            enrolled_errno=1,
            unenrolled_errno=0,
            file_errno=0,
            file_attributed=False,
        )
        self.assertEqual(silent["classification"], "silent_weakening")
        self.assertEqual(silent["file_open"], "allowed")
        unnamed = grade.grade_crash(
            enrolled_errno=1,
            unenrolled_errno=0,
            file_errno=13,
            file_attributed=False,
        )
        self.assertEqual(unnamed["classification"], "unattributed_deny")
        held = grade.grade_crash(
            enrolled_errno=1,
            unenrolled_errno=0,
            file_errno=13,
            file_attributed=True,
        )
        self.assertEqual(held["classification"], "fail_closed")
        self.assertEqual(held["file_open"], "attributed_deny")
        refused = grade.grade_crash(enrolled_errno=111, unenrolled_errno=0, file_errno=13, file_attributed=True)
        self.assertEqual(refused["enrolled_egress"], "denied")
        self.assertEqual(refused["classification"], "fail_closed")
        self.assertEqual(grade.egress_word(110), "no_response")
        self.assertEqual(grade.egress_grade_block(110, 1), "lab_network")
        self.assertEqual(grade.egress_grade_block(None, 1), "lab_network")
        self.assertEqual(grade.egress_grade_block(111, 1), "lab_network")
        self.assertEqual(grade.egress_grade_block(0, 110), "enrolled_egress_timeout")
        self.assertIsNone(grade.egress_grade_block(0, 1))
        self.assertIsNone(grade.egress_grade_block(0, 13))
        self.assertIsNone(grade.egress_grade_block(0, 111))
        self.assertIsNone(grade.egress_grade_block(0, 0))
        timed = grade.grade_crash(
            enrolled_errno=110,
            unenrolled_errno=0,
            file_errno=13,
            file_attributed=True,
        )
        self.assertEqual(timed["reason"], "enrolled_egress_timeout")
        self.assertEqual(timed["host_result"], "NOT_GRADED")
        self.assertEqual(timed["classification"], "not_graded")
        self.assertTrue(timed["setup_invalid"])
        self.assertNotEqual(timed["host_result"], "HOLD")
        lab = grade.grade_crash(enrolled_errno=1, unenrolled_errno=110, file_errno=13, file_attributed=True)
        self.assertEqual(lab["reason"], "lab_network")
        self.assertEqual(lab["host_result"], "NOT_GRADED")
        refused = grade.grade_tamper(
            enrolled_errno=110,
            unenrolled_errno=0,
            loader_up=False,
            file_errno=13,
            file_attributed=True,
        )
        self.assertEqual(refused["host_result"], "NOT_GRADED")
        self.assertEqual(refused["reason"], "enrolled_egress_timeout")
        tamper = grade.grade_tamper(
            enrolled_errno=1,
            unenrolled_errno=0,
            loader_up=False,
            file_errno=0,
            file_attributed=False,
        )
        self.assertEqual(tamper["classification"], "silent_weakening")
        tamper_held = grade.grade_tamper(
            enrolled_errno=1,
            unenrolled_errno=0,
            loader_up=False,
            file_errno=13,
            file_attributed=True,
        )
        self.assertEqual(tamper_held["classification"], "fail_closed")
        self.assertEqual(tamper_held["file_open"], "attributed_deny")
        record = bytearray(grade.DENY_ATTR_SIZE)
        record[0:4] = (4242).to_bytes(4, "little")
        record[8:12] = (grade.DENY_KIND_FILE).to_bytes(4, "little")
        record[24:32] = (9).to_bytes(8, "little")
        self.assertFalse(grade.deny_record_names(bytes(record), 4242))
        record[16:24] = (7774).to_bytes(8, "little")
        self.assertEqual(grade.deny_record_anchor(bytes(record), 4242), 7774)
        self.assertTrue(grade.deny_record_names(bytes(record), 4242))
        self.assertFalse(grade.deny_record_names(bytes(record), 4243))
        record[24:32] = (0).to_bytes(8, "little")
        self.assertFalse(grade.deny_record_names(bytes(record), 4242))

    def test_performance_rejects_a_second_host_and_a_long_run(self) -> None:
        rejected = grade.grade_performance(runtime_seconds=1, host_count=2, sample_count=10)
        self.assertEqual(rejected["result"], "REJECTED")
        slow = grade.grade_performance(runtime_seconds=901, host_count=1, sample_count=10)
        self.assertEqual(slow["reason"], "runtime_bound")
        recorded = grade.grade_performance(runtime_seconds=1.2, host_count=1, sample_count=100)
        self.assertEqual(recorded["result"], "RECORDED")
        self.assertFalse(recorded["customer_claim"])
        self.assertNotIn("latency", recorded)

    def test_enrolled_connect_is_after_the_unenrolled_control(self) -> None:
        text = Path(__file__).resolve().parent.joinpath("lab-guests", "phase2_host.py").read_text(encoding="utf-8")
        self.assertNotIn("192.0.2", text)
        for name, nxt in (("run_2d", "run_2e"), ("run_2f", "kernel_facts")):
            body = text.split(f"def {name}", 1)[1].split(f"def {nxt}", 1)[0]
            self.assertLess(body.index("control_handshake()"), body.index("child_open(True)"))
            self.assertIn('"lab_network"', body)
        aws = Path(__file__).resolve().parent.joinpath("lab-guests", "enterprise-rows.sh").read_text(encoding="utf-8")
        gcp = Path(__file__).resolve().parents[1].joinpath("gcp", "lab-guests", "enterprise-rows.sh").read_text(encoding="utf-8")
        self.assertIn("VANTIO_EGRESS_HOST", aws)
        self.assertIn("VANTIO_EGRESS_PORT", aws)
        self.assertIn("VANTIO_EGRESS_HOST", gcp)
        self.assertIn("VANTIO_EGRESS_PORT", gcp)

    def test_battery_target_is_a_reachable_private_address(self) -> None:
        self.assertEqual(
            grade.choose_egress_target(None, None, ["192.0.2.2", "172.31.24.10"]),
            ("172.31.24.10", grade.DEFAULT_EGRESS_PORT),
        )
        self.assertEqual(grade.choose_egress_target("10.128.0.5", None, []), ("10.128.0.5", grade.DEFAULT_EGRESS_PORT))
        self.assertIsNone(grade.choose_egress_target("192.0.2.2", 9, ["172.31.24.10"]))
        self.assertIsNone(grade.choose_egress_target("198.51.100.8", None, ["10.1.1.1"]))
        self.assertIsNone(grade.choose_egress_target("203.0.113.8", None, []))
        self.assertIsNone(grade.choose_egress_target("127.0.0.1", None, ["10.1.1.1"]))
        self.assertIsNone(grade.choose_egress_target("169.254.169.254", None, ["10.1.1.1"]))
        self.assertIsNone(grade.choose_egress_target(None, None, ["127.0.0.1", "192.0.2.1"]))
        self.assertIsNone(grade.choose_egress_target("10.1.1.1", 0, []))
        self.assertIsNone(grade.choose_egress_target("8.8.8.8", None, []))

    def test_documentation_listener_stays_in_the_local_netns(self) -> None:
        """192.0.2.2 is only dialed from this local veth. The battery chooser refuses it."""
        if os.geteuid() != 0:
            self.skipTest("local netns")
        ns = "pelab-doc-test"
        host_if = "vdoc-host"
        peer_if = "vdoc-peer"
        listener = "192.0.2.2"
        subprocess.run(["ip", "netns", "del", ns], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ip", "link", "del", host_if], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc = None
        try:
            self.assertEqual(subprocess.run(["ip", "link", "add", host_if, "type", "veth", "peer", "name", peer_if]).returncode, 0)
            self.assertEqual(subprocess.run(["ip", "addr", "add", "192.0.2.1/30", "dev", host_if]).returncode, 0)
            self.assertEqual(subprocess.run(["ip", "link", "set", host_if, "up"]).returncode, 0)
            self.assertEqual(subprocess.run(["ip", "netns", "add", ns]).returncode, 0)
            self.assertEqual(subprocess.run(["ip", "link", "set", peer_if, "netns", ns]).returncode, 0)
            self.assertEqual(subprocess.run(["ip", "netns", "exec", ns, "ip", "link", "set", "lo", "up"]).returncode, 0)
            self.assertEqual(subprocess.run(["ip", "netns", "exec", ns, "ip", "addr", "add", "192.0.2.2/30", "dev", peer_if]).returncode, 0)
            self.assertEqual(subprocess.run(["ip", "netns", "exec", ns, "ip", "link", "set", peer_if, "up"]).returncode, 0)
            script = Path("/tmp/vantio-doc-listen.py")
            script.write_text(
                "import socket\n"
                "server = socket.socket()\n"
                "server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
                "server.bind(('192.0.2.2', 9))\n"
                "server.listen(8)\n"
                "client, _addr = server.accept()\n"
                "client.close()\n",
                encoding="utf-8",
            )
            proc = subprocess.Popen(
                ["ip", "netns", "exec", ns, "python3", str(script)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            errno = 110
            for _ in range(25):
                sock = socket.socket()
                sock.settimeout(0.5)
                try:
                    sock.connect((listener, 9))
                    errno = 0
                    break
                except TimeoutError:
                    errno = 110
                except OSError as exc:
                    errno = exc.errno or 1
                finally:
                    sock.close()
                time.sleep(0.05)
            self.assertEqual(errno, 0)
            self.assertIsNone(grade.choose_egress_target(listener, 9, ["10.1.1.1"]))
        finally:
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=2)
            subprocess.run(["ip", "netns", "del", ns], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["ip", "link", "del", host_if], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_tamper_does_not_treat_a_live_loader_as_fail_closed(self) -> None:
        body = grade.grade_tamper(enrolled_errno=1, unenrolled_errno=0, loader_up=True)
        self.assertEqual(body["classification"], "inconclusive")

    def test_distro_refuses_a_foreign_seal_and_a_descendant_bit(self) -> None:
        foreign = grade.grade_distro(
            {
                "live_probe": True,
                "distro": "Debian 12",
                "kernel": "6.1",
                "btf": True,
                "lsm": "lockdown,capability,landlock,yama,apparmor,bpf",
                "seal": "ab" * 32,
                "enrolled_errno": 13,
                "unenrolled_errno": 0,
                "removed": True,
            }
        )
        self.assertEqual(foreign["reason"], "seal")
        rejected = grade.grade_distro(
            {
                "live_probe": True,
                "distro": "Debian 12",
                "kernel": "6.1",
                "btf": True,
                "lsm": "apparmor",
                "seal": grade.WORKING_SEAL,
                "descendant_pass": True,
                "enrolled_errno": 13,
                "unenrolled_errno": 0,
                "removed": True,
            }
        )
        self.assertEqual(rejected["reason"], "descendant_or_docker_child")


if __name__ == "__main__":
    unittest.main()
