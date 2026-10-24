#!/usr/bin/env python3
"""GCP 2E, 2F, 2G phase batteries (offline_deliver_4.py).

The GCP host grades each phase from its rows body the way AWS
phase_battery_verdict does, then recomputes the result from the integers it
kept. Guest booleans only veto. These tests do not call GCP.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import importlib.util

import offline_deliver as od

ROOT = Path(__file__).resolve().parents[2]


def _load_hu():
    path = ROOT / "scripts" / "lab" / "host_evidence_hu.py"
    spec = importlib.util.spec_from_file_location("host_evidence_hu_phase", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HU = _load_hu()
HU_PASS = HU.transcript(HU.passing_facts())
sys.path.insert(0, str(ROOT / "scripts/aws/lab-guests"))
sys.path.insert(0, str(ROOT / "scripts/aws"))
import phase2_grade as grade  # noqa: E402
import w3_lab_steps as aws_steps  # noqa: E402

SEAL = "a" * 64
PID = 4242
LOADER = {"host": 3100, "ns": 7}
SOURCE = "https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images/ubuntu-2404-noble-amd64-v20261015"
UNINSTALL_OK = "UNINSTALL_VERIFIED\n"
UNINSTALL_ROW = f"UNINSTALL_VERIFIED\ndeny_attr_post_kill pid {PID} anchor 9001\n"


def body_2e(runtime: float = 4.2, denied: int = 100, revoke_errno: int = 13) -> dict:
    """What run_2e publishes, built with the guest grader."""
    body = grade.grade_performance(runtime_seconds=runtime, host_count=1, sample_count=100)
    body["denied_samples"] = denied
    body["revoke_convergence_ms"] = 812.5
    body["revoke_errno"] = revoke_errno
    body["revoke_fail_open"] = revoke_errno == 0
    return body


def swap(**overrides) -> dict:
    value = {
        "swapped": True,
        "reason": None,
        "waited_s": 1.25,
        "before_ids": {"vantio_deny_attr": 11, "vantio_deny_attr_drops": 12, "vantio_deny_overflow": 13},
        "ids": {"vantio_deny_attr": 21, "vantio_deny_attr_drops": 22, "vantio_deny_overflow": 23},
        "incoming": [],
        "incoming_before": [],
        "incoming_seen": [f"/sys/fs/bpf/{stem}_incoming_{LOADER['ns']}" for stem in grade.DENY_SWAP_STEMS],
        "loaders": [dict(LOADER)],
    }
    value.update(overrides)
    return value


def body_2f(*, net: int = 1, file_errno: int = 13, control: int = 0, attributed: bool = True, anchor: int = 0, allow: int = 0, loader_up: bool = False) -> dict:
    """What run_2f publishes on its graded path, built with the guest grader."""
    body = grade.grade_tamper(
        enrolled_errno=net,
        unenrolled_errno=control,
        loader_up=loader_up,
        file_errno=file_errno,
        file_attributed=attributed,
        enrolled_block_anchor=anchor,
    )
    body["enrolled_after"] = {"enrolled": True, "file_errno": file_errno, "net_errno": net, "pid": PID, "uid": 65534}
    body["unenrolled_after"] = {"enrolled": False, "net_errno": control, "role": "control"}
    body["control_errno"] = control
    body["file_attributed"] = attributed
    body["standin_after_sigkill"] = {}
    body["ndjson_denied_pids"] = []
    body["map_swap"] = swap()
    grade.apply_allowlisted_private(body, allow)
    body["kill_timing"] = grade.KILL_TIMING_AFTER_MAP_SWAP
    body["claim_scope"] = grade.CLAIM_SCOPE_2F
    return grade.require_tamper_claim(body)


def body_2g(*, enrolled: int = 13, unenrolled: int = 0, btf: bool = True, lsm: str = "lockdown,capability,landlock,yama,apparmor,bpf", seal: str | None = None) -> dict:
    facts = {
        "distro": "Ubuntu 24.04.3 LTS",
        "kernel": "6.14.0-1017-gcp",
        "btf": btf,
        "lsm": lsm,
        "lockdown": "[none] integrity confidentiality",
        "image_name": "",
        "cgroup_v2": True,
        "bpffs": True,
    }
    body = grade.grade_distro(
        {
            "live_probe": True,
            "distro": facts["distro"],
            "kernel": facts["kernel"],
            "btf": btf,
            "lsm": lsm,
            "seal": grade.WORKING_SEAL if seal is None else seal,
            "enrolled_errno": enrolled,
            "unenrolled_errno": unenrolled,
            "removed": True,
            "descendant_pass": False,
            "docker_child_pass": False,
            "ami": od.PHASE_IMAGE,
        }
    )
    body["kernel_facts"] = facts
    body["enrolled"] = {"file_errno": enrolled, "net_errno": 0, "pid": PID}
    body["unenrolled"] = {"file_errno": unenrolled, "net_errno": 0, "pid": PID + 1}
    body["attributed"] = enrolled == 13
    return body


def row(mode: str, body: dict, *, uninstall: str | None = None, rc: int = 0, source: str = SOURCE, lane: bool = True, guest_rc: int = 0) -> dict:
    if uninstall is None:
        uninstall = UNINSTALL_ROW if mode == "2f-tamper" else UNINSTALL_OK
    return od.phase_row(
        mode,
        body,
        guest_rc=guest_rc,
        uninstall_text=uninstall,
        uninstall_rc=rc,
        boot_source=source,
        seal_lane=lane,
    )


def aws_pass(mode: str, body: dict) -> bool:
    return aws_steps.phase_battery_verdict(mode, body)["pass"] is True


class ParityTest(unittest.TestCase):
    """The host copies of the guest constants and checks match phase2_grade."""

    def test_constants_match_the_guest_grader(self) -> None:
        self.assertEqual(od.PHASE_MAX_PERF_SECONDS, grade.MAX_PERF_SECONDS)
        self.assertEqual(od.PHASE_CLAIM_SCOPE_2F, grade.CLAIM_SCOPE_2F)
        self.assertEqual(od.PHASE_KILL_AFTER_MAP_SWAP, grade.KILL_TIMING_AFTER_MAP_SWAP)
        self.assertEqual(od.PHASE_KILL_NOT_KILLED, grade.KILL_TIMING_NOT_KILLED)
        self.assertEqual(od.PHASE_DENY_SWAP_STEMS, grade.DENY_SWAP_STEMS)
        self.assertEqual(od.CLAIM_CAP, grade.CLAIM_CEILING)
        self.assertEqual(set(od.PHASE_MODES), {"2e-performance", "2f-tamper", "2g-distro"})
        self.assertTrue(set(od.PHASE_MODES) <= set(aws_steps.PHASE_BATTERY_PASS))

    def test_egress_word_matches(self) -> None:
        for errno in (None, True, False, 0, 1, 2, 13, 110, 111, 113, 255):
            self.assertEqual(od.phase_egress_word(errno), grade.egress_word(errno) if not isinstance(errno, bool) else "no_response", errno)

    def test_map_swap_matches(self) -> None:
        base = swap()
        cases = [
            (base["before_ids"], [], base["ids"], []),
            (base["before_ids"], [], base["before_ids"], []),
            ({}, [], base["ids"], []),
            (base["before_ids"], [], {**base["ids"], "vantio_deny_overflow": 0}, []),
            (base["before_ids"], [], base["ids"], ["/sys/fs/bpf/vantio_deny_attr_incoming_7"]),
            (base["before_ids"], ["/sys/fs/bpf/vantio_deny_attr_incoming_7"], base["ids"], ["/sys/fs/bpf/vantio_deny_attr_incoming_7"]),
            (None, [], base["ids"], []),
            (base["before_ids"], None, base["ids"], []),
            (base["before_ids"], [], {**base["ids"], "vantio_deny_attr": True}, []),
        ]
        for case in cases:
            self.assertEqual(od.phase_map_swapped(*case), grade.deny_map_swapped(*case), case)

    def test_swap_owner_matches(self) -> None:
        seen = swap()["incoming_seen"]
        cases = [
            (seen, [LOADER]),
            (seen, [{"host": LOADER["host"], "ns": LOADER["host"]}]),
            (seen, [LOADER, {"host": 9, "ns": 9}]),
            ([], [LOADER]),
            (seen + ["/sys/fs/bpf/vantio_deny_attr_incoming_99"], [LOADER]),
            (seen, []),
            (seen, [{"host": True, "ns": 7}]),
            (["/sys/fs/bpf/vantio_deny_attr_incoming_0"], [{"host": 0, "ns": 0}]),
        ]
        for case in cases:
            self.assertEqual(od.phase_swap_owner(*case), grade.swap_owner_matches(*case), case)


class Phase2ETest(unittest.TestCase):
    def test_guest_pass_is_a_host_pass(self) -> None:
        kept = row("2e-performance", body_2e())
        self.assertEqual((kept["pass"], kept["verdict_reason"]), (True, "battery_pass"))
        self.assertEqual(kept["runtime_seconds"], 4.2)
        self.assertEqual(kept["sample_count"], 100)

    def test_rows_not_exit_code(self) -> None:
        self.assertTrue(row("2e-performance", body_2e(), guest_rc=2)["pass"])
        failed = grade.grade_performance(runtime_seconds=901, host_count=1, sample_count=100)
        kept = row("2e-performance", failed, guest_rc=0)
        self.assertEqual((kept["pass"], kept["verdict_reason"]), (False, "battery_fail"))

    def test_forged_pass_is_recomputed(self) -> None:
        for change, reason in (
            ({"runtime_seconds": 901}, "host_runtime_bound"),
            ({"runtime_seconds": -1}, "host_runtime_missing"),
            ({"runtime_seconds": "4"}, "host_runtime_missing"),
            ({"sample_count": 50}, "host_sample_count"),
            ({"host_count": 2}, "host_count"),
            ({"denied_samples": 99}, "host_denied_samples"),
            ({"revoke_errno": 0}, "host_revoke_not_converged"),
            ({"revoke_fail_open": True}, "guest_flag_mismatch"),
        ):
            body = body_2e()
            body.update(change)
            body["host_result"] = "PASS"
            kept = row("2e-performance", body)
            self.assertEqual((kept["pass"], kept["verdict_reason"]), (False, reason), change)

    def test_aws_reasons(self) -> None:
        for change, reason in (
            ({"host_result": "NOT_GRADED"}, "battery_not_graded"),
            ({"host_result": "HOLD"}, "battery_hold"),
            ({"host_result": "FAIL"}, "battery_fail"),
            ({"host_result": "MAYBE"}, "battery_result_unknown"),
            ({"harness_error": "boom"}, "battery_harness_error"),
            ({"battery": "2f-tamper"}, "battery_mismatch"),
        ):
            body = body_2e()
            body.update(change)
            self.assertEqual(row("2e-performance", body)["verdict_reason"], reason, change)

    def test_uninstall_has_to_verify(self) -> None:
        for text in (
            "UNINSTALL_NOT_VERIFIED rc=1\n",
            "",
            "UNINSTALL_VERIFIED\nUNINSTALL_RESIDUAL bpffs\n/sys/fs/bpf/vantio_deny_attr\n",
            "UNINSTALL_VERIFIED\nUNINSTALL_NOT_VERIFIED rc=1\n",
            "UNINSTALL_RESIDUAL bpftool missing\n",
            "loader said UNINSTALL_VERIFIED\n",
            "UNINSTALL_VERIFIED \n",
        ):
            kept = row("2e-performance", body_2e(), uninstall=text, rc=1)
            self.assertEqual((kept["pass"], kept["verdict_reason"]), (False, "uninstall_not_verified"), text)
            self.assertFalse(kept["uninstall_verified"], text)

    def test_clean_host_is_the_lines_not_the_exit_code(self) -> None:
        # enterprise-rows.sh exits 1 when VANTIO_REQUIRE_POST_KILL=yes finds no
        # post-kill row, after it printed UNINSTALL_VERIFIED. The host is clean.
        kept = row("2e-performance", body_2e(), uninstall="UNINSTALL_VERIFIED\npost_kill_row_missing\n", rc=1)
        self.assertEqual((kept["pass"], kept["verdict_reason"]), (True, "battery_pass"))
        self.assertTrue(kept["uninstall_verified"])
        self.assertEqual(kept["uninstall_rc"], 1)

    def test_host_clean_is_an_exact_line(self) -> None:
        self.assertTrue(od.phase_host_clean("noise\nUNINSTALL_VERIFIED\nmore\n", 0))
        self.assertFalse(od.phase_host_clean("noise UNINSTALL_VERIFIED\n", 0))
        self.assertFalse(od.phase_host_clean("UNINSTALL_VERIFIED_LATER\n", 0))
        self.assertFalse(od.phase_host_clean("XUNINSTALL_VERIFIED\n", 0))
        self.assertFalse(od.phase_host_clean("UNINSTALL_VERIFIED\nUNINSTALL_RESIDUAL bpffs\n", 0))
        self.assertFalse(od.phase_host_clean(None, 0))

    def test_host_clean_needs_the_script_to_have_exited(self) -> None:
        # 0, or 1 for a missing post-kill row. 255 is ssh, a timeout, or a
        # dropped tunnel: the residue check may not have run.
        self.assertTrue(od.phase_host_clean("UNINSTALL_VERIFIED\n", 0))
        self.assertTrue(od.phase_host_clean("UNINSTALL_VERIFIED\npost_kill_row_missing\n", 1))
        for rc in (255, -1, 2, 6, 124, None, True, False, "0"):
            self.assertFalse(od.phase_host_clean("UNINSTALL_VERIFIED\n", rc), rc)
        self.assertFalse(od.phase_host_clean("UNINSTALL_VERIFIED\n\noperation timed out", 255))
        kept = row("2e-performance", body_2e(), uninstall="UNINSTALL_VERIFIED\n\noperation timed out", rc=255)
        self.assertEqual((kept["pass"], kept["verdict_reason"]), (False, "uninstall_not_verified"))
        self.assertFalse(kept["uninstall_verified"])
        self.assertEqual(od.PHASE_UNINSTALL_DIRTY, ("UNINSTALL_RESIDUAL", "UNINSTALL_NOT_VERIFIED"))
        script = (ROOT / "scripts/gcp/lab-guests/enterprise-rows.sh").read_text(encoding="utf-8")
        self.assertIn("grep -qx 'UNINSTALL_VERIFIED'", script)
        for marker in od.PHASE_UNINSTALL_DIRTY:
            self.assertIn(f'echo "{marker} ', script)

    def test_missing_revoke_fail_open_fails(self) -> None:
        body = body_2e()
        body.pop("revoke_fail_open")
        body["host_result"] = "PASS"
        kept = row("2e-performance", body)
        self.assertNotIn("revoke_fail_open", kept)
        self.assertEqual((kept["pass"], kept["verdict_reason"]), (False, "guest_flag_mismatch"))
        body["revoke_fail_open"] = None
        self.assertEqual(row("2e-performance", body)["verdict_reason"], "guest_flag_mismatch")


class Phase2FTest(unittest.TestCase):
    def test_guest_pass_is_a_host_pass(self) -> None:
        kept = row("2f-tamper", body_2f())
        self.assertEqual((kept["pass"], kept["verdict_reason"]), (True, "battery_pass"))
        self.assertEqual(kept["kill_timing"], "after_map_swap")
        self.assertEqual(kept["claim_scope"], grade.CLAIM_SCOPE_2F)
        self.assertEqual(kept["post_kill_pid"], PID)

    def test_timeout_with_egress_row_is_a_block(self) -> None:
        self.assertTrue(row("2f-tamper", body_2f(net=110, anchor=77))["pass"])

    def test_claim_fields(self) -> None:
        for key, value in (("kill_timing", None), ("claim_scope", None), ("claim_scope", "kill after anything"), ("kill_timing", "not_killed")):
            body = body_2f()
            if value is None:
                body.pop(key)
            else:
                body[key] = value
            self.assertEqual(row("2f-tamper", body)["verdict_reason"], "claim_fields_missing", (key, value))
            stripped = copy.deepcopy(body)
            stripped.update({"host_result": "PASS"})
            self.assertFalse(row("2f-tamper", grade.require_tamper_claim(stripped))["pass"])

    def test_guest_claim_check_withholds(self) -> None:
        body = body_2f()
        body.pop("claim_scope")
        body["host_result"] = "PASS"
        withheld = grade.require_tamper_claim(body)
        self.assertEqual(row("2f-tamper", withheld)["verdict_reason"], "battery_not_graded")

    def test_map_swap_timeout_is_not_graded(self) -> None:
        refused = grade.ungraded_egress("2f-tamper", grade.MAP_SWAP_TIMEOUT)
        refused["map_swap"] = swap(swapped=False, reason=grade.MAP_SWAP_TIMEOUT)
        refused["kill_timing"] = grade.KILL_TIMING_NOT_KILLED
        kept = row("2f-tamper", refused)
        self.assertEqual((kept["pass"], kept["verdict_reason"]), (False, "battery_not_graded"))
        self.assertEqual(kept["kill_timing"], "not_killed")

    def test_forged_pass_is_recomputed(self) -> None:
        def forged(**changes):
            body = body_2f()
            for key, value in changes.items():
                if key == "enrolled_after":
                    body["enrolled_after"].update(value)
                else:
                    body[key] = value
            body["host_result"] = "PASS"
            return body

        cases = [
            (forged(map_swap=swap(ids=swap()["before_ids"])), "host_map_swap_not_seen"),
            (forged(map_swap=swap(incoming=["/sys/fs/bpf/vantio_deny_attr_incoming_7"])), "host_map_swap_not_seen"),
            (forged(map_swap=swap(loaders=[LOADER, {"host": 1, "ns": 1}])), "host_swap_owner_mismatch"),
            (forged(map_swap=swap(incoming_seen=["/sys/fs/bpf/vantio_deny_attr_incoming_99"])), "host_swap_owner_mismatch"),
            (forged(map_swap=swap(swapped=False)), "guest_flag_mismatch"),
            (forged(map_swap={}), "host_map_swap_not_seen"),
            (forged(control_errno=110), "host_control_not_allowed"),
            (forged(enrolled_after={"net_errno": 0}), "host_enrolled_egress_not_denied"),
            (forged(enrolled_after={"net_errno": 110}), "host_enrolled_egress_not_denied"),
            (forged(enrolled_after={"file_errno": 0}), "host_file_not_denied"),
            (forged(enrolled_after={"file_errno": 2}), "host_file_not_denied"),
            (forged(allowlisted_private_errno=13), "host_allowlisted_private_blocked"),
            (forged(enrolled_after={"pid": None}), "host_probe_pid_missing"),
            (forged(loader_up=True), "guest_flag_mismatch"),
            (forged(file_attributed=False), "guest_flag_mismatch"),
        ]
        for body, reason in cases:
            uninstall = UNINSTALL_ROW
            kept = row("2f-tamper", body, uninstall=uninstall)
            self.assertEqual((kept["pass"], kept["verdict_reason"]), (False, reason), reason)

    def test_post_kill_row_names_the_probe(self) -> None:
        for text in (
            UNINSTALL_OK,
            f"UNINSTALL_VERIFIED\ndeny_attr_post_kill pid {PID + 1} anchor 9001\n",
            f"UNINSTALL_VERIFIED\ndeny_attr_post_kill pid {PID} anchor 0\n",
            f"UNINSTALL_VERIFIED\nnoise deny_attr_post_kill pid {PID} anchor 5\n",
        ):
            kept = row("2f-tamper", body_2f(), uninstall=text)
            self.assertEqual((kept["pass"], kept["verdict_reason"]), (False, "host_post_kill_row_missing"), text)

    def test_guest_results_stand(self) -> None:
        self.assertEqual(row("2f-tamper", body_2f(net=0))["verdict_reason"], "battery_fail")
        self.assertEqual(row("2f-tamper", body_2f(loader_up=True))["verdict_reason"], "battery_hold")
        self.assertEqual(row("2f-tamper", body_2f(allow=13))["verdict_reason"], "battery_fail")
        self.assertEqual(row("2f-tamper", body_2f(file_errno=13, attributed=False))["verdict_reason"], "battery_fail")


class Phase2GTest(unittest.TestCase):
    def test_guest_pass_is_a_host_pass(self) -> None:
        kept = row("2g-distro", body_2g())
        self.assertEqual((kept["pass"], kept["verdict_reason"]), (True, "battery_pass"))
        self.assertEqual(kept["image"], "ubuntu-os-cloud/ubuntu-2404-lts-amd64")
        self.assertEqual(kept["boot_image_name"], "ubuntu-2404-noble-amd64-v20261015")
        self.assertEqual(kept["distro"], "Ubuntu 24.04.3 LTS")

    def test_image_has_to_be_the_allowed_one(self) -> None:
        for source in (
            "",
            "https://www.googleapis.com/compute/v1/projects/debian-cloud/global/images/debian-12-bookworm-v20261010",
            "https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images/ubuntu-2204-jammy-v20261010",
            "https://www.googleapis.com/compute/v1/projects/rocky-linux-cloud/global/images/rocky-linux-9-v20261010",
            "projects/evil/global/images/ubuntu-2404-noble-amd64",
        ):
            kept = row("2g-distro", body_2g(), source=source)
            self.assertEqual((kept["pass"], kept["verdict_reason"]), (False, "host_image_not_allowed"), source)

    def test_seal_has_to_be_the_lane_seal(self) -> None:
        self.assertEqual(row("2g-distro", body_2g(), lane=False)["verdict_reason"], "host_seal_not_lane")
        self.assertEqual(row("2g-distro", body_2g(seal="b" * 64))["verdict_reason"], "battery_fail")

    def test_forged_pass_is_recomputed(self) -> None:
        def forged(**changes):
            body = body_2g()
            for key, value in changes.items():
                if key in ("enrolled", "unenrolled"):
                    body[key].update(value)
                elif key in ("lsm", "btf", "distro", "kernel"):
                    body["kernel_facts"][key] = value
                else:
                    body[key] = value
            body["host_result"] = "PASS"
            return body

        for body, reason in (
            (forged(lsm="lockdown,capability,apparmor"), "host_bpf_lsm_missing"),
            (forged(lsm="lockdown,capability,apparmor,bpffoo"), "host_bpf_lsm_missing"),
            (forged(lsm=""), "host_missing_fields"),
            (forged(distro=""), "host_missing_fields"),
            (forged(enrolled={"file_errno": 0}), "host_enrolled_not_denied"),
            (forged(enrolled={"pid": 0}), "host_probe_pid_missing"),
            (forged(unenrolled={"file_errno": 13}), "host_unenrolled_not_allowed"),
            (forged(btf=False), "guest_flag_mismatch"),
            (forged(result="NOT_PROVED"), "guest_flag_mismatch"),
        ):
            kept = row("2g-distro", body)
            self.assertEqual((kept["pass"], kept["verdict_reason"]), (False, reason), reason)

    def test_guest_results_stand(self) -> None:
        self.assertEqual(row("2g-distro", body_2g(enrolled=0))["verdict_reason"], "battery_fail")
        # grade_distro counts btf False as a missing field.
        self.assertEqual(row("2g-distro", body_2g(btf=False))["verdict_reason"], "battery_hold")


class NoWeakerThanAwsTest(unittest.TestCase):
    """A GCP pass is never a body AWS phase_battery_verdict would refuse."""

    def test_gcp_pass_implies_aws_pass(self) -> None:
        bodies = {
            "2e-performance": [body_2e(), body_2e(runtime=901), body_2e(denied=1), grade.ungraded_egress("2e-performance", "x")],
            "2f-tamper": [
                body_2f(),
                body_2f(net=0),
                body_2f(net=110, anchor=5),
                body_2f(net=110),
                body_2f(control=110),
                body_2f(allow=13),
                body_2f(loader_up=True),
                body_2f(file_errno=0),
            ],
            "2g-distro": [body_2g(), body_2g(enrolled=0), body_2g(unenrolled=13), body_2g(btf=False), body_2g(seal="c" * 64)],
        }
        seen_pass = 0
        for mode, items in bodies.items():
            for body in items:
                for mutate in (None, "drop_scope", "harness", "battery"):
                    case = copy.deepcopy(body)
                    if mutate == "drop_scope":
                        case.pop("claim_scope", None)
                    elif mutate == "harness":
                        case["harness_error"] = "x"
                    elif mutate == "battery":
                        case["battery"] = "2c-upgrade-rollback"
                    if row(mode, case)["pass"]:
                        seen_pass += 1
                        self.assertTrue(aws_pass(mode, case), (mode, mutate))
        self.assertGreaterEqual(seen_pass, 4)

    def test_verdict_line_matches_aws_format(self) -> None:
        for mode, body in (("2e-performance", body_2e()), ("2f-tamper", body_2f()), ("2g-distro", body_2g(enrolled=0))):
            kept = row(mode, body)
            aws = aws_steps.phase_battery_verdict(mode, body)
            with contextlib.redirect_stdout(io.StringIO()), mock.patch.dict("os.environ", {"GITHUB_STEP_SUMMARY": ""}):
                aws_line = aws_steps.report_battery_verdict(aws)
            # GCP 2G names its one-image scope after the AWS fields.
            extra = " distro_scope=ubuntu-2404-only" if mode == "2g-distro" else ""
            self.assertEqual(od.phase_verdict_line(kept), aws_line + extra, mode)

    def test_2g_line_and_summary_name_the_distro_scope(self) -> None:
        self.assertEqual(od.PHASE_DISTRO_SCOPE, "ubuntu-2404-only")
        self.assertEqual(od.ENUMS["distro_scope"], frozenset({od.PHASE_DISTRO_SCOPE}))
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "summary.md"
            with contextlib.redirect_stdout(io.StringIO()), mock.patch.dict("os.environ", {"GITHUB_STEP_SUMMARY": str(summary)}):
                line = od.report_phase_verdict(row("2g-distro", body_2g()))
                od.report_phase_verdict(row("2e-performance", body_2e()))
            text = summary.read_text(encoding="utf-8").splitlines()
        self.assertTrue(line.endswith(" distro_scope=ubuntu-2404-only"), line)
        self.assertEqual(text[0], line)
        self.assertNotIn("distro_scope", text[1])


class SanitizerTest(unittest.TestCase):
    def test_forged_pass_and_unknown_keys_are_dropped(self) -> None:
        kept = row("2e-performance", body_2e(denied=3))
        forged = dict(kept, **{"pass": True, "verdict_reason": "battery_pass", "secret": "ghp_x", "hostname": "h"})
        cleaned = od.allow_phase_row(forged)
        self.assertEqual((cleaned["pass"], cleaned["verdict_reason"]), (False, "host_denied_samples"))
        self.assertNotIn("secret", cleaned)
        self.assertNotIn("hostname", cleaned)

    def test_guest_strings_are_typed(self) -> None:
        body = body_2g()
        body["kernel_facts"]["distro"] = "Ubuntu\nghp_secret"
        body["kernel_facts"]["kernel"] = "6.8 $(id)"
        kept = row("2g-distro", body)
        self.assertNotIn("distro", kept)
        self.assertNotIn("kernel", kept)
        self.assertFalse(kept["pass"])
        body = body_2f()
        body["map_swap"]["incoming_seen"] = ["/etc/shadow"]
        self.assertEqual(row("2f-tamper", body)["verdict_reason"], "host_swap_owner_mismatch")

    def test_allow_record_recomputes_phases_pass(self) -> None:
        rows = [row("2e-performance", body_2e()), row("2f-tamper", body_2f()), row("2g-distro", body_2g())]
        kept = od.allow_record({"phases": rows, "phases_pass": False, "distro_excluded": list(od.DISTRO_EXCLUDED) + [{"distro": "x", "reason": "y"}]})
        self.assertTrue(kept["phases_pass"])
        self.assertEqual(kept["distro_excluded"], [dict(item) for item in od.DISTRO_EXCLUDED])
        rows[1] = dict(rows[1], enrolled_file_errno=0, **{"pass": True})
        self.assertFalse(od.allow_record({"phases": rows, "phases_pass": True})["phases_pass"])

    def test_allow_record_keeps_three_phases_at_most(self) -> None:
        rows = [row("2e-performance", body_2e()), row("2f-tamper", body_2f()), row("2g-distro", body_2g())]
        kept = od.allow_record({"phases": rows + [rows[2]]})
        self.assertEqual(len(kept["phases"]), 3)
        self.assertTrue(kept["phases_pass"])

    def test_unknown_host_result_is_not_kept(self) -> None:
        body = body_2e()
        body["host_result"] = "MAYBE"
        kept = row("2e-performance", body)
        self.assertEqual(kept["host_result"], "")
        self.assertIn(" host_result=None ", od.phase_verdict_line(kept))

    def test_phases_pass_needs_all_three_in_order(self) -> None:
        rows = [row("2e-performance", body_2e()), row("2f-tamper", body_2f()), row("2g-distro", body_2g())]
        self.assertTrue(od.phases_pass(rows))
        self.assertFalse(od.phases_pass(rows[:2]))
        self.assertFalse(od.phases_pass([rows[1], rows[0], rows[2]]))
        self.assertFalse(od.phases_pass([rows[0], rows[0], rows[2]]))
        self.assertFalse(od.phases_pass(None))

    def test_excluded_distros_are_named(self) -> None:
        names = {item["distro"] for item in od.DISTRO_EXCLUDED}
        self.assertEqual(names, {"debian-12", "ubuntu-2204", "rocky-9", "amazon-linux-2023", "rhel-sles"})
        self.assertEqual(od.PHASE_IMAGE, f"{od.IMAGE_PROJECT}/{od.IMAGE_FAMILY}")
        self.assertEqual(od.PHASE_IMAGE, "ubuntu-os-cloud/ubuntu-2404-lts-amd64")


class BudgetTest(unittest.TestCase):
    T = 1_800_000_000

    def test_reserve_covers_the_worst_phase(self) -> None:
        # Two PHASE_CASE_SSH_TIMEOUT calls around the sshd wait (INFRA_RETRY),
        # the last probe, then the pull, describe, and uninstall timeouts.
        self.assertEqual(od.PHASE_CASE_SSH_TIMEOUT, 900)
        self.assertLess(od.PHASE_CASE_SSH_TIMEOUT, od.CASE_SSH_TIMEOUT)
        self.assertEqual(
            od.PHASE_RESERVE_S,
            2 * od.PHASE_CASE_SSH_TIMEOUT
            + od.SSHD_WAIT_SECONDS
            + od.PROBE_SSH_TIMEOUT
            + od.PHASE_PULL_TIMEOUT_S
            + od.PHASE_DESCRIBE_TIMEOUT_S
            + od.PHASE_UNINSTALL_TIMEOUT_S,
        )
        self.assertEqual(od.PHASE_RESERVE_S, 2600)
        self.assertEqual(od.PHASE_RETRY_NEED_S, od.PHASE_RESERVE_S - od.PHASE_CASE_SSH_TIMEOUT)
        self.assertEqual(od.PHASE_RETRY_NEED_S, 1700)

    def test_run_six_timing_fits_one_hundred_minutes(self) -> None:
        deadline = od.phase_deadline(self.T, self.T + 19, "100")
        self.assertEqual(deadline, self.T + 100 * 60 - od.PHASE_END_MARGIN_S)
        self.assertLess(deadline, self.T + 110 * 60)
        # The last start with a full reserve: 51 min 40 s after create.
        self.assertTrue(od.phase_has_time(deadline, self.T + 3100))
        self.assertFalse(od.phase_has_time(deadline, self.T + 3101))
        # Run 6 finished 2C 26 minutes after create. At ten minutes a phase
        # (2C took five) all three start with a full reserve left.
        start = self.T + 26 * 60
        for index in range(3):
            self.assertTrue(od.phase_has_time(deadline, start + index * 600), index)
        # At thirteen minutes a phase 2G is skipped.
        self.assertFalse(od.phase_has_time(deadline, start + 2 * 780))
        # Worst case every phase hits every timeout: one starts, and nothing
        # runs past the guest's power-off.
        started = [index for index in range(3) if od.phase_has_time(deadline, start + index * od.PHASE_RESERVE_S)]
        self.assertEqual(started, [0])
        self.assertLessEqual(start + od.PHASE_RESERVE_S, deadline)

    def test_one_hundred_five_minutes_fits_the_job_limit(self) -> None:
        # Dispatch with stop_after_minutes=105: the guest powers off at the
        # same point the job cap allows, inside the 110-minute job.
        deadline = od.phase_deadline(self.T, self.T + 19, "105")
        self.assertEqual(deadline, self.T + 105 * 60 - od.PHASE_END_MARGIN_S)
        self.assertEqual(deadline, od.phase_deadline(self.T, self.T + 19, "120"))
        self.assertLess(deadline + od.PHASE_END_MARGIN_S, self.T + 110 * 60)
        # The last start: 56 min 40 s after create.
        self.assertTrue(od.phase_has_time(deadline, self.T + 3400))
        self.assertFalse(od.phase_has_time(deadline, self.T + 3401))
        start = self.T + 26 * 60
        self.assertTrue(od.phase_has_time(deadline, start + 2 * 900))

    def test_short_budget_stops_phases(self) -> None:
        deadline = od.phase_deadline(self.T, self.T, "80")
        self.assertTrue(od.phase_has_time(deadline, self.T + 30 * 60))
        self.assertFalse(od.phase_has_time(deadline, self.T + 32 * 60))

    def test_job_limit_caps_the_guest_budget(self) -> None:
        self.assertEqual(od.phase_deadline(self.T, self.T, "120"), self.T + od.PHASE_JOB_LIMIT_AFTER_CREATE_S - od.PHASE_END_MARGIN_S)

    def test_bad_minutes_is_no_budget(self) -> None:
        for minutes in ("", "0", "121", "abc", None):
            self.assertEqual(od.phase_deadline(self.T, self.T, minutes), 0)
            self.assertFalse(od.phase_has_time(0, self.T))

    def test_missing_create_time_uses_run_start(self) -> None:
        self.assertEqual(od.phase_deadline(None, self.T, "100"), self.T + 6000 - od.PHASE_END_MARGIN_S)
        self.assertEqual(od.phase_deadline(self.T + 99, self.T, "100"), self.T + 6000 - od.PHASE_END_MARGIN_S)


def _done(stdout: str = "", rc: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], rc, stdout=stdout, stderr="")


class RunnerTest(unittest.TestCase):
    T = 1_800_000_000

    def _run(
        self,
        bodies: dict,
        *,
        ready: bool = True,
        uninstall: dict | None = None,
        now=None,
        minutes: str = "100",
        lane_seal: str = SEAL,
        timeouts: list | None = None,
    ):
        calls: list[str] = []
        pulled: list[str] = []
        current: dict = {}
        timeouts = timeouts if timeouts is not None else []

        def ssh_case(_p, _n, command, deadline=None, now=None):
            calls.append(command)
            mode = command.split()[-1]
            current["mode"] = mode
            current["deadline"] = deadline
            return _done("PY_RC=0\n"), False

        def pull(_p, _n, timeout_s=None):
            timeouts.append(("pull", timeout_s))
            mode = current["mode"]
            pulled.append(mode)
            body = bodies.get(mode)
            if isinstance(body, str):
                raise SystemExit(body)
            return copy.deepcopy(body)

        def ssh(_p, _n, command, timeout_s=None):
            # Mirrors enterprise-rows.sh authorized_uninstall: exit 1 unless the
            # exact UNINSTALL_VERIFIED line is there with no residual, and with
            # VANTIO_REQUIRE_POST_KILL=yes exit 1 when no post-kill row was
            # found, even after UNINSTALL_VERIFIED. With =no it prints no row.
            calls.append(command)
            timeouts.append(("uninstall", timeout_s))
            require = "VANTIO_REQUIRE_POST_KILL=yes" in command
            text = (uninstall or {}).get(current["mode"])
            if text is None:
                text = UNINSTALL_ROW if current["mode"] == "2f-tamper" else UNINSTALL_OK
            lines = text.splitlines()
            if not require:
                lines = [line for line in lines if not line.startswith("deny_attr_post_kill ")]
            clean = "UNINSTALL_VERIFIED" in lines and not any(
                line.startswith(("UNINSTALL_RESIDUAL", "UNINSTALL_NOT_VERIFIED")) for line in lines
            )
            has_row = any(line.startswith("deny_attr_post_kill pid ") for line in lines)
            if clean and require and not has_row:
                lines.append("post_kill_row_missing")
            rc = 0 if clean and (has_row or not require) else 1
            return _done("\n".join(lines) + "\n", rc)

        stubs = {
            "_phase_ssh_case": mock.Mock(side_effect=ssh_case),
            "_pull_guest_json": mock.Mock(side_effect=pull),
            "_ssh": mock.Mock(side_effect=ssh),
            "_creation_epoch": mock.Mock(return_value=self.T),
            "_boot_source": mock.Mock(return_value=SOURCE),
            "_lane_seal": mock.Mock(return_value=lane_seal),
        }
        out = io.StringIO()
        with mock.patch.multiple(od, **stubs), contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rows = od.run_phase_batteries(
                "vantio-lab-oct08",
                "vantio-gcp-lab-1",
                SEAL,
                {"STOP_AFTER_MINUTES": minutes},
                ready=ready,
                started_epoch=self.T + 20,
                now=now if callable(now) else (lambda: now if now is not None else self.T + 26 * 60),
            )
        return rows, calls, pulled, out.getvalue()

    def _bodies(self) -> dict:
        return {"2e-performance": body_2e(), "2f-tamper": body_2f(), "2g-distro": body_2g()}

    def test_all_three_pass_with_their_own_uninstall(self) -> None:
        rows, calls, pulled, out = self._run(self._bodies())
        self.assertEqual([item["battery"] for item in rows], list(od.PHASE_MODES))
        self.assertTrue(od.phases_pass(rows), rows)
        self.assertEqual(pulled, list(od.PHASE_MODES))
        self.assertEqual(len(calls), 6)
        self.assertEqual(calls[0], f"bash {od.GUEST_DIR}/enterprise-rows.sh {SEAL} 2e-performance")
        self.assertIn("VANTIO_REQUIRE_POST_KILL=no VANTIO_PROBE_PID=0", calls[1])
        self.assertTrue(calls[1].endswith(f"{SEAL} uninstall"))
        self.assertEqual(calls[2], f"bash {od.GUEST_DIR}/enterprise-rows.sh {SEAL} 2f-tamper")
        self.assertIn(f"VANTIO_REQUIRE_POST_KILL=yes VANTIO_PROBE_PID={PID}", calls[3])
        self.assertEqual(calls[4], f"env VANTIO_IMAGE_ID=ubuntu-os-cloud/ubuntu-2404-lts-amd64 bash {od.GUEST_DIR}/enterprise-rows.sh {SEAL} 2g-distro")
        self.assertIn("VANTIO_REQUIRE_POST_KILL=no", calls[5])
        lines = [line for line in out.splitlines() if line.startswith("BATTERY_VERDICT")]
        self.assertEqual(len(lines), 3)
        self.assertIn('kill_timing=after_map_swap claim_scope="kill after deny-attr map swap; ready-to-swap gap not covered (VAN-45)"', lines[1])

    def test_dirty_host_stops_later_phases(self) -> None:
        rows, calls, _, _ = self._run(self._bodies(), uninstall={"2e-performance": "UNINSTALL_NOT_VERIFIED rc=1\n"})
        self.assertEqual(rows[0]["verdict_reason"], "uninstall_not_verified")
        self.assertEqual([item.get("not_run_reason") for item in rows[1:]], ["previous_uninstall"] * 2)
        self.assertEqual(len(calls), 2)
        self.assertFalse(od.phases_pass(rows))

    def test_unverified_final_uninstall_runs_nothing(self) -> None:
        rows, calls, _, _ = self._run(self._bodies(), ready=False)
        self.assertEqual(calls, [])
        self.assertEqual({item["host_result"] for item in rows}, {"NOT_RUN"})
        self.assertEqual({item["verdict_reason"] for item in rows}, {"previous_uninstall"})

    def test_time_budget(self) -> None:
        rows, calls, _, _ = self._run(self._bodies(), now=self.T + 80 * 60)
        self.assertEqual(calls, [])
        self.assertEqual({item["verdict_reason"] for item in rows}, {"time_budget"})
        # stop_after_minutes=100: 2G would start 52 minutes after create,
        # past 51 min 40 s. 2E and 2F run, 2G does not.
        clock = iter([self.T + 26 * 60, self.T + 39 * 60, self.T + 52 * 60])
        rows, calls, _, _ = self._run(self._bodies(), now=lambda: next(clock))
        self.assertEqual([item["verdict_reason"] for item in rows], ["battery_pass", "battery_pass", "time_budget"])
        self.assertEqual(len(calls), 4)
        self.assertFalse(od.phases_pass(rows))
        # stop_after_minutes=60: no phase has a full reserve at 26 minutes.
        rows, calls, _, _ = self._run(self._bodies(), minutes="60")
        self.assertEqual({item["verdict_reason"] for item in rows}, {"time_budget"})
        self.assertEqual(calls, [])

    def test_missing_rows_still_uninstall(self) -> None:
        bodies = self._bodies()
        bodies["2f-tamper"] = "rows_malformed"
        rows, calls, _, _ = self._run(bodies)
        self.assertEqual(rows[1]["verdict_reason"], "rows_malformed")
        # No body, no probe pid: the uninstall does not ask for a post-kill row,
        # so the real script exits 0 on a clean host and 2G runs.
        self.assertIn("VANTIO_REQUIRE_POST_KILL=no VANTIO_PROBE_PID=0", calls[3])
        self.assertTrue(rows[1]["uninstall_verified"])
        self.assertTrue(rows[2]["pass"])

    def test_missing_rows_on_a_dirty_host_stop_2g(self) -> None:
        bodies = self._bodies()
        bodies["2f-tamper"] = "rows_missing"
        rows, calls, _, _ = self._run(bodies, uninstall={"2f-tamper": "UNINSTALL_VERIFIED\nUNINSTALL_RESIDUAL bpffs\n"})
        self.assertEqual(rows[1]["verdict_reason"], "rows_missing")
        self.assertFalse(rows[1]["uninstall_verified"])
        self.assertEqual(rows[2]["verdict_reason"], "previous_uninstall")
        self.assertEqual(len(calls), 4)

    def test_2f_map_swap_timeout_still_runs_2g(self) -> None:
        bodies = self._bodies()
        refused = grade.ungraded_egress("2f-tamper", grade.MAP_SWAP_TIMEOUT)
        refused["map_swap"] = swap(swapped=False, reason=grade.MAP_SWAP_TIMEOUT)
        refused["kill_timing"] = grade.KILL_TIMING_NOT_KILLED
        refused["enrolled_after"] = {"pid": PID}
        bodies["2f-tamper"] = refused
        rows, calls, _, _ = self._run(bodies, uninstall={"2f-tamper": UNINSTALL_OK})
        self.assertEqual(rows[1]["verdict_reason"], "battery_not_graded")
        self.assertIn(f"VANTIO_REQUIRE_POST_KILL=no VANTIO_PROBE_PID={PID}", calls[3])
        self.assertTrue(rows[1]["uninstall_verified"])
        self.assertEqual(rows[1]["uninstall_rc"], 0)
        self.assertEqual((rows[2]["pass"], rows[2]["verdict_reason"]), (True, "battery_pass"))
        self.assertEqual(len(calls), 6)

    def test_2f_without_post_kill_row_still_runs_2g(self) -> None:
        # The guest killed after the swap, the uninstall is verified, but no
        # post-kill row: the script exits 1. 2F fails on the row; the host is
        # clean, so 2G still runs.
        rows, calls, _, _ = self._run(self._bodies(), uninstall={"2f-tamper": UNINSTALL_OK})
        self.assertIn(f"VANTIO_REQUIRE_POST_KILL=yes VANTIO_PROBE_PID={PID}", calls[3])
        self.assertEqual(rows[1]["uninstall_rc"], 1)
        self.assertTrue(rows[1]["uninstall_verified"])
        self.assertEqual((rows[1]["pass"], rows[1]["verdict_reason"]), (False, "host_post_kill_row_missing"))
        self.assertNotIn("post_kill_pid", rows[1])
        self.assertTrue(rows[2]["pass"])
        self.assertFalse(od.phases_pass(rows))

    def _case(self, results, *, deadline=None, now=None, ready=True):
        seen: list = []
        ssh = mock.Mock(side_effect=lambda _p, _n, command, timeout_s=None: seen.append(timeout_s) or results.pop(0))
        sshd = mock.Mock(return_value=ready)
        out = io.StringIO()
        with mock.patch.multiple(od, _ssh=ssh, _ssh_ready=sshd), contextlib.redirect_stdout(out):
            kwargs = {} if deadline is None else {"deadline": deadline, "now": now}
            completed, skipped = od._phase_ssh_case("vantio-lab-oct08", "vantio-gcp-lab-1", "cmd", **kwargs)
        return completed, skipped, seen, sshd.call_count, out.getvalue()

    def test_phase_guest_call_uses_the_phase_timeout(self) -> None:
        completed, skipped, seen, probes, _ = self._case([_done("PY_RC=0\n")])
        self.assertEqual((completed.returncode, skipped, seen, probes), (0, False, [od.PHASE_CASE_SSH_TIMEOUT], 0))
        # A guest exit code means the guest answered: no retry.
        _, skipped, seen, probes, _ = self._case([_done("PY_RC=1\noperation timed out", 255)])
        self.assertEqual((skipped, len(seen), probes), (False, 1, 0))

    def test_infra_retry_runs_when_it_fits(self) -> None:
        dead = _done("operation timed out", 255)
        for deadline, now in ((None, None), (self.T + od.PHASE_RETRY_NEED_S, lambda: self.T)):
            completed, skipped, seen, probes, out = self._case([dead, _done("PY_RC=0\n")], deadline=deadline, now=now)
            self.assertEqual((completed.returncode, skipped), (0, False), deadline)
            self.assertEqual(seen, [od.PHASE_CASE_SSH_TIMEOUT] * 2)
            self.assertEqual(probes, 1)
            self.assertIn("INFRA_RETRY", out)
        # sshd never came back: no second call, not a skip.
        completed, skipped, seen, _, _ = self._case([dead], ready=False)
        self.assertEqual((completed.returncode, skipped, len(seen)), (255, False, 1))

    def test_infra_retry_is_skipped_when_it_does_not_fit(self) -> None:
        dead = _done("operation timed out", 255)
        completed, skipped, seen, probes, out = self._case(
            [dead], deadline=self.T + od.PHASE_RETRY_NEED_S - 1, now=lambda: self.T
        )
        self.assertEqual((completed.returncode, skipped, len(seen), probes), (255, True, 1, 0))
        self.assertIn("INFRA_RETRY_SKIPPED time_budget", out)

    def test_skipped_retry_is_infra_not_graded_and_still_uninstalls(self) -> None:
        dead = _done("operation timed out", 255)
        for mode in od.PHASE_MODES:
            calls: list = []

            def ssh(_p, _n, command, timeout_s=None):
                calls.append(command)
                return dead if not command.endswith(" uninstall") else _done(UNINSTALL_OK)

            boot = mock.Mock(return_value=SOURCE)
            pull = mock.Mock(side_effect=AssertionError("no pull"))
            with mock.patch.multiple(od, _ssh=ssh, _boot_source=boot, _pull_guest_json=pull, _lane_seal=mock.Mock(return_value=SEAL)), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                kept = od._run_one_phase(
                    "vantio-lab-oct08", "vantio-gcp-lab-1", SEAL, mode, deadline=self.T + 600, now=lambda: self.T
                )
            self.assertEqual(kept["host_result"], "NOT_GRADED", mode)
            self.assertEqual(kept["reason"], "infra_retry_skipped", mode)
            self.assertEqual((kept["pass"], kept["verdict_reason"]), (False, "battery_not_graded"), mode)
            self.assertTrue(kept["uninstall_verified"], mode)
            self.assertEqual(len(calls), 2, mode)
            self.assertTrue(calls[1].endswith(" uninstall"), mode)
            self.assertIn("VANTIO_REQUIRE_POST_KILL=no", calls[1])
            self.assertEqual(boot.call_count, 0, mode)

    def test_runner_passes_the_deadline_to_each_phase(self) -> None:
        seen: list = []

        def one(_p, _n, _s, mode, deadline=None, now=None):
            seen.append((mode, deadline, callable(now)))
            return od.phase_row(mode, None, not_run_reason="transport")

        with mock.patch.multiple(od, _run_one_phase=mock.Mock(side_effect=one), _creation_epoch=mock.Mock(return_value=self.T)), contextlib.redirect_stdout(io.StringIO()):
            od.run_phase_batteries("p", "n", SEAL, {"STOP_AFTER_MINUTES": "105"}, ready=True, started_epoch=self.T + 20, now=lambda: self.T + 26 * 60)
        self.assertEqual(seen, [("2e-performance", self.T + 105 * 60 - od.PHASE_END_MARGIN_S, True)])

    def test_rowless_phase_reads_host_clean_from_the_lines(self) -> None:
        for text, rc, clean in (
            ("UNINSTALL_VERIFIED\n", 1, True),
            ("UNINSTALL_VERIFIED\nUNINSTALL_RESIDUAL bpffs\n", 0, False),
            ("loader said UNINSTALL_VERIFIED\n", 0, False),
            ("UNINSTALL_VERIFIED\n\noperation timed out", 255, False),
            ("UNINSTALL_VERIFIED\n", 2, False),
        ):
            stubs = {
                "_phase_ssh_case": mock.Mock(return_value=(_done("PY_RC=1\n", 1), False)),
                "_pull_guest_json": mock.Mock(side_effect=SystemExit("rows_missing")),
                "_ssh": mock.Mock(return_value=_done(text, rc)),
            }
            with mock.patch.multiple(od, **stubs), contextlib.redirect_stderr(io.StringIO()):
                kept = od._run_one_phase("vantio-lab-oct08", "vantio-gcp-lab-1", SEAL, "2e-performance")
            self.assertEqual(kept["verdict_reason"], "rows_missing", text)
            self.assertIs(kept["uninstall_verified"], clean, text)

    def test_transport_failure_without_py_rc_never_pulls_rows(self) -> None:
        # The tunnel died before the guest printed PY_RC. Rows on the guest
        # may be a previous phase's, so they are never pulled: NOT_RUN transport.
        for dead in (_done("operation timed out", 255), _done("Connection reset by peer", 1)):
            for mode in od.PHASE_MODES:
                pull = mock.Mock(side_effect=AssertionError("no pull"))
                uninstall = mock.Mock(return_value=_done(UNINSTALL_OK))
                stubs = {
                    "_phase_ssh_case": mock.Mock(return_value=(dead, False)),
                    "_pull_guest_json": pull,
                    "_ssh": uninstall,
                    "_boot_source": mock.Mock(side_effect=AssertionError("no boot read")),
                }
                with mock.patch.multiple(od, **stubs), contextlib.redirect_stderr(io.StringIO()):
                    kept = od._run_one_phase("vantio-lab-oct08", "vantio-gcp-lab-1", SEAL, mode)
                self.assertEqual(pull.call_count, 0, mode)
                self.assertEqual(kept["host_result"], "NOT_RUN", mode)
                self.assertEqual(kept["not_run_reason"], "transport", mode)
                self.assertIs(kept["pass"], False, mode)
                self.assertTrue(kept["uninstall_verified"], mode)
                self.assertEqual(uninstall.call_count, 1, mode)
                self.assertIn("VANTIO_REQUIRE_POST_KILL=no", uninstall.call_args[0][2])
        # The same transport text after the guest printed PY_RC does pull.
        pull = mock.Mock(side_effect=SystemExit("rows_missing"))
        stubs = {
            "_phase_ssh_case": mock.Mock(return_value=(_done("PY_RC=1\nConnection reset by peer", 255), False)),
            "_pull_guest_json": pull,
            "_ssh": mock.Mock(return_value=_done(UNINSTALL_OK)),
        }
        with mock.patch.multiple(od, **stubs), contextlib.redirect_stderr(io.StringIO()):
            kept = od._run_one_phase("vantio-lab-oct08", "vantio-gcp-lab-1", SEAL, "2e-performance")
        self.assertEqual(pull.call_count, 1)
        self.assertEqual(kept["verdict_reason"], "rows_missing")

    def test_post_kill_row_is_asked_for_only_with_a_probe_after_the_swap(self) -> None:
        bodies = self._bodies()
        bodies["2f-tamper"]["enrolled_after"]["pid"] = 0
        rows, calls, _, _ = self._run(bodies)
        self.assertIn("VANTIO_REQUIRE_POST_KILL=no VANTIO_PROBE_PID=0", calls[3])
        self.assertEqual(rows[1]["verdict_reason"], "host_probe_pid_missing")
        self.assertTrue(rows[2]["pass"])
        bodies = self._bodies()
        bodies["2f-tamper"]["kill_timing"] = grade.KILL_TIMING_NOT_KILLED
        _, calls, _, _ = self._run(bodies)
        self.assertIn(f"VANTIO_REQUIRE_POST_KILL=no VANTIO_PROBE_PID={PID}", calls[3])

    def test_residual_line_stops_later_phases(self) -> None:
        rows, calls, _, _ = self._run(self._bodies(), uninstall={"2e-performance": "UNINSTALL_VERIFIED\nUNINSTALL_RESIDUAL bpffs\n"})
        self.assertEqual(rows[0]["verdict_reason"], "uninstall_not_verified")
        self.assertEqual([item.get("not_run_reason") for item in rows[1:]], ["previous_uninstall"] * 2)
        self.assertEqual(len(calls), 2)

    def test_2g_seal_is_checked_against_the_lane_seal(self) -> None:
        rows, _, _, _ = self._run(self._bodies(), lane_seal="b" * 64)
        self.assertEqual([item["pass"] for item in rows], [True, True, False])
        self.assertEqual(rows[2]["verdict_reason"], "host_seal_not_lane")
        self.assertIs(rows[2]["seal_lane"], False)
        rows, _, _, _ = self._run(self._bodies(), lane_seal="")
        self.assertEqual(rows[2]["verdict_reason"], "host_seal_not_lane")

    def test_every_phase_call_has_a_timeout(self) -> None:
        timeouts: list = []
        self._run(self._bodies(), timeouts=timeouts)
        self.assertEqual(
            timeouts,
            [("pull", od.PHASE_PULL_TIMEOUT_S), ("uninstall", od.PHASE_UNINSTALL_TIMEOUT_S)] * 3,
        )
        seen: list = []

        def run(argv, timeout_s=None):
            seen.append(timeout_s)
            return _done(json.dumps({"sourceImage": SOURCE}))

        with mock.patch.object(od, "_run", side_effect=run):
            self.assertEqual(od._boot_source("vantio-lab-oct08", "vantio-gcp-lab-1"), SOURCE)
        self.assertEqual(seen, [od.PHASE_DESCRIBE_TIMEOUT_S])
        scp: list = []

        def scp_run(argv, timeout_s=None):
            scp.append(timeout_s)
            return _done("", 1)

        with mock.patch.object(od, "_run", side_effect=scp_run), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                od._pull_guest_json("vantio-lab-oct08", "vantio-gcp-lab-1", timeout_s=od.PHASE_PULL_TIMEOUT_S)
        self.assertEqual(scp, [od.PHASE_PULL_TIMEOUT_S])

    def test_a_broken_phase_is_recorded_and_stops_the_rest(self) -> None:
        bodies = self._bodies()
        with mock.patch.object(od, "phase_command", side_effect=[od.phase_command(SEAL, "2e-performance"), SystemExit("battery"), "x"]):
            rows, calls, _, _ = self._run(bodies)
        self.assertEqual([item["verdict_reason"] for item in rows], ["battery_pass", "phase_error", "previous_uninstall"])
        self.assertEqual(len(calls), 2)

    def test_phase_failure_does_not_stop_the_next(self) -> None:
        bodies = self._bodies()
        bodies["2e-performance"] = body_2e(runtime=901)
        rows, _, _, _ = self._run(bodies)
        self.assertEqual([item["pass"] for item in rows], [False, True, True])


class RunBatteriesTest(unittest.TestCase):
    def _write(
        self,
        *,
        full: bool,
        phase_rows: list,
        uninstall: str = "UNINSTALL_VERIFIED\ndeny_attr_post_kill pid 9 anchor 3\n",
        uninstall_rc: int = 0,
        ready: bool = True,
        interim: list | None = None,
        kill_body: dict | None = None,
        calls: list | None = None,
        marks: object = None,
    ) -> tuple[object, dict]:
        if marks is None:
            marks = subprocess.CompletedProcess([], 0, stdout="120\n45\n", stderr="")
        if kill_body is None:
            kill_body = {"enrolled_after": {"pid": 9}}
        repeat = {"b1_pass": True, "deny_hold": True, "deny_pid": 41, "desc_deny_pid": 42, "lineage_anchor": 7}
        done = subprocess.CompletedProcess([], uninstall_rc, stdout=uninstall, stderr="")
        setup = subprocess.CompletedProcess([], 0, stdout="", stderr="")

        def ssh(_p, _n, command, timeout_s=None):
            if "host_evidence_hu.py" in command:
                return subprocess.CompletedProcess([], 0, stdout=HU_PASS, stderr="")
            if calls is not None:
                calls.append(command)
            if command.startswith("for f in /var/lib/vantio-pe-clean-host/evidence/events.ndjson"):
                if calls is not None:
                    calls.append(f"marks timeout_s={timeout_s}")
                return marks(command) if callable(marks) else marks
            return done if command.endswith(" uninstall") else setup

        def loader_case(_p, _n, _s, mode):
            if calls is not None:
                calls.append(f"loader_case {mode}")
            return {"body": kill_body, "rc": 0, "word": "held"}

        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence"

            def phases(*_args, **_kwargs):
                # What is on disk while 2E, 2F, 2G run.
                if interim is not None:
                    interim.append(json.loads((evidence / "gcp-lab-rows.json").read_text(encoding="utf-8")))
                return phase_rows

            runner = mock.Mock(side_effect=phases)
            stubs = {
                "_enabled": mock.DEFAULT,
                "require_lab_project": mock.Mock(return_value="vantio-lab-test"),
                "_gate_ok": mock.DEFAULT,
                "batteries_requested": mock.Mock(return_value=True),
                "instance_name": mock.Mock(return_value="vantio-gcp-lab-1"),
                "refuse_batteries": mock.Mock(return_value=SEAL),
                "_evidence_dir": mock.Mock(return_value=evidence),
                "_stage_payload": mock.Mock(return_value=[]),
                "_wait_until_running": mock.DEFAULT,
                "_ssh": mock.Mock(side_effect=ssh),
                "_scp_to": mock.DEFAULT,
                "_prepare_lab_lsm": mock.Mock(return_value={}),
                "_wait_live_boot": mock.Mock(return_value="boot-2"),
                "_run_one_battery": mock.Mock(return_value=repeat),
                "full_set_passes": mock.Mock(return_value=full),
                # 2D asks for a post-kill row only when the kill body has the probe pid.
                "_loader_case": mock.Mock(side_effect=loader_case),
                "run_phase_batteries": runner,
                "drop_guest_copies": mock.DEFAULT,
                "remove_os_login_key": mock.DEFAULT,
            }
            code: object = 0
            with mock.patch.multiple(od, **stubs), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                try:
                    code = od.run_batteries({"RUNNER_TEMP": tmp, "STOP_AFTER_MINUTES": "100"})
                except SystemExit as exc:
                    code = exc.code
            self.assertIs(runner.call_args.kwargs["ready"], ready)
            return code, json.loads((evidence / "gcp-lab-rows.json").read_text(encoding="utf-8"))

    def _passing(self) -> list:
        return [row("2e-performance", body_2e()), row("2f-tamper", body_2f()), row("2g-distro", body_2g())]

    def test_h_u_stop_does_not_start_batteries(self) -> None:
        facts = HU.passing_facts()
        facts["cursor_stores"] = "present"
        stop = HU.transcript(facts)
        battery = mock.Mock(side_effect=AssertionError("battery started"))

        def ssh(_p, _n, command, timeout_s=None):
            if "host_evidence_hu.py" in command:
                return subprocess.CompletedProcess([], 6, stdout=stop, stderr="")
            return subprocess.CompletedProcess([], 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence"
            stubs = {
                "_enabled": mock.DEFAULT,
                "require_lab_project": mock.Mock(return_value="vantio-lab-test"),
                "_gate_ok": mock.DEFAULT,
                "batteries_requested": mock.Mock(return_value=True),
                "instance_name": mock.Mock(return_value="vantio-gcp-lab-1"),
                "refuse_batteries": mock.Mock(return_value=SEAL),
                "_evidence_dir": mock.Mock(return_value=evidence),
                "_stage_payload": mock.Mock(return_value=[]),
                "_wait_until_running": mock.DEFAULT,
                "_ssh": mock.Mock(side_effect=ssh),
                "_scp_to": mock.DEFAULT,
                "_prepare_lab_lsm": mock.Mock(side_effect=AssertionError("lsm started")),
                "_run_one_battery": battery,
            }
            with mock.patch.multiple(od, **stubs), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    od.run_batteries({"RUNNER_TEMP": tmp, "STOP_AFTER_MINUTES": "100"})
            body = json.loads((evidence / "h-u.json").read_text(encoding="utf-8"))
            text = (evidence / "h-u.json").read_text(encoding="utf-8")
        self.assertEqual(caught.exception.code, "h_u")
        battery.assert_not_called()
        self.assertEqual(body["verdict"], "STOP")
        self.assertNotIn("PRIVATE KEY", text)
        self.assertIn("h-u.json", od.EVIDENCE_FILES)

    def test_2d_without_a_probe_pid_does_not_ask_for_or_count_a_post_kill_row(self) -> None:
        # PR 368 council N1: with pid 0 any older post-kill row would satisfy the check.
        calls: list = []
        code, rows = self._write(full=True, phase_rows=self._passing(), kill_body={}, calls=calls)
        uninstall = [command for command in calls if command.endswith(" uninstall")]
        self.assertEqual(len(uninstall), 1)
        self.assertIn("VANTIO_REQUIRE_POST_KILL=no VANTIO_PROBE_PID=0", uninstall[0])
        self.assertEqual(code, "uninstall")

    def test_2d_with_a_probe_pid_asks_for_that_pid(self) -> None:
        calls: list = []
        code, _rows = self._write(full=True, phase_rows=self._passing(), calls=calls)
        uninstall = [command for command in calls if command.endswith(" uninstall")]
        self.assertIn("VANTIO_REQUIRE_POST_KILL=yes VANTIO_PROBE_PID=9", uninstall[0])
        self.assertEqual(code, 0)

    def test_2d_marks_the_files_before_the_kill_and_passes_the_marks(self) -> None:
        # PR 368 council D1: the 2C cycle writes the probe's row before the final
        # uninstall, so the sizes are taken before the 2D case kills the loader.
        calls: list = []
        code, _rows = self._write(full=True, phase_rows=self._passing(), calls=calls)
        mark = next(i for i, c in enumerate(calls) if c.startswith("for f in /var/lib/vantio-pe-clean-host/evidence/events.ndjson"))
        self.assertIn("/var/log/vantio/uninstall.ndjson", calls[mark])
        self.assertLess(mark, calls.index("loader_case 2d-crash-recovery"))
        self.assertLess(calls.index("loader_case 2d-crash-recovery"), calls.index("loader_case 2c-upgrade-rollback"))
        uninstall = [command for command in calls if command.endswith(" uninstall")]
        self.assertEqual(len(uninstall), 1)
        self.assertIn(
            "VANTIO_REQUIRE_POST_KILL=yes VANTIO_PROBE_PID=9 VANTIO_EVENTS_BEFORE=120 VANTIO_LEDGER_BEFORE=45 ",
            uninstall[0],
        )
        self.assertEqual(code, 0)

    def _run_marks(
        self, command: str, stat_rc: int, exists: set, sudo_rc: int = 0
    ) -> subprocess.CompletedProcess:
        """Run the real marks command with a fake sudo: test -e by set, stat by rc.

        A non-zero sudo_rc makes every sudo call fail with that code (sudo broken).
        """
        with tempfile.TemporaryDirectory() as tmp:
            sudo = Path(tmp) / "sudo"
            sudo.write_text(
                "#!/bin/bash\n"
                '[ "$SUDO_RC" = 0 ] || { echo "sudo: failed" >&2; exit "$SUDO_RC"; }\n'
                'if [ "$1" = test ]; then\n'
                '  neg=0; [ "$2" = "!" ] && { neg=1; shift; }\n'
                '  [ "$2" = -e ] || exit 98\n'
                '  case " $EXISTS " in *" $3 "*) hit=1 ;; *) hit=0 ;; esac\n'
                '  [ "$hit" != "$neg" ] && exit 0; exit 1\n'
                "fi\n"
                'if [ "$1" = stat ]; then\n'
                '  case " $EXISTS " in *" $4 "*) ;; *) echo "stat: no such file" >&2; exit 1 ;; esac\n'
                '  [ "$STAT_RC" = 0 ] && { echo 123; exit 0; }; echo "stat: failed" >&2; exit "$STAT_RC"\n'
                "fi\n"
                "exit 99\n",
                encoding="utf-8",
            )
            sudo.chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{tmp}:{os.environ['PATH']}",
                "STAT_RC": str(stat_rc),
                "SUDO_RC": str(sudo_rc),
                "EXISTS": " ".join(sorted(exists)),
            }
            return subprocess.run(["bash", "-c", command], capture_output=True, text=True, env=env, check=False)

    def test_the_marks_command_reads_0_only_for_a_missing_file(self) -> None:
        events = "/var/lib/vantio-pe-clean-host/evidence/events.ndjson"
        ledger = "/var/log/vantio/uninstall.ndjson"
        seen: list = []

        def capture(command: str) -> subprocess.CompletedProcess:
            seen.append(command)
            return subprocess.CompletedProcess([], 0, stdout="120\n45\n", stderr="")

        calls: list = []
        self._write(full=True, phase_rows=self._passing(), marks=capture, calls=calls)
        self.assertIn("marks timeout_s=60", calls)
        command = seen[0]
        self.assertEqual(self._run_marks(command, 0, {events, ledger}).stdout.split(), ["123", "123"])
        self.assertEqual(self._run_marks(command, 0, {events}).stdout.split(), ["123", "0"])
        self.assertEqual(self._run_marks(command, 0, set()).stdout.split(), ["0", "0"])
        # stat fails on a file that exists: no 0 is printed for it.
        failed = self._run_marks(command, 1, {events})
        self.assertEqual(failed.stdout.split(), ["0"])
        # sudo itself fails on every call: nothing is printed, not "0 0".
        for exists in ({events, ledger}, {events}, set()):
            broken = self._run_marks(command, 0, exists, sudo_rc=1)
            self.assertEqual(broken.stdout.split(), [], sorted(exists))
            self.assertNotEqual(broken.returncode, 0, sorted(exists))

    def test_a_sudo_failure_fails_the_marks_closed(self) -> None:
        # PR 368 council delta-3 N1: a failed sudo must not read as "missing" (offset 0).
        events = "/var/lib/vantio-pe-clean-host/evidence/events.ndjson"
        ledger = "/var/log/vantio/uninstall.ndjson"
        for exists in ({events, ledger}, {events}, {ledger}, set()):
            calls: list = []
            code, _rows = self._write(
                full=True,
                phase_rows=self._passing(),
                calls=calls,
                marks=lambda command, exists=exists: self._run_marks(command, 0, exists, sudo_rc=1),
            )
            uninstall = [command for command in calls if command.endswith(" uninstall")]
            self.assertIn(
                "VANTIO_REQUIRE_POST_KILL=no VANTIO_PROBE_PID=9 VANTIO_EVENTS_BEFORE= VANTIO_LEDGER_BEFORE= ",
                uninstall[0],
                sorted(exists),
            )
            self.assertEqual(code, "uninstall", sorted(exists))

    def test_a_stat_failure_on_an_existing_file_fails_the_marks_closed(self) -> None:
        # PR 368 council delta-2 note 1: a failed stat must not read the whole file.
        events = "/var/lib/vantio-pe-clean-host/evidence/events.ndjson"
        ledger = "/var/log/vantio/uninstall.ndjson"
        for exists in ({events, ledger}, {events}, {ledger}):
            calls: list = []
            code, _rows = self._write(
                full=True,
                phase_rows=self._passing(),
                calls=calls,
                marks=lambda command, exists=exists: self._run_marks(command, 1, exists),
            )
            uninstall = [command for command in calls if command.endswith(" uninstall")]
            self.assertIn(
                "VANTIO_REQUIRE_POST_KILL=no VANTIO_PROBE_PID=9 VANTIO_EVENTS_BEFORE= VANTIO_LEDGER_BEFORE= ",
                uninstall[0],
                sorted(exists),
            )
            self.assertEqual(code, "uninstall", sorted(exists))

    def test_2d_without_good_marks_does_not_ask_for_or_count_a_post_kill_row(self) -> None:
        bad = (
            subprocess.CompletedProcess([], 1, stdout="120\n45\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="120\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="120\nx45\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="1\n2\n3\n", stderr=""),
        )
        for marks in bad:
            calls: list = []
            code, _rows = self._write(full=True, phase_rows=self._passing(), calls=calls, marks=marks)
            uninstall = [command for command in calls if command.endswith(" uninstall")]
            self.assertIn(
                "VANTIO_REQUIRE_POST_KILL=no VANTIO_PROBE_PID=9 VANTIO_EVENTS_BEFORE= VANTIO_LEDGER_BEFORE= ",
                uninstall[0],
                marks.stdout,
            )
            self.assertEqual(code, "uninstall", marks.stdout)

    def test_all_pass(self) -> None:
        code, rows = self._write(full=True, phase_rows=self._passing())
        self.assertEqual(code, 0)
        self.assertTrue(rows["phases_pass"])
        self.assertEqual(len(rows["phases"]), 3)
        self.assertEqual(rows["claim_cap"], "INTERNAL_CLEAN_HOST_PROOF")
        self.assertEqual(rows["distro_scope"], "ubuntu-2404-only")
        self.assertEqual(len(rows["distro_excluded"]), len(od.DISTRO_EXCLUDED))

    def test_interim_rows_are_on_disk_before_the_phases(self) -> None:
        interim: list = []
        code, rows = self._write(full=True, phase_rows=self._passing(), interim=interim)
        self.assertEqual(code, 0)
        self.assertEqual(len(interim), 1)
        self.assertEqual(interim[0]["phases"], [])
        self.assertIs(interim[0]["interim"], True)
        self.assertIs(interim[0]["phases_complete"], False)
        self.assertFalse(interim[0]["phases_pass"])
        self.assertIs(rows["interim"], False)
        self.assertIs(rows["phases_complete"], True)
        self.assertTrue(interim[0]["full_set"])
        self.assertTrue(interim[0]["uninstall_verified"])
        self.assertEqual(interim[0]["claim_cap"], "INTERNAL_CLEAN_HOST_PROOF")
        self.assertEqual(interim[0]["distro_scope"], "ubuntu-2404-only")
        self.assertEqual(len(interim[0]["repeats"]), od.BATTERY_REPEATS)
        self.assertTrue(rows["phases_pass"])

    def test_interim_flags_do_not_change_the_grade(self) -> None:
        phases = self._passing()
        phases[1] = row("2f-tamper", body_2f(net=0))
        code, rows = self._write(full=True, phase_rows=phases)
        # The phases ran: complete, not interim, and still a failed step.
        self.assertEqual(code, "phases")
        self.assertIs(rows["phases_complete"], True)
        self.assertIs(rows["interim"], False)
        self.assertFalse(rows["phases_pass"])
        kept = od.allow_record({"interim": True, "phases_complete": False, "phases": self._passing()})
        self.assertTrue(kept["phases_pass"])
        self.assertEqual((kept["interim"], kept["phases_complete"]), (True, False))
        self.assertNotIn("interim", od.allow_record({"interim": "yes"}))

    def test_final_uninstall_timeout_is_not_clean(self) -> None:
        code, rows = self._write(
            full=True, phase_rows=[], uninstall="UNINSTALL_VERIFIED\n\noperation timed out", uninstall_rc=255, ready=False
        )
        self.assertEqual(code, "uninstall")
        self.assertFalse(rows["uninstall_verified"])

    def test_dirty_final_uninstall_runs_no_phase(self) -> None:
        for text in ("UNINSTALL_NOT_VERIFIED rc=1\n", "UNINSTALL_VERIFIED\nUNINSTALL_RESIDUAL bpffs\n", "x UNINSTALL_VERIFIED\n"):
            code, rows = self._write(full=True, phase_rows=[], uninstall=text, uninstall_rc=1, ready=False)
            self.assertEqual(code, "uninstall", text)
            self.assertFalse(rows["uninstall_verified"], text)

    def test_missing_2d_post_kill_row_does_not_block_the_phases(self) -> None:
        # The final uninstall verified the host but found no 2D post-kill row
        # (exit 1). 2E, 2F, 2G still run; the full set still fails on the row.
        code, rows = self._write(
            full=True,
            phase_rows=self._passing(),
            uninstall="UNINSTALL_VERIFIED\npost_kill_row_missing\n",
            uninstall_rc=1,
            ready=True,
        )
        self.assertEqual(code, "uninstall")
        self.assertTrue(rows["uninstall_verified"])
        self.assertFalse(rows["deny_attr_post_kill"])
        self.assertTrue(rows["phases_pass"])
        self.assertEqual(len(rows["phases"]), 3)

    def test_a_failed_phase_fails_the_step(self) -> None:
        phases = self._passing()
        phases[1] = row("2f-tamper", body_2f(net=0))
        code, rows = self._write(full=True, phase_rows=phases)
        self.assertEqual(code, "phases")
        self.assertFalse(rows["phases_pass"])
        self.assertEqual(rows["phases"][1]["verdict_reason"], "battery_fail")

    def test_phases_are_recorded_when_an_earlier_battery_failed(self) -> None:
        code, rows = self._write(full=False, phase_rows=self._passing())
        self.assertEqual(code, "battery")
        self.assertTrue(rows["phases_pass"])


class WiringTest(unittest.TestCase):
    def test_guest_command_accepts_the_phases(self) -> None:
        for mode in od.PHASE_MODES:
            self.assertEqual(od.guest_command(SEAL, mode), f"bash {od.GUEST_DIR}/enterprise-rows.sh {SEAL} {mode}")
        with self.assertRaises(SystemExit):
            od.phase_command(SEAL, "2h-anything")

    def test_guest_script_runs_the_phases(self) -> None:
        text = (ROOT / "scripts/gcp/lab-guests/enterprise-rows.sh").read_text(encoding="utf-8")
        self.assertIn("lsm-guard|2e-performance|2f-tamper|2g-distro|uninstall) ;;", text)
        self.assertIn("  2c-upgrade-rollback|2d-crash-recovery|lsm-guard|2e-performance|2f-tamper|2g-distro)\n", text)
        self.assertIn('VANTIO_LAB_CLOUD=gcp VANTIO_IMAGE="$image" VANTIO_IMAGE_ID="${VANTIO_IMAGE_ID:-}"', text)
        result = subprocess.run(["bash", "-n", str(ROOT / "scripts/gcp/lab-guests/enterprise-rows.sh")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_job_checks_out_part_four(self) -> None:
        workflow = (ROOT / ".github/workflows/gcp-lab-provision.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count("scripts/gcp/offline_deliver_4.py"), workflow.count("scripts/gcp/offline_deliver_3.py"))
        self.assertGreaterEqual(workflow.count("scripts/gcp/offline_deliver_4.py"), 3)
        loader = (ROOT / "scripts/gcp/offline_deliver.py").read_text(encoding="utf-8")
        self.assertIn('"offline_deliver_4.py"', loader)

    def test_ci_runs_this_file(self) -> None:
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("python3 scripts/gcp/test_gcp_phase_batteries.py -v", ci)

    def test_part_four_never_shells_out_itself(self) -> None:
        source = (ROOT / "scripts/gcp/offline_deliver_4.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess.", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("labels", source)


if __name__ == "__main__":
    unittest.main()
