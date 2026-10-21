#!/usr/bin/env python3
"""Host-free checks for the phase batteries. They do not launch an instance."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lab-guests"))

import baseline_diag  # noqa: E402
import phase2_grade as grade  # noqa: E402
import sticky_write  # noqa: E402


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

    def test_lockdown_file_and_exact_image_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lockdown"
            path.write_text("none [integrity] confidentiality\n", encoding="utf-8")
            self.assertEqual(baseline_diag.read_lockdown(path), "none [integrity] confidentiality")
            path.write_text("[none] integrity confidentiality\n", encoding="utf-8")
            self.assertEqual(baseline_diag.read_lockdown(path), "[none] integrity confidentiality")
            path.write_text("lockdown,capability,bpf\n", encoding="utf-8")
            self.assertEqual(baseline_diag.read_lockdown(path), "")
        dated = "ubuntu-2404-noble-amd64-v20261014"
        ami = "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-20260901"
        self.assertEqual(baseline_diag.exact_image_name(dated), dated)
        self.assertEqual(baseline_diag.exact_image_name(ami), ami)
        self.assertEqual(baseline_diag.exact_image_name("ubuntu-2404-lts-amd64"), "")
        self.assertEqual(baseline_diag.exact_image_name(ami[:-1] + "*"), "")
        host = Path(__file__).resolve().parent / "lab-guests" / "phase2_host.py"
        text = host.read_text(encoding="utf-8")
        self.assertIn("baseline_diag.read_lockdown()", text)
        self.assertIn("baseline_diag.read_image_name()", text)

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

    def test_container_exit_records_fail_open_and_fail_closed(self) -> None:
        closed = grade.grade_container_exit(
            file_errno=13, egress_errno=1, program_listed=True, while_up_file_errno=13
        )
        self.assertEqual(closed["classification"], "fail_closed")
        self.assertEqual(closed["host_result"], "RECORDED")
        self.assertFalse(closed["lab_pass"])
        self.assertFalse(closed["customer_claim"])
        opened = grade.grade_container_exit(
            file_errno=0, egress_errno=0, program_listed=True, while_up_file_errno=13
        )
        self.assertEqual(opened["classification"], "fail_open")
        self.assertFalse(opened["lab_pass"])
        not_engaged = grade.grade_container_exit(
            file_errno=0, egress_errno=0, program_listed=False, while_up_file_errno=0
        )
        self.assertEqual(not_engaged["classification"], "deny_not_engaged")
        self.assertNotEqual(not_engaged["classification"], "fail_open")
        self.assertEqual(not_engaged["host_result"], "NOT_GRADED")
        self.assertFalse(not_engaged["lab_pass"])
        mixed = grade.grade_container_exit(
            file_errno=13, egress_errno=0, program_listed=True, while_up_file_errno=13
        )
        self.assertEqual(mixed["classification"], "mixed")
        missing = grade.grade_container_exit(
            file_errno=None, egress_errno=0, program_listed=None, while_up_file_errno=13
        )
        self.assertEqual(missing["classification"], "unmeasured")
        absent = grade.grade_container_exit(
            file_errno=0, egress_errno=0, program_listed=False, while_up_file_errno=13
        )
        self.assertEqual(absent["classification"], "program_not_listed")
        self.assertEqual(absent["reason"], "cgroup_program_absent_after_stop")
        self.assertEqual(absent["host_result"], "RECORDED")
        self.assertFalse(absent["cgroup_program_held"])
        self.assertNotEqual(absent["classification"], "fail_open")
        self.assertTrue(absent["measured_before_uninstall"])
        host = Path(__file__).resolve().parent.joinpath("lab-guests", "phase2_host.py").read_text(encoding="utf-8")
        body = host.split("def run_r15", 1)[1].split("\ndef run_2g", 1)[0]
        self.assertNotIn("cgroup detach", body)
        self.assertNotIn(".unlink(", body)
        self.assertNotIn("rmdir", body)
        self.assertIn('["docker", "stop"', body)
        self.assertLess(body.index('file_errno") != 13'), body.index('["docker", "stop"'))
        self.assertLess(body.index('["docker", "stop"'), body.index("engine_programs_listed()"))
        self.assertNotIn("authorized_uninstall", body)
        self.assertNotIn('"--uninstall"', body)
        self.assertIn("detached_by_lab", body)

    def test_banner_waits_for_the_exact_cgroup_pin_line(self) -> None:
        pins = (
            "Path DENY pinned: kprobe_open_deny -> __x64_sys_open\n"
            "Path DENY pinned: kprobe_openat_deny -> __x64_sys_openat\n"
        )
        self.assertFalse(grade.enforce_banner_ready(pins))
        scoped = "tc enforce : SCOPED (drop enrolled)\n"
        self.assertFalse(grade.enforce_banner_ready(scoped))
        self.assertFalse(grade.enforce_banner_ready(pins + scoped))
        failed = scoped + "cgroup_skb_egress_enforce not loaded (verifier). Egress deny is not on cgroup_skb.\n"
        self.assertFalse(grade.enforce_banner_ready(failed))
        self.assertFalse(grade.stderr_has_cgroup_pin("name cgroup_skb_egress_enforce tag abc\n"))
        ready = pins + scoped + "cgroup_skb_egress_enforce\n"
        self.assertTrue(grade.stderr_has_cgroup_pin(ready))
        self.assertTrue(grade.enforce_banner_ready(ready))
        host = Path(__file__).resolve().parent.joinpath("lab-guests", "phase2_host.py").read_text(encoding="utf-8")
        banner = host.split("def _banner_ready", 1)[1].split("\ndef _wait_scoped_banner", 1)[0]
        self.assertIn("grade.enforce_banner_ready", banner)
        self.assertNotIn("kprobe_open_deny", banner)

    def test_bpftool_prefix_still_counts_as_the_cgroup_program(self) -> None:
        self.assertTrue(grade.cgroup_skb_listed(["cgroup_skb_egre", "sshd"]))
        self.assertTrue(grade.cgroup_skb_listed(["cgroup_skb_egress_enforce"]))
        self.assertFalse(grade.cgroup_skb_listed(["sshd"]))
        self.assertFalse(grade.cgroup_skb_listed("cgroup_skb_egre"))
        host = Path(__file__).resolve().parent.joinpath("lab-guests", "phase2_host.py").read_text(encoding="utf-8")
        listed = host.split("def engine_programs_listed", 1)[1].split("\ndef run_r15", 1)[0]
        self.assertIn("grade.cgroup_skb_listed", listed)
        self.assertIn("cgroup_skb_egre", listed)

    def test_upgrade_cycle_checks_enforcement_and_uninstall(self) -> None:
        pin = "sha256:" + "a" * 64
        seal = "sha256:" + "b" * 64

        def step(name: str, digest: str, image: str, errno: int = 13) -> dict:
            return {
                "archive_sha256": digest,
                "attributed": errno == 13,
                "file_errno": errno,
                "image_id": image,
                "name": name,
                "uninstall": {"tail": "UNINSTALL_VERIFIED\n", "verified_removed": True},
            }

        held = grade.grade_image_cycle(
            [
                step("baseline", grade.PUBLIC_INSTALLER_PIN, pin),
                step("upgrade", grade.WORKING_SEAL, seal),
                step("rollback", grade.PUBLIC_INSTALLER_PIN, pin),
                step("reupgrade", grade.WORKING_SEAL, seal),
            ]
        )
        self.assertEqual(held["host_result"], "RECORDED")
        self.assertEqual(held["host_rollback"], "RAN")
        self.assertTrue(held["upgrade_pass"])
        self.assertFalse(held["lab_pass"])
        self.assertFalse(held["customer_claim"])
        self.assertEqual(held["reason"], "upgrade_rollback_reupgrade")
        opened = grade.grade_image_cycle(
            [
                step("baseline", grade.PUBLIC_INSTALLER_PIN, pin),
                step("upgrade", grade.WORKING_SEAL, seal, errno=0),
                step("rollback", grade.PUBLIC_INSTALLER_PIN, pin),
                step("reupgrade", grade.WORKING_SEAL, seal),
            ]
        )
        self.assertEqual(opened["reason"], "upgrade_enforcement")
        self.assertEqual(opened["host_result"], "FAIL")
        self.assertFalse(opened["upgrade_pass"])
        same = grade.grade_image_cycle(
            [
                step("baseline", grade.PUBLIC_INSTALLER_PIN, pin),
                step("upgrade", grade.WORKING_SEAL, pin),
                step("rollback", grade.PUBLIC_INSTALLER_PIN, pin),
                step("reupgrade", grade.WORKING_SEAL, pin),
            ]
        )
        self.assertEqual(same["reason"], "image_identity")
        host = Path(__file__).resolve().parent.joinpath("lab-guests", "phase2_host.py").read_text(encoding="utf-8")
        run = host.split("def _load_oci", 1)[1].split("\ndef run_2d", 1)[0]
        self.assertIn("public-pin.oci.tar", run)
        self.assertIn("grade_image_cycle", run)
        self.assertIn('"--uninstall"', run)
        self.assertNotIn("grade_rollback_gap", run)
        self.assertNotIn("cgroup detach", run)
        self.assertNotIn(".unlink(", run)
        self.assertNotIn("rmdir", run)
        perf = host.split("def run_2e", 1)[1].split("\ndef run_2f", 1)[0]
        self.assertIn("time_revoke=True", perf)
        self.assertIn("revoke_convergence_ms", perf)

    def test_redteam_kill_stays_on_the_pre_phase(self) -> None:
        text = Path(__file__).resolve().parents[1].joinpath("gcp", "lab-guests", "redteam_rows.py").read_text(
            encoding="utf-8"
        )
        start = text.index("def kill_on_this_phase")
        end = text.index("\ndef ", start + 1)
        namespace: dict[str, object] = {}
        exec(text[start:end], namespace)
        kill = namespace["kill_on_this_phase"]
        assert callable(kill)
        self.assertTrue(kill("pre"))
        self.assertFalse(kill("post"))
        self.assertIn('OUT_PATH = Path("/var/lib/vantio-lab/redteam-rows.json")', text)
        steps = Path(__file__).resolve().parents[1].joinpath("aws", "w3_lab_steps.py").read_text(encoding="utf-8")
        self.assertIn('REDTEAM_ROWS_REMOTE = "/var/lib/vantio-lab/redteam-rows.json"', steps)
        self.assertNotIn(":/tmp/redteam-rows.json", steps)

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
        kept = grade.apply_allowlisted_private(dict(held), 0)
        self.assertEqual(kept["host_result"], "PASS")
        self.assertEqual(kept["allowlisted_private"], "allowed")
        blocked = grade.apply_allowlisted_private(dict(held), 1)
        self.assertEqual(blocked["host_result"], "FAIL")
        self.assertEqual(blocked["classification"], "overblock")
        missing = grade.apply_allowlisted_private(dict(held), None)
        self.assertEqual(missing["host_result"], "FAIL")
        self.assertEqual(missing["allowlisted_private"], "missing")
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
        recorded = bytearray(grade.DENY_ATTR_SIZE)
        recorded[0:4] = (20287).to_bytes(4, "little")
        recorded[8:12] = (grade.DENY_KIND_EGRESS_CGROUP).to_bytes(4, "little")
        recorded[16:24] = (8498).to_bytes(8, "little")
        recorded[24:32] = (9).to_bytes(8, "little")
        self.assertEqual(grade.egress_record_anchor(bytes(recorded), 20287), 8498)
        self.assertEqual(grade.deny_record_anchor(bytes(recorded), 20287), 0)
        blocked = grade.grade_crash(
            enrolled_errno=110,
            unenrolled_errno=0,
            file_errno=13,
            file_attributed=True,
            enrolled_block_anchor=8498,
        )
        self.assertEqual(blocked["enrolled_egress"], "denied")
        self.assertEqual(blocked["host_result"], "PASS")
        self.assertEqual(blocked["classification"], "fail_closed")
        self.assertEqual(blocked["net_block_anchor"], 8498)
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
        self.assertIn('"--network=host"', text)
        self.assertIn('"/usr/bin/ip"', text)
        self.assertLess(text.index("def ensure_lab_iface"), text.index("def prepare_enforce"))
        refusal = text.split("def _refusal_log", 1)[1].split("def run_lsm_guard", 1)[0]
        self.assertLess(refusal.index("ensure_lab_iface()"), refusal.index("start_loader"))
        guard = text.split("def run_lsm_guard", 1)[1].split("RUNNERS", 1)[0]
        self.assertLess(guard.index("bpf_pins"), guard.index("apply_consented_lsm"))
        self.assertLess(guard.index("egress_present"), guard.index("apply_consented_lsm"))
        enforce = text.split("def _enforce_generation_log", 1)[1].split("def apply_consented_lsm", 1)[0]
        self.assertLess(enforce.index("ensure_lab_iface()"), enforce.index("start_loader"))
        prepared = text.split("def prepare_enforce", 1)[1].split("def _pin_fd", 1)[0]
        self.assertLess(prepared.index("ensure_lab_iface()"), prepared.index("start_loader"))
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

    def test_restart_keeps_the_same_process_and_anchor(self) -> None:
        held = grade.restart_keeps_the_same_anchor(
            pid=14303,
            before_errno=13,
            before_anchor=7136,
            after_errno=13,
            after_anchor=7136,
            before_count=1,
            after_count=2,
        )
        self.assertTrue(held["held"])
        self.assertIsNone(held["reason"])
        dropped = grade.restart_keeps_the_same_anchor(
            pid=14303,
            before_errno=13,
            before_anchor=7136,
            after_errno=0,
            after_anchor=0,
            before_count=1,
            after_count=1,
        )
        self.assertFalse(dropped["held"])
        self.assertEqual(dropped["reason"], "enrollment_dropped")
        standin = grade.restart_keeps_the_same_anchor(
            pid=14303,
            before_errno=13,
            before_anchor=7136,
            after_errno=13,
            after_anchor=7136,
            before_count=1,
            after_count=1,
        )
        self.assertEqual(standin["reason"], "no_new_deny_after_restart")
        changed = grade.restart_keeps_the_same_anchor(
            pid=14303,
            before_errno=13,
            before_anchor=7136,
            after_errno=13,
            after_anchor=8000,
            before_count=1,
            after_count=2,
        )
        self.assertEqual(changed["reason"], "anchor_not_carried")
        text = Path(__file__).resolve().parent.joinpath("lab-guests", "phase2_host.py").read_text(encoding="utf-8")
        body = text.split("def run_2d", 1)[1].split("def run_2e", 1)[0]
        self.assertLess(body.index("same_process_across_restart"), body.index("kill_loader()"))

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


class BaselineDiagTests(unittest.TestCase):
    def test_cause_names(self) -> None:
        self.assertEqual(baseline_diag.classify({"namei_outside_blocked": True, "open_errno": 13}), "parent_traverse")
        self.assertEqual(
            baseline_diag.classify({"file_unreadable_outside": True, "open_errno": 13}),
            "file_mode",
        )
        self.assertEqual(baseline_diag.classify({"apparmor_denied": True, "open_errno": 13}), "apparmor")
        self.assertEqual(
            baseline_diag.classify(
                {"apparmor_denied": True, "open_errno": 13, "deny_row_for_probe": True}
            ),
            "attributed_deny",
        )
        noise = "audit: type=1400 apparmor=DENIED operation=open name=/usr/bin/snap"
        hit = 'apparmor="DENIED" operation="open" name="/var/lib/vantio-pe-clean-host/d/secret" pid=14314'
        self.assertEqual(baseline_diag.relevant_apparmor([noise], "/var/lib/vantio-pe-clean-host/d/secret", 14314), [])
        self.assertEqual(
            baseline_diag.relevant_apparmor([noise, hit], "/var/lib/vantio-pe-clean-host/d/secret", 14314),
            [hit],
        )
        self.assertEqual(
            baseline_diag.classify({"open_errno": 13, "open_uses_o_creat": True, "sticky_parent": True}),
            "protected_regular",
        )
        self.assertEqual(baseline_diag.classify({"open_errno": 13, "deny_row_for_probe": True}), "attributed_deny")
        self.assertEqual(baseline_diag.classify({"open_errno": 13, "deny_row_other_pid": True}), "deny_row_other_pid")
        self.assertEqual(baseline_diag.classify({"open_errno": 13, "overflow_increased": True}), "silent_deny_overflow")
        self.assertEqual(
            baseline_diag.classify(
                {"open_errno": 13, "strace_eacces": True, "cgroup_matches_enrolled": True}
            ),
            "eacces_unaccounted",
        )
        self.assertEqual(
            baseline_diag.classify({"open_errno": 13, "strace_eacces": True, "cgroup_matches_enrolled": False}),
            "eacces_cgroup_mismatch",
        )
        self.assertEqual(baseline_diag.classify({"open_errno": 0}), "open_not_eacces")
        dump = [
            {"key": 0, "values": [{"cpu": 0, "value": 2}, {"cpu": 1, "value": 1}]},
            {"key": 2, "values": [{"cpu": 0, "value": 0}, {"cpu": 1, "value": 0}]},
            {"key": 7, "values": [{"cpu": 0, "value": 2}, {"cpu": 1, "value": 0}]},
        ]
        summary = baseline_diag.summarize_decision(dump)
        self.assertEqual(summary["hooks"]["path"]["hits"], 3)
        self.assertEqual(summary["hooks"]["path"]["ceiling_path"], 0)
        self.assertEqual(summary["hooks"]["path"]["allow_reason_name"], "path_miss")
        hex_dump = [
            {
                "key": ["0x00", "0x00", "0x00", "0x00"],
                "values": [
                    {"cpu": 0, "value": ["0x9b", "0x00", "0x00", "0x00", "0x00", "0x00", "0x00", "0x00"]},
                    {"cpu": 1, "value": ["0xab", "0x00", "0x00", "0x00", "0x00", "0x00", "0x00", "0x00"]},
                ],
            }
        ]
        hex_summary = baseline_diag.summarize_decision(hex_dump)
        self.assertEqual(hex_summary["hooks"]["path"]["hits"], 326)
        self.assertFalse(baseline_diag.bpf_lsm_active("capability,landlock,selinux"))
        self.assertTrue(baseline_diag.bpf_lsm_active("apparmor,bpf"))
        self.assertEqual(baseline_diag.cgroup_enroll_keys(6745, (0x11 << 32) | 6745)[:2], [6745, (0x11 << 32) | 6745])
        proved = baseline_diag.classify_readiness_log(
            "INSTALL_ENFORCEMENT_READINESS_BLOCKED reason=bpf_lsm_inactive\n  enforce    : NOT ENFORCING\n"
        )
        self.assertTrue(proved["blocked"])
        claimed = baseline_diag.classify_readiness_log(
            "INSTALL_ENFORCEMENT_READINESS_BLOCKED reason=bpf_lsm_inactive\n  tc enforce : SCOPED (drop enrolled)\n"
        )
        self.assertFalse(claimed["blocked"])
        self.assertTrue(claimed["reports_enforcing"])
        planned = baseline_diag.plan_grub_lsm(
            'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"\nGRUB_CMDLINE_LINUX=""\n',
            ['GRUB_CMDLINE_LINUX_DEFAULT="lsm=capability,apparmor"\n'],
            "lockdown,capability,apparmor,bpf",
        )
        self.assertNotIn("error", planned)
        self.assertIn('GRUB_CMDLINE_LINUX="lsm=lockdown,capability,apparmor,bpf"', planned["main"])
        self.assertNotIn("lsm=", planned["extras"][0])
        dropin = baseline_diag.lsm_dropin_text("lockdown,capability,apparmor,bpf")
        self.assertIn("lsm=lockdown,capability,apparmor,bpf", dropin)
        self.assertIn('GRUB_CMDLINE_LINUX="${_vantio_linux# } lsm=lockdown,capability,apparmor,bpf"', dropin)
        self.assertNotIn('GRUB_CMDLINE_LINUX=""', dropin)
        self.assertIn("case $_vantio_tok in", dropin)
        cfg = "\n".join(
            [
                "menuentry 'Ubuntu' {",
                "  linux /boot/vmlinuz root=PARTUUID ro console=ttyS0 lsm=lockdown,capability,apparmor,bpf",
                "}",
            ]
        )
        self.assertTrue(baseline_diag.grub_cfg_has_lsm(cfg, "lockdown,capability,apparmor,bpf"))
        self.assertFalse(baseline_diag.grub_cfg_has_lsm(cfg, "lockdown,capability,apparmor"))
        later = "linux /boot/vmlinuz root=PARTUUID ro console=ttyS0\nlinux /boot/vmlinuz root=PARTUUID lsm=lockdown,capability,apparmor,bpf\n"
        self.assertFalse(baseline_diag.grub_cfg_has_lsm(later, "lockdown,capability,apparmor,bpf"))
        overwritten = "linux /vmlinuz root=PARTUUID ro lsm=lockdown,capability,apparmor,bpf lsm=lockdown,capability,apparmor\n"
        self.assertFalse(baseline_diag.grub_cfg_has_lsm(overwritten, "lockdown,capability,apparmor,bpf"))
        stock_entry = "\n".join(
            [
                "linux /vmlinuz root=PARTUUID ro lsm=lockdown,capability,apparmor,bpf",
                "linux /vmlinuz root=PARTUUID ro console=ttyS0,115200 panic=-1",
            ]
        )
        self.assertFalse(baseline_diag.grub_cfg_has_lsm(stock_entry, "lockdown,capability,apparmor,bpf"))
        self.assertEqual(
            baseline_diag.first_linux_line(stock_entry),
            "linux /vmlinuz root=PARTUUID ro console=ttyS0,115200 panic=-1",
        )
        buried = (
            "linux /vmlinuz root=PARTUUID ro console=ttyS0,115200 "
            "lsm=lockdown,capability,apparmor,bpf panic=-1\n"
        )
        self.assertTrue(buried.strip().endswith("panic=-1"))
        self.assertTrue(baseline_diag.grub_cfg_has_lsm(buried, "lockdown,capability,apparmor,bpf"))
        forced = baseline_diag.rewrite_linux_lines(stock_entry, "lockdown,capability,apparmor,bpf")
        self.assertFalse(baseline_diag.grub_cfg_has_lsm(forced, "lockdown,capability,apparmor,bpf"))
        self.assertIn("panic=-1 lsm=lockdown,capability,apparmor,bpf", forced)
        regen = baseline_diag.reboot_with_grub_script("lockdown,capability,apparmor,bpf")
        self.assertNotIn("grub-mkconfig -o", regen)
        self.assertNotIn("command -v grub-mkconfig", regen)
        self.assertNotIn("panic=-1 lsm=", regen)
        self.assertIn("updater=update-grub", regen)
        self.assertIn("/etc/default/grub.d/99-vantio-lsm.cfg", regen)
        self.assertIn("set -euo pipefail", regen)
        self.assertIn("refusing reboot", regen)
        self.assertIn("systemctl reboot --force", regen)
        self.assertIn("keeping sealed boot line", regen)
        self.assertIn("lsm=lockdown,capability,apparmor,bpf", regen)
        bare = baseline_diag.reboot_with_grub_script()
        self.assertNotIn("systemctl reboot", bare)
        self.assertIn("refusing reboot: no lab lsm token", bare)
        fresh = baseline_diag.stock_reboot_script()
        self.assertIn("systemctl reboot --force", fresh)
        self.assertNotIn("update-grub", fresh)
        self.assertNotIn("lsm=", fresh)
        self.assertIn("stock reboot", fresh)
        syntax = subprocess.run(["bash", "-n"], input=fresh, text=True, capture_output=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        cloud = 'GRUB_CMDLINE_LINUX="console=ttyS0,115200 panic=-1"\n'
        rewritten = baseline_diag.assignments_with_lsm(cloud, "lockdown,capability,apparmor,bpf")
        self.assertIn("console=ttyS0,115200 panic=-1 lsm=lockdown,capability,apparmor,bpf", rewritten)
        missed, code = baseline_diag.lsm_boot_decision(
            "lockdown,capability,apparmor",
            "root=PARTUUID ro console=ttyS0",
            {"reboot_requested": True},
        )
        self.assertEqual(code, 2)
        self.assertIsNotNone(missed)
        self.assertEqual(missed["host_result"], "FAIL")
        self.assertFalse(missed["cmdline_has_bpf"])
        self.assertIn("console=ttyS0", missed["cmdline"])
        pending, pending_code = baseline_diag.lsm_boot_decision("lockdown,capability,apparmor", "root=PARTUUID", None)
        self.assertIsNone(pending)
        self.assertEqual(pending_code, 1)
        host = Path(__file__).resolve().parent.joinpath("lab-guests/phase2_host.py").read_text(encoding="utf-8")
        self.assertIn("99-vantio-lsm.cfg", host)
        self.assertIn("0o755", host)
        apply = host.split("def apply_consented_lsm", 1)[1].split("\ndef ", 1)[0]
        self.assertNotIn("rewrite_linux_lines", apply)
        self.assertNotIn("grub-mkconfig", apply)
        redteam = Path(__file__).resolve().parents[1].joinpath("gcp/redteam_campaign.py").read_text(encoding="utf-8")
        self.assertIn("sudo mkdir -p /var/lib/vantio-lab", redteam)
        self.assertNotIn("rm -rf {od.GUEST_DIR} && mkdir -p {od.GUEST_DIR}", redteam)
        self.assertEqual(
            baseline_diag.plan_grub_lsm("GRUB_CMDLINE_LINUX+=\"lsm=apparmor\"\n", [], "capability,bpf"),
            {"error": "grub_append"},
        )
        enabled = baseline_diag.lsm_status_body(
            "lockdown,capability,apparmor,bpf",
            "root=PARTUUID lsm=lockdown,capability,apparmor,bpf",
            {"reboot_requested": True, "stock_lsm": "lockdown,capability,apparmor"},
        )
        self.assertEqual(enabled["host_result"], "LSM_ENABLED")
        ignored = baseline_diag.lsm_status_body(
            "lockdown,capability,apparmor",
            "root=PARTUUID lsm=lockdown,capability,apparmor,bpf",
            {"reboot_requested": True},
        )
        self.assertEqual(ignored["host_result"], "FAIL")
        self.assertEqual(ignored["reason"], "bpf_not_active")
        stock = baseline_diag.lsm_status_body("capability,bpf", "root=PARTUUID", None)
        self.assertEqual(stock["host_result"], "LSM_ALREADY_ACTIVE")
        self.assertTrue(stock["stock_bpf_lsm"])

    def test_stock_aws_loader_log_requests_the_bpf_reboot(self) -> None:
        stock_lsm = "lockdown,capability,landlock,yama,apparmor,ima,evm"
        log = (
            "Vantio Phantom Engine\n"
            "not enforcing\n"
            "bpf is not in the active LSM list. Add lsm=...,bpf and reboot. "
            "The installer writes that line only after explicit operator consent.\n"
        )
        verdict = baseline_diag.classify_readiness_log(log)
        self.assertTrue(verdict["blocked"])
        self.assertEqual(verdict["reason"], "lsm_bpf_inactive")
        self.assertTrue(verdict["not_enforcing"])
        self.assertFalse(verdict["reports_enforcing"])
        self.assertFalse(baseline_diag.bpf_lsm_active(stock_lsm))
        action = baseline_diag.lsm_guard_action(
            verdict,
            stock_lsm=stock_lsm,
            bpf_pins=[],
            egress_present=False,
        )
        self.assertTrue(action["write_grub"])
        self.assertEqual(action["lsm_value"], stock_lsm + ",bpf")
        self.assertEqual(action["reason"], "lsm_bpf_inactive")
        self.assertFalse(baseline_diag.reboot_after_grub(action, False))
        self.assertTrue(baseline_diag.reboot_after_grub(action, True))
        pinned = baseline_diag.lsm_guard_action(
            verdict,
            stock_lsm=stock_lsm,
            bpf_pins=["vantio_enforce"],
            egress_present=False,
        )
        self.assertFalse(pinned["write_grub"])
        self.assertEqual(pinned["reason"], "pins_left")
        self.assertFalse(baseline_diag.reboot_after_grub(pinned, True))
        claimed = baseline_diag.classify_readiness_log(log + "tc enforce : SCOPED (drop enrolled)\n")
        self.assertFalse(claimed["blocked"])
        self.assertTrue(claimed["reports_enforcing"])

    def test_cloudimg_override_keeps_lsm_before_panic(self) -> None:
        token = "lockdown,capability,landlock,yama,apparmor,ima,evm,bpf"
        main = f'GRUB_CMDLINE_LINUX_DEFAULT="quiet"\nGRUB_CMDLINE_LINUX="lsm={token}"\n'
        cloud = (
            "GRUB_RECORDFAIL_TIMEOUT=0\n"
            "GRUB_TIMEOUT=0\n"
            'GRUB_CMDLINE_LINUX_DEFAULT="console=tty1 console=ttyS0 nvme_core.io_timeout=4294967295"\n'
            'GRUB_CMDLINE_LINUX=""\n'
            "GRUB_TERMINAL=console\n"
        )
        line = baseline_diag.render_cloudimg_linux_line(main, cloud, token)
        self.assertTrue(line.endswith("panic=-1"), line)
        self.assertIn("console=tty1 console=ttyS0 nvme_core.io_timeout=4294967295", line)
        self.assertTrue(baseline_diag.grub_cfg_has_lsm(line, token))
        self.assertEqual(baseline_diag.last_lsm_token(line), f"lsm={token}")
        self.assertEqual(baseline_diag.render_cloudimg_linux_line(main, cloud, token), line)
        late = line.replace(f" lsm={token} panic=-1", f" panic=-1 lsm={token}")
        self.assertTrue(late.endswith(f"lsm={token}"), late)
        self.assertFalse(baseline_diag.grub_cfg_has_lsm(late, token))

    def test_reboot_script_refuses_lsm_after_panic_on_the_cloud_line(self) -> None:
        token = "lockdown,capability,landlock,yama,apparmor,ima,evm,bpf"
        script = baseline_diag.reboot_with_grub_script(token)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / "grub.cfg"
            efi = root / "efi"
            efi.mkdir()
            (efi / "grub.cfg").write_text("set prefix=stub\n", encoding="utf-8")
            bad = (
                "linux /vmlinuz-7.0.0-1013-aws root=PARTUUID=1feb5770-cc6a-4240-8c18-3b802f140518 "
                "ro console=tty1 console=ttyS0 nvme_core.io_timeout=4294967295 "
                f"panic=-1 lsm={token}\n"
            )
            cfg.write_text(bad, encoding="utf-8")
            dropin = root / "99-vantio-lsm.cfg"
            dropin.write_text(baseline_diag.lsm_dropin_text(token), encoding="utf-8")
            updater = root / "update-grub"
            updater.write_text(f"#!/bin/sh\nprintf '%s' '{bad}' > '{cfg}'\n", encoding="utf-8")
            updater.chmod(0o755)
            sandboxed = script.replace("updater=update-grub", f"updater={updater}")
            sandboxed = sandboxed.replace("/boot/grub/grub.cfg", str(cfg)).replace("/boot/efi", str(efi))
            sandboxed = sandboxed.replace("dropin=/etc/default/grub.d/99-vantio-lsm.cfg", f"dropin={dropin}")
            sandboxed = sandboxed.replace("log=/var/lib/vantio-lab/grub-mkconfig.txt", f"log={root / 'log.txt'}")
            sandboxed = sandboxed.replace("mkdir -p /var/lib/vantio-lab\n", f"mkdir -p {root}\n")
            sandboxed = sandboxed.replace("systemctl reboot --force", "echo REBOOT_SHOULD_NOT")
            ran = subprocess.run(["bash", "-c", sandboxed], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 1, ran.stderr + ran.stdout)
            self.assertNotIn("REBOOT", ran.stdout)
            self.assertIn("refusing reboot", (root / "log.txt").read_text(encoding="utf-8"))

    def test_uninstall_removes_the_dropin_unless_reboot_is_pending(self) -> None:
        self.assertTrue(
            baseline_diag.uninstall_keeps_boot_token(
                {"host_result": "GUARD_PROVED", "reboot_requested": True}
            )
        )
        self.assertFalse(
            baseline_diag.uninstall_keeps_boot_token(
                {"host_result": "FAIL", "reboot_requested": False, "reason": "readiness_not_blocked"}
            )
        )
        shell = Path(__file__).resolve().parent.joinpath("lab-guests/enterprise-rows.sh").read_text(encoding="utf-8")
        uninstall = shell[shell.index("authorized_uninstall()"): shell.index("\nmode=${2:-enterprise}")]
        self.assertLess(uninstall.index("UNINSTALL_VERIFIED"), uninstall.index("clear_lab_grub_lsm"))
        self.assertIn("remove_consented_lsm_live", uninstall)
        self.assertIn("UNINSTALL_GRUB_LSM", uninstall)
        token = "lockdown,capability,landlock,yama,apparmor,ima,evm,bpf"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dropin = root / "etc/default/grub.d/99-vantio-lsm.cfg"
            dropin.parent.mkdir(parents=True)
            dropin.write_text(baseline_diag.lsm_dropin_text(token), encoding="utf-8")
            cfg = root / "boot/grub/grub.cfg"
            cfg.parent.mkdir(parents=True)
            cfg.write_text(
                "linux /vmlinuz ro console=tty1 console=ttyS0 nvme_core.io_timeout=4294967295 "
                f"lsm={token} panic=-1\n",
                encoding="utf-8",
            )

            def updater() -> int:
                cfg.write_text(
                    "linux /vmlinuz ro console=tty1 console=ttyS0 nvme_core.io_timeout=4294967295 panic=-1\n",
                    encoding="utf-8",
                )
                return 0

            removed = baseline_diag.remove_consented_lsm(root, updater)
            self.assertTrue(removed["ok"], removed)
            self.assertTrue(removed["removed"])
            self.assertFalse(dropin.exists())
            self.assertFalse(baseline_diag.boot_lines_carry_lsm(cfg.read_text(encoding="utf-8"), token))
            again = baseline_diag.remove_consented_lsm(root, updater)
            self.assertTrue(again["ok"])
            self.assertFalse(again["removed"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dropin = root / "etc/default/grub.d/99-vantio-lsm.cfg"
            dropin.parent.mkdir(parents=True)
            dropin.write_text(baseline_diag.lsm_dropin_text(token), encoding="utf-8")
            cfg = root / "boot/grub/grub.cfg"
            cfg.parent.mkdir(parents=True)
            stale = (
                "linux /vmlinuz ro console=tty1 console=ttyS0 nvme_core.io_timeout=4294967295 "
                f"lsm={token} panic=-1\n"
            )
            cfg.write_text(stale, encoding="utf-8")
            kept = baseline_diag.remove_consented_lsm(root, lambda: 0)
            self.assertFalse(kept["ok"])
            self.assertEqual(kept["error"], "grub_cfg_still_has_lsm")
            self.assertEqual(dropin.read_text(encoding="utf-8"), baseline_diag.lsm_dropin_text(token))
            self.assertEqual(cfg.read_text(encoding="utf-8"), stale)

    def test_uninstall_strips_lsm_from_grub_and_the_cloudimg_file(self) -> None:
        token = "lockdown,capability,landlock,yama,apparmor,ima,evm,bpf"
        needle = f"lsm={token}"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            main = root / "etc/default/grub"
            cloud = root / "etc/default/grub.d/50-cloudimg-settings.cfg"
            dropin = root / "etc/default/grub.d/99-vantio-lsm.cfg"
            bios = root / "boot/grub/grub.cfg"
            efi = root / "boot/efi/EFI/ubuntu/grub.cfg"
            main.parent.mkdir(parents=True)
            cloud.parent.mkdir(parents=True)
            bios.parent.mkdir(parents=True)
            efi.parent.mkdir(parents=True)
            main.write_text(f'GRUB_CMDLINE_LINUX="console=ttyS0 {needle}"\n', encoding="utf-8")
            cloud.write_text(
                'GRUB_CMDLINE_LINUX_DEFAULT="console=tty1 console=ttyS0 '
                f'nvme_core.io_timeout=4294967295 {needle}"\n'
                f'GRUB_CMDLINE_LINUX="{needle}"\n',
                encoding="utf-8",
            )
            dropin.write_text(baseline_diag.lsm_dropin_text(token), encoding="utf-8")
            bios.write_text(f"linux /vmlinuz ro {needle} panic=-1\n", encoding="utf-8")
            efi.write_text(f"linux /vmlinuz ro {needle} panic=-1\n", encoding="utf-8")

            def updater() -> int:
                sources = main.read_text(encoding="utf-8") + cloud.read_text(encoding="utf-8")
                line = (
                    f"linux /vmlinuz ro {needle} panic=-1\n"
                    if needle in sources
                    else "linux /vmlinuz ro console=tty1 console=ttyS0 panic=-1\n"
                )
                bios.write_text(line, encoding="utf-8")
                efi.write_text(line, encoding="utf-8")
                return 0

            removed = baseline_diag.remove_consented_lsm(root, updater)
            self.assertTrue(removed["ok"], removed)
            self.assertFalse(dropin.exists())
            self.assertNotIn(needle, main.read_text(encoding="utf-8"))
            self.assertNotIn(needle, cloud.read_text(encoding="utf-8"))
            self.assertIn("console=tty1", cloud.read_text(encoding="utf-8"))
            self.assertFalse(baseline_diag.boot_lines_carry_lsm(bios.read_text(encoding="utf-8"), token))
            self.assertFalse(baseline_diag.boot_lines_carry_lsm(efi.read_text(encoding="utf-8"), token))

            dropin.write_text(baseline_diag.lsm_dropin_text(token), encoding="utf-8")
            main.write_text("GRUB_CMDLINE_LINUX=\"\"\n", encoding="utf-8")
            cloud.write_text('GRUB_CMDLINE_LINUX_DEFAULT="console=tty1"\n', encoding="utf-8")
            bios.write_text("linux /vmlinuz ro panic=-1\n", encoding="utf-8")
            efi.write_text(f"linux /vmlinuz ro {needle} panic=-1\n", encoding="utf-8")
            left = baseline_diag.remove_consented_lsm(root, lambda: 0)
            self.assertFalse(left["ok"])
            self.assertEqual(left["error"], "grub_cfg_still_has_lsm")
            self.assertTrue(dropin.is_file())
            self.assertIn(needle, efi.read_text(encoding="utf-8"))

    def test_stock_reboot_script_does_not_replace_a_sealed_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "reboot-with-grub.sh"
            target.write_text("#!/bin/bash\necho sealed\n", encoding="utf-8")
            target.chmod(0o755)
            self.assertEqual(baseline_diag.install_stock_reboot_script(target), "present")
            self.assertIn("echo sealed", target.read_text(encoding="utf-8"))
            missing = Path(tmp) / "fresh" / "reboot-with-grub.sh"
            self.assertEqual(baseline_diag.install_stock_reboot_script(missing), "installed")
            text = missing.read_text(encoding="utf-8")
            self.assertIn("systemctl reboot --force", text)
            self.assertNotIn("update-grub", text)
            self.assertTrue(os.access(missing, os.X_OK))

    def test_reboot_script_keeps_the_panic_line_token(self) -> None:
        token = "lockdown,capability,apparmor,bpf"
        script = baseline_diag.reboot_with_grub_script(token)
        syntax = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / "grub.cfg"
            efi = root / "efi"
            efi.mkdir()
            (efi / "grub.cfg").write_text("set prefix=stub\n", encoding="utf-8")
            cfg.write_text("menuentry 'Ubuntu' {\nset prefix=old\n}\n", encoding="utf-8")
            dropin = root / "99-vantio-lsm.cfg"
            dropin.write_text("lab\n", encoding="utf-8")
            generated = (
                "linux /vmlinuz root=PARTUUID=10c90fd7-bb6d-4926-b2f0-5f9d77cdcf47 "
                f"ro console=ttyS0,115200 lsm={token} panic=-1\n"
            )
            updater = root / "update-grub"
            updater.write_text(f"#!/bin/sh\nprintf '%s' '{generated}' > '{cfg}'\n", encoding="utf-8")
            updater.chmod(0o755)
            sandboxed = script.replace("updater=update-grub", f"updater={updater}")
            sandboxed = sandboxed.replace("/boot/grub/grub.cfg", str(cfg)).replace("/boot/efi", str(efi))
            sandboxed = sandboxed.replace("dropin=/etc/default/grub.d/99-vantio-lsm.cfg", f"dropin={dropin}")
            sandboxed = sandboxed.replace("log=/var/lib/vantio-lab/grub-mkconfig.txt", f"log={root / 'log.txt'}")
            sandboxed = sandboxed.replace("mkdir -p /var/lib/vantio-lab\n", f"mkdir -p {root}\n")
            sandboxed = sandboxed.replace("systemctl reboot --force", "echo REBOOT")
            ran = subprocess.run(["bash", "-c", sandboxed], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr + ran.stdout)
            self.assertIn("REBOOT", ran.stdout)
            booted = cfg.read_text(encoding="utf-8").strip()
            self.assertTrue(booted.endswith("panic=-1"), booted)
            self.assertIn(f"lsm={token}", booted)
            self.assertNotIn(f"panic=-1 lsm={token}", booted)
            self.assertEqual((efi / "grub.cfg").read_text(encoding="utf-8"), "set prefix=stub\n")

            sealed = cfg.read_text(encoding="utf-8")
            stamp = root / "regenerated"
            clobber = root / "update-grub-clobber"
            clobber.write_text(
                "#!/bin/sh\n"
                f"touch '{stamp}'\n"
                f"printf '%s\\n' 'linux /vmlinuz root=PARTUUID ro console=ttyS0,115200 panic=-1' > '{cfg}'\n",
                encoding="utf-8",
            )
            clobber.chmod(0o755)
            keep = script.replace("updater=update-grub", f"updater={clobber}")
            keep = keep.replace("/boot/grub/grub.cfg", str(cfg)).replace("/boot/efi", str(efi))
            keep = keep.replace("dropin=/etc/default/grub.d/99-vantio-lsm.cfg", f"dropin={dropin}")
            keep = keep.replace("log=/var/lib/vantio-lab/grub-mkconfig.txt", f"log={root / 'keep.txt'}")
            keep = keep.replace("mkdir -p /var/lib/vantio-lab\n", f"mkdir -p {root}\n")
            keep = keep.replace("systemctl reboot --force", "echo REBOOT")
            kept = subprocess.run(["bash", "-c", keep], capture_output=True, text=True)
            self.assertEqual(kept.returncode, 0, kept.stderr + kept.stdout)
            self.assertIn("REBOOT", kept.stdout)
            self.assertFalse(stamp.exists())
            self.assertEqual(cfg.read_text(encoding="utf-8"), sealed)
            self.assertIn("keeping sealed boot line", (root / "keep.txt").read_text(encoding="utf-8"))
            self.assertIn("boot-evidence.json", script)
            self.assertIn("boot_evidence_snapshot", script)

            cfg.write_text(
                "linux /vmlinuz root=PARTUUID ro console=ttyS0,115200 panic=-1\n",
                encoding="utf-8",
            )
            stock = root / "update-grub-stock"
            stock.write_text(
                "#!/bin/sh\n"
                f"printf '%s\\n' 'linux /vmlinuz root=PARTUUID ro console=ttyS0,115200 panic=-1' > '{cfg}'\n",
                encoding="utf-8",
            )
            stock.chmod(0o755)
            refused = script.replace("updater=update-grub", f"updater={stock}")
            refused = refused.replace("/boot/grub/grub.cfg", str(cfg)).replace("/boot/efi", str(efi))
            refused = refused.replace("dropin=/etc/default/grub.d/99-vantio-lsm.cfg", f"dropin={dropin}")
            refused = refused.replace("log=/var/lib/vantio-lab/grub-mkconfig.txt", f"log={root / 'stock.txt'}")
            refused = refused.replace("mkdir -p /var/lib/vantio-lab\n", f"mkdir -p {root}\n")
            refused = refused.replace("systemctl reboot --force", "echo REBOOT_SHOULD_NOT")
            blocked = subprocess.run(["bash", "-c", refused], capture_output=True, text=True)
            self.assertEqual(blocked.returncode, 1, blocked.stderr + blocked.stdout)
            self.assertNotIn("REBOOT", blocked.stdout)
            self.assertIn("refusing reboot", (root / "stock.txt").read_text(encoding="utf-8"))

            marker = root / "updater-ran"
            missing = root / "missing-dropin.cfg"
            early = root / "update-grub-early"
            early.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
            early.chmod(0o755)
            nodropin = script.replace("updater=update-grub", f"updater={early}")
            nodropin = nodropin.replace("/boot/grub/grub.cfg", str(cfg)).replace("/boot/efi", str(efi))
            nodropin = nodropin.replace("dropin=/etc/default/grub.d/99-vantio-lsm.cfg", f"dropin={missing}")
            nodropin = nodropin.replace("log=/var/lib/vantio-lab/grub-mkconfig.txt", f"log={root / 'missing.txt'}")
            nodropin = nodropin.replace("mkdir -p /var/lib/vantio-lab\n", f"mkdir -p {root}\n")
            nodropin = nodropin.replace("systemctl reboot --force", "echo REBOOT_SHOULD_NOT")
            missed = subprocess.run(["bash", "-c", nodropin], capture_output=True, text=True)
            self.assertEqual(missed.returncode, 1, missed.stderr + missed.stdout)
            self.assertFalse(marker.exists())
            self.assertIn("refusing reboot", (root / "missing.txt").read_text(encoding="utf-8"))

    def test_dropin_is_the_line_a_cloud_image_boots(self) -> None:
        token = "lockdown,capability,landlock,yama,apparmor,ima,evm,bpf"
        partuuid = "10c90fd7-bb6d-4926-b2f0-5f9d77cdcf47"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "00-main.cfg").write_text('GRUB_CMDLINE_LINUX=""\n', encoding="utf-8")
            (root / "40-force-partuuid.cfg").write_text(
                f'GRUB_FORCE_PARTUUID="{partuuid}"\n',
                encoding="utf-8",
            )
            (root / "50-cloudimg-settings.cfg").write_text(
                'GRUB_CMDLINE_LINUX_DEFAULT="console=ttyS0,115200"\n',
                encoding="utf-8",
            )
            (root / "99-vantio-lsm.cfg").write_text(baseline_diag.lsm_dropin_text(token), encoding="utf-8")
            emit = (
                "linux /vmlinuz root=PARTUUID=$GRUB_FORCE_PARTUUID "
                "ro $GRUB_CMDLINE_LINUX $GRUB_CMDLINE_LINUX_DEFAULT panic=-1"
            )
            sourced = "\n".join(
                [
                    "set -eu",
                    'GRUB_CMDLINE_LINUX=""',
                    'GRUB_CMDLINE_LINUX_DEFAULT=""',
                    f'. "{root / "00-main.cfg"}"',
                    f'. "{root / "40-force-partuuid.cfg"}"',
                    f'. "{root / "50-cloudimg-settings.cfg"}"',
                    f'. "{root / "99-vantio-lsm.cfg"}"',
                    f'. "{root / "99-vantio-lsm.cfg"}"',
                    f"printf '%s\\n' \"{emit}\"",
                ]
            )
            ran = subprocess.run(["dash", "-c", sourced], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            line = ran.stdout.strip()
            self.assertTrue(line.endswith("panic=-1"), line)
            self.assertEqual(baseline_diag.last_lsm_token(line), f"lsm={token}")
            stock = "\n".join(
                [
                    "set -eu",
                    'GRUB_CMDLINE_LINUX=""',
                    'GRUB_CMDLINE_LINUX_DEFAULT=""',
                    f'. "{root / "00-main.cfg"}"',
                    f'. "{root / "40-force-partuuid.cfg"}"',
                    f'. "{root / "50-cloudimg-settings.cfg"}"',
                    f"printf '%s\\n' \"{emit}\"",
                ]
            )
            plain = subprocess.run(["dash", "-c", stock], capture_output=True, text=True)
            self.assertEqual(plain.returncode, 0, plain.stderr)
            recorded = plain.stdout.strip()
            self.assertTrue(recorded.endswith("ro  console=ttyS0,115200 panic=-1") or recorded.endswith("ro console=ttyS0,115200 panic=-1"), recorded)
            self.assertEqual(baseline_diag.last_lsm_token(recorded), "")

    def test_efi_stub_is_kept_and_the_boot_file_gains_lsm_before_panic(self) -> None:
        token = "lockdown,capability,landlock,yama,apparmor,ima,evm,bpf"
        stub_uuid = "8e2a9073-72b3-4cba-bf15-3704b810f72a"
        stub = (
            f"search.fs_uuid {stub_uuid} root hd0,gpt13\n"
            "set prefix=($root)'/grub'\n"
            "configfile $prefix/grub.cfg\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            efi = root / "boot/efi/EFI/ubuntu"
            efi.mkdir(parents=True)
            (efi / "grub.cfg").write_text(stub, encoding="utf-8")
            bios = root / "boot/grub"
            bios.mkdir(parents=True)
            (bios / "grub.cfg").write_text(
                "linux /vmlinuz root=PARTUUID=10c90fd7-bb6d-4926-b2f0-5f9d77cdcf47 "
                "ro console=ttyS0,115200 panic=-1\n",
                encoding="utf-8",
            )
            sealed = baseline_diag.seal_firmware_tree(root, token, boot_uuid=stub_uuid)
            self.assertTrue(sealed["ok"], sealed)
            self.assertEqual((efi / "grub.cfg").read_text(encoding="utf-8"), stub)
            chain = sealed["bootchain"]
            self.assertEqual(chain["efi_kind"], "stub")
            self.assertEqual(chain["stub_uuid"], stub_uuid)
            self.assertIn("/grub", chain["stub_prefix"])
            self.assertEqual(chain["decision"], "match")
            booted = (bios / "grub.cfg").read_text(encoding="utf-8").strip()
            self.assertTrue(booted.endswith("panic=-1"), booted)
            self.assertIn(f"lsm={token}", booted)
            self.assertNotIn(f"panic=-1 lsm={token}", booted)
            self.assertTrue(baseline_diag.firmware_cmdline_ok(booted, token))
            self.assertEqual(chain["uuid_mount"], "boot")
            self.assertEqual(chain["grub_alias"], "absent")
            self.assertFalse((root / "grub" / "grub.cfg").exists())

    def test_boot_manifest_hashes_the_stub_and_both_menus(self) -> None:
        stub = "search.fs_uuid 6a4d7abf-5bb6-427d-a1f5-1df6cda29962 root\nset prefix=($root)'/grub'\nconfigfile $prefix/grub.cfg\n"
        sealed = (
            "linux /vmlinuz root=PARTUUID=10c90fd7-bb6d-4926-b2f0-5f9d77cdcf47 "
            "ro console=ttyS0,115200 lsm=lockdown,capability,apparmor,bpf panic=-1\n"
        )
        stock = (
            "linux /vmlinuz root=PARTUUID=10c90fd7-bb6d-4926-b2f0-5f9d77cdcf47 "
            "ro console=ttyS0,115200 panic=-1\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "boot/efi/EFI/ubuntu").mkdir(parents=True)
            (root / "boot/grub").mkdir(parents=True)
            (root / "grub").mkdir()
            (root / "boot/efi/EFI/ubuntu/grub.cfg").write_text(stub, encoding="utf-8")
            (root / "boot/grub/grub.cfg").write_text(sealed, encoding="utf-8")
            (root / "grub/grub.cfg").write_text(stock, encoding="utf-8")
            rows = {row["path"]: row for row in baseline_diag.boot_file_manifest(root)}
            self.assertEqual(set(rows), {"boot/efi/EFI/ubuntu/grub.cfg", "boot/grub/grub.cfg", "grub/grub.cfg"})
            self.assertEqual(rows["boot/efi/EFI/ubuntu/grub.cfg"]["kind"], "stub")
            self.assertEqual(rows["boot/grub/grub.cfg"]["sha256"], hashlib.sha256(sealed.encode()).hexdigest())
            self.assertIn("lsm=lockdown,capability,apparmor,bpf", rows["boot/grub/grub.cfg"]["boot_line"])
            self.assertNotIn("lsm=", rows["grub/grub.cfg"]["boot_line"])
            self.assertEqual(rows["grub/grub.cfg"]["sha256"], hashlib.sha256(stock.encode()).hexdigest())
            shot = baseline_diag.boot_evidence_snapshot(root)
            self.assertEqual(shot["files"], baseline_diag.boot_file_manifest(root))
            self.assertNotIn("efibootmgr", shot)

    def test_empty_grubenv_records_no_fallback_keys(self) -> None:
        warning = "# GRUB Environment Block\n# WARNING: Do not edit this file by tools other than grub-editenv!!!\n"
        data = warning.encode() + b"#" * (1024 - len(warning))
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "f64122858064885ef0733e42c6a3d2d3fd642671f714db0d974b880c0f087430",
        )
        self.assertEqual(baseline_diag.grubenv_assignments(data), [])
        armed = warning.encode() + b"recordfail=1\n" + b"#" * (1024 - len(warning) - len(b"recordfail=1\n"))
        self.assertEqual(baseline_diag.grubenv_assignments(armed), ["recordfail=1"])
        logged = "Kernel command line: BOOT_IMAGE=/vmlinuz ro lsm=lockdown,capability,bpf panic=-1\n"
        self.assertEqual(
            baseline_diag.kernel_command_lines(logged),
            ["BOOT_IMAGE=/vmlinuz ro lsm=lockdown,capability,bpf panic=-1"],
        )
        long_line = "BOOT_IMAGE=/vmlinuz ro " + ("x" * 500) + " lsm=lockdown,capability,bpf panic=-1"
        self.assertEqual(
            baseline_diag.kernel_command_lines(f"Kernel command line: {long_line}\n"),
            [long_line],
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "boot/grub").mkdir(parents=True)
            (root / "boot/grub/grubenv").write_bytes(data)
            rows = baseline_diag.boot_file_manifest(root)
            self.assertEqual(rows[0]["kind"], "env")
            self.assertEqual(rows[0]["variables"], [])

    def test_lsm_rows_record_this_boot_in_both_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tmp_rows = root / "tmp-rows.json"
            lib_rows = root / "var" / "enterprise-pe-rows.json"
            original = baseline_diag.lsm_row_paths
            baseline_diag.lsm_row_paths = lambda: (tmp_rows, lib_rows)
            try:
                written = baseline_diag.write_lsm_rows(
                    {
                        "host_result": "LSM_ENABLED",
                        "cmdline": "lsm=lockdown,capability,bpf panic=-1",
                        "stock_lsm": "lockdown,capability,bpf",
                    }
                )
            finally:
                baseline_diag.lsm_row_paths = original
            self.assertEqual(written["boot_id"], baseline_diag.read_boot_id())
            for path in (tmp_rows, lib_rows):
                body = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(body["boot_id"], written["boot_id"])
                self.assertEqual(body["host_result"], "LSM_ENABLED")

    def test_same_filesystem_stub_seals_the_prefix_path(self) -> None:
        token = "lockdown,capability,landlock,yama,apparmor,ima,evm,bpf"
        stub_uuid = "6a4d7abf-5bb6-427d-a1f5-1df6cda29962"
        other = "8e2a9073-72b3-4cba-bf15-3704b810f72a"
        stub = (
            f"search.fs_uuid {stub_uuid} root\n"
            "set prefix=($root)'/grub'\n"
            "configfile $prefix/grub.cfg\n"
        )
        stock = (
            "linux /vmlinuz root=PARTUUID=10c90fd7-bb6d-4926-b2f0-5f9d77cdcf47 "
            "ro console=ttyS0,115200 panic=-1\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            efi = root / "boot/efi/EFI/ubuntu"
            efi.mkdir(parents=True)
            (efi / "grub.cfg").write_text(stub, encoding="utf-8")
            (root / "boot/grub").mkdir(parents=True)
            (root / "boot/grub/grub.cfg").write_text(stock, encoding="utf-8")
            (root / "grub").mkdir()
            (root / "grub/grub.cfg").write_text(stock, encoding="utf-8")
            sealed = baseline_diag.seal_firmware_tree(
                root,
                token,
                boot_uuid=stub_uuid,
                root_uuid=stub_uuid,
            )
            self.assertTrue(sealed["ok"], sealed)
            self.assertEqual((efi / "grub.cfg").read_text(encoding="utf-8"), stub)
            chain = sealed["bootchain"]
            self.assertEqual(chain["uuid_mount"], "same")
            self.assertEqual(chain["grub_alias"], "sealed")
            self.assertEqual(chain["boot_uuid"], stub_uuid)
            self.assertEqual(chain["root_uuid"], stub_uuid)
            alias = (root / "grub/grub.cfg").read_text(encoding="utf-8")
            self.assertIn(f"lsm={token} panic=-1", alias)
            self.assertNotIn(f"panic=-1 lsm={token}", alias)
            self.assertTrue(baseline_diag.firmware_cmdline_ok(alias.strip(), token))
            self.assertIn("grub/grub.cfg", chain["rewritten"])
            self.assertIn("boot/grub/grub.cfg", chain["rewritten"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            efi = root / "boot/efi/EFI/ubuntu"
            efi.mkdir(parents=True)
            (efi / "grub.cfg").write_text(stub, encoding="utf-8")
            (root / "boot/grub").mkdir(parents=True)
            (root / "boot/grub/grub.cfg").write_text(stock, encoding="utf-8")
            sealed = baseline_diag.seal_firmware_tree(
                root,
                token,
                boot_uuid=stub_uuid,
                root_uuid=stub_uuid,
            )
            self.assertTrue(sealed["ok"], sealed)
            self.assertEqual(sealed["bootchain"]["grub_alias"], "sealed")
            created = (root / "grub/grub.cfg").read_text(encoding="utf-8")
            self.assertIn(f"lsm={token} panic=-1", created)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            efi = root / "boot/efi/EFI/ubuntu"
            efi.mkdir(parents=True)
            (efi / "grub.cfg").write_text(stub, encoding="utf-8")
            (root / "boot/grub").mkdir(parents=True)
            (root / "boot/grub/grub.cfg").write_text(stock, encoding="utf-8")
            sealed = baseline_diag.seal_firmware_tree(
                root,
                token,
                boot_uuid=stub_uuid,
                root_uuid=other,
            )
            self.assertTrue(sealed["ok"], sealed)
            self.assertEqual(sealed["bootchain"]["uuid_mount"], "boot")
            self.assertEqual(sealed["bootchain"]["grub_alias"], "absent")
            self.assertFalse((root / "grub/grub.cfg").exists())

    def test_loader_entry_and_efi_menu_keep_panic_last(self) -> None:
        token = "lockdown,capability,landlock,yama,apparmor,ima,evm,bpf"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry_dir = root / "boot/loader/entries"
            entry_dir.mkdir(parents=True)
            (entry_dir / "ubuntu.conf").write_text(
                "title Ubuntu\noptions root=PARTUUID=10c90fd7-bb6d-4926-b2f0-5f9d77cdcf47 "
                "ro console=ttyS0,115200 panic=-1\n",
                encoding="utf-8",
            )
            sealed = baseline_diag.seal_firmware_tree(root, token)
            self.assertTrue(sealed["ok"], sealed)
            options = (entry_dir / "ubuntu.conf").read_text(encoding="utf-8").splitlines()[-1]
            self.assertTrue(options.endswith("panic=-1"), options)
            self.assertIn(f" lsm={token} panic=-1", options)
            self.assertTrue(baseline_diag.firmware_cmdline_ok(options, token))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            menu = root / "boot/efi/EFI/ubuntu"
            menu.mkdir(parents=True)
            (menu / "grub.cfg").write_text(
                "menuentry 'Ubuntu' {\n"
                "  linux /vmlinuz root=PARTUUID=10c90fd7-bb6d-4926-b2f0-5f9d77cdcf47 "
                "ro console=ttyS0,115200 panic=-1\n"
                "}\n",
                encoding="utf-8",
            )
            sealed = baseline_diag.seal_firmware_tree(root, token)
            self.assertTrue(sealed["ok"], sealed)
            self.assertEqual(sealed["bootchain"]["efi_kind"], "menu")
            self.assertIn("panic=-1", sealed["bootchain"]["stock_line"])
            self.assertNotIn("lsm=", sealed["bootchain"]["stock_line"])
            text = (menu / "grub.cfg").read_text(encoding="utf-8")
            self.assertIn(f"lsm={token} panic=-1", text)
            self.assertNotIn(f"panic=-1 lsm={token}", text)
            self.assertTrue(text.strip().endswith("}"))

    def test_lsm_after_panic_is_not_the_booted_line(self) -> None:
        token = "lockdown,capability,apparmor,bpf"
        late = (
            "linux /vmlinuz root=PARTUUID ro console=ttyS0,115200 "
            f"panic=-1 lsm={token}"
        )
        self.assertFalse(baseline_diag.firmware_cmdline_ok(late, token))
        self.assertTrue(late.endswith(f"lsm={token}"))
        placed = baseline_diag.place_lsm_before_panic(
            "linux /vmlinuz root=PARTUUID ro console=ttyS0,115200 panic=-1",
            token,
        )
        self.assertTrue(baseline_diag.firmware_cmdline_ok(placed, token))
        self.assertTrue(placed.endswith("panic=-1"))

    def test_stub_uuid_mismatch_names_the_other_filesystem(self) -> None:
        stub_uuid = "44FB-ACAE"
        mounted = "8e2a9073-72b3-4cba-bf15-3704b810f72a"
        decision = baseline_diag.stub_boot_decision(stub_uuid, mounted, target_sealed=False)
        self.assertEqual(decision, f"boot_uuid_mismatch:{stub_uuid}")
        self.assertIn(stub_uuid, decision)
        self.assertNotIn(mounted, decision)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            efi = root / "boot/efi/EFI/ubuntu"
            efi.mkdir(parents=True)
            (efi / "grub.cfg").write_text(
                f"search.fs_uuid {stub_uuid} root\n"
                "set prefix=($root)'/EFI/ubuntu/grub'\n"
                "configfile $prefix/grub.cfg\n",
                encoding="utf-8",
            )
            sealed = baseline_diag.seal_firmware_tree(
                root,
                "lockdown,capability,apparmor,bpf",
                boot_uuid=mounted,
                root_uuid=mounted,
                esp_uuid="",
            )
            self.assertFalse(sealed["ok"])
            self.assertEqual(sealed["error"], f"boot_uuid_mismatch:{stub_uuid}")
            self.assertEqual(sealed["bootchain"]["efi_kind"], "stub")
            self.assertIn("search.fs_uuid", sealed["bootchain"]["efi_head"])

    def test_parent_walk_flags_a_directory_without_execute(self) -> None:
        walk = "/ kind=dir mode=0o755 x=1\n/var kind=dir mode=0o700 x=0\n"
        self.assertTrue(baseline_diag._parent_blocked(walk))
        self.assertFalse(baseline_diag._file_unreadable("/secret kind=file mode=0o644 r=1\n"))

    def test_2d_records_the_diag_when_the_open_has_no_row(self) -> None:
        text = Path(__file__).resolve().parent.joinpath("lab-guests", "phase2_host.py").read_text(encoding="utf-8")
        body = text.split("def run_2d", 1)[1].split("def run_2e", 1)[0]
        self.assertLess(body.index("baseline_diag.collect"), body.index("control_handshake()"))
        self.assertIn("baseline_diag=diag", body)

    def test_guest_scripts_do_not_recreate_the_rows_file(self) -> None:
        for relative in (
            Path("lab-guests/enterprise-rows.sh"),
            Path(__file__).resolve().parents[1].joinpath("gcp/lab-guests/enterprise-rows.sh"),
        ):
            path = relative if relative.is_absolute() else Path(__file__).resolve().parent / relative
            text = path.read_text(encoding="utf-8")
            self.assertIn("write_replacing", text)
            self.assertNotIn("rows.write_text", text)
            self.assertIn("sticky_write.py", text)

    def test_runners_copy_the_diag_and_the_writer(self) -> None:
        steps = Path(__file__).resolve().parent.joinpath("w3_lab_steps.py").read_text(encoding="utf-8")
        deliver_dir = Path(__file__).resolve().parents[1] / "gcp"
        deliver = "\n".join(
            path.read_text(encoding="utf-8") for path in sorted(deliver_dir.glob("offline_deliver*.py"))
        )
        for name in ("baseline_diag.py", "sticky_write.py"):
            self.assertIn(name, steps)
            self.assertIn(name, deliver)

    def test_root_write_text_on_a_user_file_in_tmp_is_protected_regular(self) -> None:
        if shutil.which("sudo") is None:
            self.skipTest("sudo")
        if subprocess.run(["sudo", "-n", "true"], check=False).returncode != 0:
            self.skipTest("sudo -n")
        protected = int(Path("/proc/sys/fs/protected_regular").read_text(encoding="utf-8"))
        self.assertGreaterEqual(protected, 1)
        target = Path(f"/tmp/vantio-sticky-{os.getpid()}.json")
        target.write_text("owned-by-caller\n", encoding="utf-8")
        os.chmod(target, 0o644)
        module = str(Path(sticky_write.__file__).resolve().parent)
        code = (
            "import os, sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from pathlib import Path\n"
            "from sticky_write import write_replacing\n"
            "path = Path(sys.argv[2])\n"
            "try:\n"
            "    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)\n"
            "    os.close(fd)\n"
            "    print('creat ok')\n"
            "except OSError as exc:\n"
            "    print('creat', exc.errno)\n"
            "try:\n"
            "    fd = os.open(path, os.O_WRONLY | os.O_TRUNC)\n"
            "    os.close(fd)\n"
            "    print('trunc ok')\n"
            "except OSError as exc:\n"
            "    print('trunc', exc.errno)\n"
            "write_replacing(path, '{\"kept\":true}')\n"
            "print(path.read_text(encoding='utf-8'))\n"
        )
        try:
            ran = subprocess.run(
                ["sudo", "-n", "python3", "-c", code, module, str(target)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertIn("creat 13", ran.stdout)
            self.assertIn("trunc ok", ran.stdout)
            self.assertIn('{"kept":true}', ran.stdout)
            self.assertEqual(target.read_text(encoding="utf-8"), '{"kept":true}')
        finally:
            target.unlink(missing_ok=True)

    def test_a_refused_truncate_is_not_replaced(self) -> None:
        target = Path(f"/tmp/vantio-sticky-keep-{os.getpid()}.json")
        target.write_text("keep\n", encoding="utf-8")
        os.chmod(target, 0o000)
        try:
            with self.assertRaises(PermissionError):
                sticky_write.write_replacing(target, "replaced")
            os.chmod(target, 0o644)
            self.assertEqual(target.read_text(encoding="utf-8"), "keep\n")
        finally:
            os.chmod(target, 0o644)
            target.unlink(missing_ok=True)

    def test_diag_does_not_apt_and_strace_is_in_the_offline_debs(self) -> None:
        diag = Path(baseline_diag.__file__).read_text(encoding="utf-8")
        self.assertNotIn("apt-get", diag)
        root = Path(__file__).resolve().parents[2]
        for relative in ("scripts/aws/fetch_offline_debs.sh", "scripts/gcp/fetch_offline_debs.sh"):
            self.assertIn("strace", (root / relative).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
