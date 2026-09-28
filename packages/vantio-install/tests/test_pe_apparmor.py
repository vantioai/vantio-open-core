"""Regression fixtures for the observe-only PE AppArmor decision."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from tests.test_stage_a import Harness  # noqa: E402
from vantio_install import constants  # noqa: E402
from vantio_install.commands import (  # noqa: E402
    apparmor_parser_load_argv,
    apparmor_parser_remove_argv,
    observe_apparmor_opt,
    observe_binds,
    observe_container_argv,
)
from vantio_install.host import tracefs_present  # noqa: E402
from vantio_install.live_executor import ROLLBACK_OPERATIONS, STEP_OPERATIONS  # noqa: E402
from vantio_install.pe_apparmor import (  # noqa: E402
    apparmor_profile_loaded,
    inspect_is_observe_container,
    pe_apparmor_profile_path,
    profile_text,
)


class ObserveApparmorFixtures(unittest.TestCase):
    def test_profile_keeps_docker_default_denies_and_allows_bpf_pin(self) -> None:
        text = profile_text()
        self.assertIn("profile vantio-pe-observe flags=(attach_disconnected,mediate_deleted) {", text)
        self.assertNotIn("deny /sys/fs/[^c]*/** wklx", text)
        self.assertNotIn("flags=(unconfined)", text)
        self.assertIn("/sys/fs/bpf/ rwkl,", text)
        self.assertIn("/sys/fs/bpf/** rwkl,", text)
        self.assertIn("deny /sys/fs/bpf/** x,", text)
        self.assertIn("deny /sys/fs/[^cb]*/** wklx,", text)
        self.assertIn("deny /sys/fs/b[^p]*/** wklx,", text)
        self.assertIn("deny /sys/fs/bp[^f]*/** wklx,", text)
        self.assertIn("deny /sys/fs/bpf?* wklx,", text)
        for kept in (
            "deny mount,",
            "deny @{PROC}/* w,",
            "deny /sys/[^f]*/** wklx,",
            "deny /sys/fs/c[^g]*/** wklx,",
            "deny /sys/fs/cg[^r]*/** wklx,",
            "deny /sys/firmware/** rwklx,",
            "deny /sys/devices/virtual/powercap/** rwklx,",
            "deny /sys/kernel/security/** rwklx,",
            "signal (receive) peer=unconfined,",
            "ptrace (trace,read,tracedby,readby) peer=vantio-pe-observe,",
        ):
            self.assertIn(kept, text)
        self.assertEqual(text.count("profile vantio-pe-observe "), 1)
        self.assertEqual(constants.PE_OBSERVE_APPARMOR_PROFILE, "vantio-pe-observe")
        self.assertNotIn("/sys/kernel/tracing rw", text)
        self.assertNotIn("/sys/kernel/tracing/** rw", text)
        self.assertIn("Writes stay denied.", text)

    def test_inspect_requires_named_profile_and_refuses_privileged(self) -> None:
        cmd = '["--iface","ens5"]'
        good = f"true false vantio-pe-observe {cmd}"
        self.assertTrue(inspect_is_observe_container(good))
        self.assertFalse(inspect_is_observe_container(f"true false docker-default {cmd}"))
        self.assertFalse(inspect_is_observe_container(f"true false unconfined {cmd}"))
        self.assertFalse(inspect_is_observe_container(f"true true vantio-pe-observe {cmd}"))
        self.assertFalse(inspect_is_observe_container(f"false false vantio-pe-observe {cmd}"))
        self.assertFalse(inspect_is_observe_container(f"true false vantio-pe-observe {cmd} --enforce"))
        self.assertFalse(inspect_is_observe_container("true false vantio-pe-observe"))

    def test_profile_list_match_is_exact(self) -> None:
        directory = Path(tempfile.mkdtemp(prefix="vantio-aa-"))
        self.addCleanup(lambda: shutil.rmtree(directory, ignore_errors=True))
        missing = directory / "missing"
        self.assertIs(apparmor_profile_loaded("vantio-pe-observe", missing), False)
        profiles = directory / "profiles"
        profiles.write_text(
            "docker-default (enforce)\nvantio-pe-observe (enforce)\n",
            encoding="utf-8",
        )
        self.assertIs(apparmor_profile_loaded("vantio-pe-observe", profiles), True)
        self.assertIs(apparmor_profile_loaded("vantio-pe-observe-extra", profiles), False)
        other = directory / "other"
        other.write_text("docker-default (enforce)\n", encoding="utf-8")
        self.assertIs(apparmor_profile_loaded("vantio-pe-observe", other), False)
        self.assertIsNone(apparmor_profile_loaded("vantio-pe-observe", directory))

    def test_parser_argv_is_replace_or_remove_of_the_stage_profile(self) -> None:
        path = "/var/lib/vantio/stage/apparmor/vantio-pe-observe"
        self.assertEqual(apparmor_parser_load_argv(path), ["apparmor_parser", "-Kr", path])
        self.assertEqual(apparmor_parser_remove_argv(path), ["apparmor_parser", "-KR", path])
        self.assertEqual(
            pe_apparmor_profile_path(Path("/var/lib/vantio/stage")),
            Path("/var/lib/vantio/stage/apparmor/vantio-pe-observe"),
        )

    def test_generated_docker_argv_sets_the_named_profile(self) -> None:
        tag = constants.FROZEN_PINS["pe_local_tag"]
        argv = observe_container_argv(tag=tag, iface="ens5", name="vantio-pe-test")
        self.assertEqual(argv[argv.index("--security-opt") + 1], observe_apparmor_opt())
        self.assertEqual(
            [argv[index + 1] for index, item in enumerate(argv) if item == "--cap-add"],
            ["NET_ADMIN", "BPF", "SYS_ADMIN"],
        )
        self.assertNotIn("--privileged", argv)
        self.assertNotIn("PERFMON", argv)
        self.assertNotIn("apparmor=unconfined", argv)
        self.assertNotIn("apparmor=docker-default", argv)
        self.assertEqual(
            [argv[index + 1] for index, item in enumerate(argv) if item == "-v"],
            ["/sys/fs/bpf:/sys/fs/bpf", "/sys/kernel/tracing:/sys/kernel/tracing"],
        )
        self.assertEqual(observe_binds(), ["/sys/fs/bpf:/sys/fs/bpf", "/sys/kernel/tracing:/sys/kernel/tracing"])
        self.assertNotIn("/sys/kernel/debug/tracing:/sys/kernel/debug/tracing", argv)
        self.assertNotIn("/sys/kernel/tracing:/sys/kernel/tracing:ro", argv)
        self.assertEqual(argv.count("--security-opt"), 1)
        self.assertNotIn("--privileged", argv)

    def test_plan_lists_profile_load_before_container_start(self) -> None:
        harness = Harness()
        self.addCleanup(harness.close)
        code, body = harness.run("plan")
        self.assertEqual(code, 0, body)
        plan = json.loads((harness.tx_file("PLAN.json")).read_text(encoding="utf-8"))
        ops = plan["live_operations"]
        self.assertLess(ops.index("write_pe_apparmor"), ops.index("load_pe_apparmor"))
        self.assertLess(ops.index("load_pe_apparmor"), ops.index("start_pe_observe"))
        preflight = json.loads((harness.tx_file("PREFLIGHT.json")).read_text(encoding="utf-8"))
        apparmor = [row for row in preflight["checks"] if row["id"] == "PF-APPARMOR"]
        self.assertEqual([row["result"] for row in apparmor], ["PASS"])
        self.assertEqual(
            STEP_OPERATIONS["start_pe_observe"],
            ("tc_clsact", "write_pe_apparmor", "load_pe_apparmor", "start_pe_observe"),
        )
        self.assertEqual(
            ROLLBACK_OPERATIONS["start_pe_observe"],
            (
                "docker_stop",
                "docker_rm",
                "unpin_bpf_maps",
                "unload_pe_apparmor",
                "remove_pe_apparmor",
                "tc_clsact_del",
            ),
        )

    def test_missing_apparmor_blocks_plan(self) -> None:
        harness = Harness()
        self.addCleanup(harness.close)
        harness.host["apparmor_enabled"] = False
        code, body = harness.run("plan")
        self.assertEqual(code, 2, body)
        self.assertIn("PF-APPARMOR", body["failed_or_limiting_checks"])
        harness.host["apparmor_enabled"] = True
        harness.host["apparmor_parser"] = "UNKNOWN"
        code, body = harness.run("plan")
        self.assertEqual(code, 2, body)
        self.assertIn("PF-APPARMOR", body["failed_or_limiting_checks"])

    def test_tracefs_probe_accepts_only_a_nonempty_kernel_tracing_mount(self) -> None:
        mounts = "tracefs /sys/kernel/tracing tracefs rw,nosuid,nodev,noexec,relatime 0 0\n"
        self.assertTrue(tracefs_present(mounts, ["events"]))
        self.assertFalse(tracefs_present(mounts, []))
        self.assertFalse(tracefs_present(mounts, None))
        debug_only = "tracefs /sys/kernel/debug/tracing tracefs rw 0 0\n"
        self.assertFalse(tracefs_present(debug_only, ["events"]))
        self.assertFalse(tracefs_present("", ["events"]))

    def test_missing_tracefs_blocks_plan(self) -> None:
        harness = Harness()
        self.addCleanup(harness.close)
        harness.host["tracefs_mounted"] = False
        code, body = harness.run("plan")
        self.assertEqual(code, 2, body)
        self.assertIn("PF-TRACEFS", body["failed_or_limiting_checks"])
        harness.host["tracefs_mounted"] = "UNKNOWN"
        code, body = harness.run("plan")
        self.assertEqual(code, 2, body)
        self.assertIn("PF-TRACEFS", body["failed_or_limiting_checks"])
        del harness.host["tracefs_mounted"]
        code, body = harness.run("plan")
        self.assertEqual(code, 2, body)
        self.assertIn("PF-TRACEFS", body["failed_or_limiting_checks"])
