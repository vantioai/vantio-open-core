#!/usr/bin/env python3
"""Host-free checks for the phase batteries. They do not launch an instance."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
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
        deliver = Path(__file__).resolve().parents[1].joinpath("gcp/offline_deliver.py").read_text(encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
