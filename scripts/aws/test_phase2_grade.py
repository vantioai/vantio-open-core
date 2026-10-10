#!/usr/bin/env python3
"""Host-free checks for the phase batteries. They do not launch an instance."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lab-guests"))

import phase2_grade as grade  # noqa: E402


class Phase2GradeTests(unittest.TestCase):
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
        record[16:24] = (9).to_bytes(8, "little")
        record[32:36] = (grade.DENY_KIND_FILE).to_bytes(4, "little")
        self.assertTrue(grade.deny_record_names(bytes(record), 4242))
        self.assertFalse(grade.deny_record_names(bytes(record), 4243))
        record[16:24] = (0).to_bytes(8, "little")
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
