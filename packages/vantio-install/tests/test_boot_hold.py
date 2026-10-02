"""Boot-hold tests. No EC2 and no live packet filter."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE))

from vantio_install.boot_hold.cli import main  # noqa: E402
from vantio_install.boot_hold.constants import BPF_PINS, HELD_MESSAGE, SLICE  # noqa: E402
from vantio_install.boot_hold.errors import BootHoldError  # noqa: E402
from vantio_install.boot_hold.files import allow_profile, deny_profile  # noqa: E402
from vantio_install.boot_hold.graph import graph_errors, parse_unit  # noqa: E402
from vantio_install.boot_hold.identity import Caller  # noqa: E402
from vantio_install.boot_hold.net import commands_are_scoped  # noqa: E402
from vantio_install.boot_hold.policy import _trusted, default_policy, load_policy, save_policy  # noqa: E402
from vantio_install.boot_hold.lifecycle import enforcement_lifecycle  # noqa: E402
from vantio_install.boot_hold.readiness import (  # noqa: E402
    assemble_host_facts,
    attachment_from_log,
    evaluate_ready,
    new_block_count,
    perform_deny_self_check,
    policy_id_from_cmdline,
    probe_loader,
)
from vantio_install.boot_hold.probe_link import HOST_IFACE, PEER_IFACE  # noqa: E402
from vantio_install.commands import enforce_container_argv  # noqa: E402
from vantio_install.boot_hold.service import (  # noqa: E402
    apply_boot,
    configure,
    enable_from_apply,
    enroll_compose,
    enroll_docker,
    enroll_systemd,
    loader_argv,
    observe_unenrolled,
    opt_out,
    observe_profile_path,
    prepare_enforce,
    release,
    reload_observe_profile,
    status_body,
)
from vantio_install.boot_hold.units import static_units  # noqa: E402
from vantio_install.constants import PROOF_CEILING, PROOF_STATE  # noqa: E402
from vantio_install.pe_apparmor import profile_text  # noqa: E402

READY = {
    "bpf_pins": list(BPF_PINS),
    "loader_cmdline": "/vantio-loader --iface ens5 --enforce --cgroup-skb-enforce",
    "loader_health": "OK",
    "bpf_programs": "cgroup_skb_egress_enforce tag abc",
    "enforcement_attachment": {
        "attached": True,
        "program": "cgroup_skb_egress_enforce",
        "cgroup": "/sys/fs/cgroup/vantio-enrolled.slice",
    },
    "policy_loaded": True,
    "enforce_mode": "scoped",
    "pins_current": True,
    "expected_policy_id": "--iface ens5 --enforce --cgroup-skb-enforce",
    "loaded_policy_id": "--iface ens5 --enforce --cgroup-skb-enforce",
    "deny_self_check": {
        "attempted": True,
        "enrolled_denied": True,
        "unenrolled_allowed": True,
        "mechanism": "phantom-engine",
        "hold_bypassed": True,
        "block_events": 1,
        "control_block_events": 0,
        "exception_removed": True,
        "enrolled_in_slice": True,
        "unenrolled_outside_slice": True,
    },
}
NOT_READY = {"bpf_pins": [], "loader_cmdline": "", "loader_health": "", "bpf_programs": ""}


class Rec:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str]) -> int:
        self.calls.append(list(argv))
        if len(argv) >= 2 and argv[1] in {"-C", "-N", "-D", "-X"}:
            return 1
        if "inspect" in argv:
            return 1
        if argv[:2] == ["/usr/sbin/apparmor_parser", "-V"]:
            return 1
        if argv[:2] == ["apparmor_parser", "-V"]:
            return 0 if shutil.which("apparmor_parser") else 1
        if argv[:3] == ["systemctl", "is-active", "stay-down.service"]:
            return 3
        return 0


def root_caller() -> Caller:
    return Caller(0, 10, "vantio-boot-hold", "0::/system.slice/ssh.service\n", "systemd")


def enrolled_root() -> Caller:
    return Caller(0, 11, "agent", f"0::/{SLICE}/my-agent.service\n", "systemd")


def user_caller() -> Caller:
    return Caller(1000, 12, "user", "0::/user.slice/user.service\n", "systemd")


def container_root() -> Caller:
    return Caller(0, 13, "agent", "0::/\n", "agent")


class BootHoldTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="vantio-boot-hold-"))
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))
        self.runner = Rec()
        self.caller = root_caller()
        self.python = "/usr/bin/python3"

    def test_missing_config_defaults_on(self) -> None:
        policy, notes = load_policy(self.root)
        self.assertTrue(policy["enabled"])
        self.assertTrue(policy["hold"])
        self.assertTrue(policy["ordering"])
        self.assertTrue(any("defaults" in note or "absent" in note or "stays on" in note for note in notes))
        body = status_body(self.root)
        self.assertEqual(body["reboot_row"], "NOT_PROVED")
        self.assertEqual(body["proof_state"], PROOF_STATE)
        self.assertEqual(body["proof_ceiling"], PROOF_CEILING)
        self.assertFalse(body["host_wide_default_route_hold"])
        self.assertEqual(body["state"], "CONFIGURED")

    def test_world_writable_opt_out_is_ignored(self) -> None:
        save_policy(self.root, {"enabled": False, "hold": False, "ordering": False})
        path = self.root / "etc/vantio/boot-hold.json"
        os.chmod(path, 0o666)
        policy, notes = load_policy(self.root)
        self.assertTrue(policy["enabled"])
        self.assertTrue(policy["hold"])
        self.assertTrue(any("ignored" in note for note in notes))

    def test_non_root_owned_config_is_not_trusted_on_the_host_root(self) -> None:
        path = self.root / "boot-hold.json"
        path.write_text("{}\n", encoding="utf-8")
        os.chmod(path, 0o644)
        self.assertFalse(_trusted(Path("/"), path))
        self.assertNotEqual(path.stat().st_uid, 0)

    def test_enroll_and_unenrolled_lookup(self) -> None:
        enroll_systemd(self.root, self.caller, "my-agent.service", ["/var/lib/app/secrets"], self.python)
        observe_unenrolled(self.root, self.caller, "control", "systemd")
        apply_boot(self.root, self.caller, self.runner, self.python)
        body = status_body(self.root, lookup="nobody")
        by_id = {row["id"]: row for row in body["workloads"]}
        self.assertEqual(by_id["my-agent.service"]["protection"], "HELD")
        self.assertEqual(by_id["control"]["protection"], "UNPROTECTED")
        self.assertEqual(by_id["control"]["enrolled"], "no")
        self.assertEqual(by_id["nobody"]["protection"], "UNPROTECTED")
        self.assertEqual(body["state"], "HELD")
        self.assertEqual(body["health"], "DEGRADED")
        self.assertIn("SSH", body["message"])
        dropin = (self.root / "etc/systemd/system/my-agent.service.d/vantio-boot-hold.conf").read_text(encoding="utf-8")
        self.assertIn("Slice=vantio-enrolled.slice", dropin)
        self.assertIn("InaccessiblePaths=/var/lib/app/secrets", dropin)
        self.assertIn("Requires=vantio-boot-hold.service vantio-pe-enforce-ready.service", dropin)

    def test_protected_paths_and_recovery_units(self) -> None:
        for bad in ["/", "/etc/ssh", "/root/.ssh", "/var/lib", "relative/secrets", "/var/lib/app/../secrets"]:
            with self.assertRaises(BootHoldError):
                enroll_systemd(self.root, self.caller, "my-agent.service", [bad], self.python)
        with self.assertRaises(BootHoldError):
            enroll_systemd(self.root, self.caller, "ssh.service", ["/var/lib/app/secrets"], self.python)

    def test_packet_rules_are_enrolled_only(self) -> None:
        apply_boot(self.root, self.caller, self.runner, self.python)
        blob = [" ".join(call) for call in self.runner.calls]
        joined = "\n".join(blob)
        self.assertIn("--path vantio.slice/vantio-enrolled.slice", joined)
        self.assertIn("-s 10.250.250.0/24", joined)
        self.assertIn("-s fd76:616e:7469::/64", joined)
        self.assertEqual(commands_are_scoped(self.runner.calls), [])
        self.assertNotIn("route", joined)
        self.assertNotIn("blackhole", joined)
        self.assertNotIn("0.0.0.0/0", joined)
        for call in self.runner.calls:
            self.assertNotIn("-P", call)

    def test_release_requires_ready_or_break_glass(self) -> None:
        apply_boot(self.root, self.caller, Rec(), self.python)
        fresh = Rec()
        with self.assertRaises(BootHoldError):
            release(
                self.root,
                self.caller,
                fresh,
                require_ready=False,
                break_glass=False,
                operator_flag=False,
                facts_probe=lambda: NOT_READY,
            )
        self.assertFalse(any(call[1:2] == ["-D"] for call in fresh.calls))
        audit = (self.root / "var/lib/vantio/boot-hold/audit.log").read_text(encoding="utf-8")
        self.assertIn("REFUSED", audit)

    def test_loader_failure_stays_held(self) -> None:
        apply_boot(self.root, self.caller, Rec(), self.python)
        fresh = Rec()
        with self.assertRaises(BootHoldError) as caught:
            release(
                self.root,
                self.caller,
                fresh,
                require_ready=True,
                break_glass=False,
                operator_flag=False,
                facts_probe=lambda: NOT_READY,
                wait_seconds=0,
            )
        self.assertIn("held", str(caught.exception).lower())
        body = status_body(self.root)
        self.assertEqual(body["state"], "HELD")
        self.assertEqual(body["health"], "DEGRADED")
        self.assertIn(HELD_MESSAGE, body["message"])
        self.assertFalse(any(len(call) > 1 and call[1] == "-D" for call in fresh.calls))

    def test_ready_release_and_break_glass(self) -> None:
        enroll_systemd(self.root, self.caller, "stay-down.service", ["/var/lib/app/secrets"], self.python)
        apply_boot(self.root, self.caller, Rec(), self.python)
        fresh = Rec()
        body = release(
            self.root,
            self.caller,
            fresh,
            require_ready=True,
            break_glass=False,
            operator_flag=False,
            facts_probe=lambda: READY,
        )
        self.assertEqual(body["state"], "RELEASED")
        self.assertEqual(body["reboot_row"], "NOT_PROVED")
        self.assertEqual(body["audit_reason"], "enforce-ready")
        self.assertTrue(any(call[1:2] == ["-D"] for call in fresh.calls))
        self.assertEqual(commands_are_scoped(fresh.calls), [])
        dropin = (self.root / "etc/systemd/system/stay-down.service.d/vantio-boot-hold.conf").read_text(encoding="utf-8")
        self.assertNotIn("InaccessiblePaths=", dropin)
        self.assertIn("Requires=vantio-boot-hold.service vantio-pe-enforce-ready.service", dropin)
        again = Rec()
        glass = release(
            self.root,
            self.caller,
            again,
            require_ready=False,
            break_glass=True,
            operator_flag=True,
            facts_probe=lambda: NOT_READY,
        )
        self.assertEqual(glass["audit_reason"], "BREAK_GLASS")
        self.assertEqual(glass["health"], "DEGRADED")
        self.assertIn("packet-hold-ipv4", glass["released"])
        self.assertIn("packet-hold-ipv6", glass["released"])
        self.assertIn("file-hold", glass["released"])
        self.assertIn("start-gate:stay-down.service", glass["released"])
        cleared = (self.root / "etc/systemd/system/stay-down.service.d/vantio-boot-hold.conf").read_text(encoding="utf-8")
        self.assertNotIn("vantio-pe-enforce-ready.service", cleared)
        self.assertNotIn("Requires=", cleared)
        docker_unit = (self.root / "etc/systemd/system/vantio-enrolled-docker@.service").read_text(encoding="utf-8")
        self.assertNotIn("vantio-pe-enforce-ready.service", docker_unit)
        audit = (self.root / "var/lib/vantio/boot-hold/audit.log").read_text(encoding="utf-8")
        self.assertIn("start-gate:stay-down.service", audit)
        self.assertIn("packet-hold-ipv4", audit)
        self.assertEqual(status_body(self.root)["reboot_row"], "NOT_PROVED")
        with self.assertRaises(BootHoldError):
            release(
                self.root,
                self.caller,
                Rec(),
                require_ready=False,
                break_glass=True,
                operator_flag=False,
                facts_probe=lambda: NOT_READY,
            )

    def test_enrolled_and_non_root_release_refused(self) -> None:
        apply_boot(self.root, self.caller, Rec(), self.python)
        for caller in (enrolled_root(), user_caller(), container_root()):
            with self.assertRaises(BootHoldError):
                release(
                    self.root,
                    caller,
                    Rec(),
                    require_ready=False,
                    break_glass=True,
                    operator_flag=True,
                    facts_probe=lambda: READY,
                )
        audit = (self.root / "var/lib/vantio/boot-hold/audit.log").read_text(encoding="utf-8")
        self.assertGreaterEqual(audit.count('"result": "REFUSED"'), 3)
        self.assertNotIn('"result": "BREAK_GLASS"', audit)
        self.assertEqual(status_body(self.root)["state"], "HELD")

    def test_hold_alone_ordering_alone_and_both(self) -> None:
        enroll_systemd(self.root, self.caller, "my-agent.service", ["/var/lib/app/secrets"], self.python)
        configure(self.root, self.caller, self.runner, hold=True, ordering=False, python=self.python)
        dropin = (self.root / "etc/systemd/system/my-agent.service.d/vantio-boot-hold.conf").read_text(encoding="utf-8")
        parsed = parse_unit(dropin)
        requires = parsed["Unit"].get("Requires", [])
        self.assertIn("vantio-boot-hold.service", requires)
        self.assertNotIn("vantio-pe-enforce-ready.service", requires)
        self.assertIn("InaccessiblePaths=/var/lib/app/secrets", dropin)
        self.assertTrue(any(call[1:2] == ["-I"] for call in self.runner.calls))
        units = static_units(self.python, {"enabled": True, "hold": True, "ordering": False, **{k: default_policy()[k] for k in ("cgroup_slice", "enrolled_subnet_v4", "enrolled_subnet_v6")}})
        self.assertEqual(graph_errors(units, ordering=False, hold=True), [])

        ordering_runner = Rec()
        configure(self.root, self.caller, ordering_runner, hold=False, ordering=True, python=self.python)
        self.assertFalse(any(call[1:2] == ["-I"] for call in ordering_runner.calls))
        dropin = (self.root / "etc/systemd/system/my-agent.service.d/vantio-boot-hold.conf").read_text(encoding="utf-8")
        self.assertNotIn("InaccessiblePaths=", dropin)
        self.assertIn("vantio-pe-enforce-ready.service", parse_unit(dropin)["Unit"].get("Requires", []))
        off_units = static_units(self.python, load_policy(self.root)[0])
        self.assertEqual(graph_errors(off_units, ordering=True, hold=False), [])

        both = Rec()
        configure(self.root, self.caller, both, hold=True, ordering=True, python=self.python)
        self.assertTrue(any("--path" in call and any("vantio-enrolled.slice" in part for part in call) for call in both.calls))
        both_units = static_units(self.python, default_policy())
        self.assertEqual(graph_errors(both_units, ordering=True, hold=True), [])
        with self.assertRaises(BootHoldError):
            configure(self.root, self.caller, Rec(), hold=False, ordering=False, python=self.python)

    def test_docker_restart_policy_and_cgroup_parent(self) -> None:
        with self.assertRaises(BootHoldError):
            enroll_docker(
                self.root,
                self.caller,
                "agent",
                "always",
                "/vantio-enrolled.slice",
                ["/var/lib/app/secrets"],
                self.python,
                set_restart_no=False,
                runner=Rec(),
            )
        body = enroll_docker(
            self.root,
            self.caller,
            "agent",
            "always",
            "/vantio-enrolled.slice",
            ["/var/lib/app/secrets"],
            self.python,
            set_restart_no=True,
            runner=self.runner,
        )
        self.assertEqual(body["state"], "ENROLLED")
        self.assertIn(["docker", "update", "--restart=no", "agent"], self.runner.calls)
        unit = (self.root / "etc/systemd/system/vantio-enrolled-docker@.service").read_text(encoding="utf-8")
        self.assertIn("Requires=docker.service vantio-enrolled-network.service vantio-boot-hold.service vantio-pe-enforce-ready.service", unit)
        self.assertIn("ExecStart=/usr/bin/docker start %i", unit)
        with self.assertRaises(BootHoldError):
            enroll_docker(
                self.root,
                self.caller,
                "other",
                "no",
                "/system.slice",
                [],
                self.python,
                set_restart_no=False,
                runner=Rec(),
            )

    def test_compose_enroll_refuses_restart_always(self) -> None:
        with self.assertRaises(BootHoldError):
            enroll_compose(self.root, self.caller, "/var/lib/app/compose", "restart: always\n", self.python)
        text = "\n".join(
            [
                "services:",
                "  agent:",
                "    restart: \"no\"",
                "    cgroup_parent: /vantio-enrolled.slice",
                "    security_opt:",
                "      - apparmor:vantio-boot-hold",
                "networks:",
                "  enrolled:",
                "    subnet: 10.250.250.0/24",
            ]
        )
        body = enroll_compose(self.root, self.caller, "/var/lib/app/compose", text, self.python)
        self.assertEqual(body["state"], "ENROLLED")
        unit = (self.root / "etc/systemd/system/vantio-enrolled-compose-compose.service").read_text(encoding="utf-8")
        self.assertIn("ExecStart=/usr/bin/docker compose start", unit)
        self.assertIn("vantio-pe-enforce-ready.service", parse_unit(unit)["Unit"].get("Requires", []))

    def test_packaged_units_match_the_renderer(self) -> None:
        rendered = static_units("/usr/bin/python3", default_policy())
        mapping = {
            "etc/systemd/system/vantio-boot-hold.service": "vantio-boot-hold.service",
            "etc/systemd/system/vantio-pe-loader.service": "vantio-pe-loader.service",
            "etc/systemd/system/vantio-pe-enforce-ready.service": "vantio-pe-enforce-ready.service",
            "etc/systemd/system/vantio-enrolled.slice": "vantio-enrolled.slice",
            "etc/systemd/system/vantio-enrolled-docker@.service": "vantio-enrolled-docker@.service",
            "etc/systemd/system/vantio-enrolled-network.service": "vantio-enrolled-network.service",
            "etc/systemd/system/docker.service.d/vantio-boot-hold.conf": "docker.service.d-vantio-boot-hold.conf",
            "etc/systemd/system/containerd.service.d/vantio-boot-hold.conf": "containerd.service.d-vantio-boot-hold.conf",
        }
        base = PACKAGE / "packaging/boot-hold"
        for rel, name in mapping.items():
            self.assertEqual((base / name).read_text(encoding="utf-8"), rendered[rel], name)

    def test_graph_keeps_ssh_off_the_hold(self) -> None:
        units = static_units(self.python, default_policy())
        self.assertEqual(graph_errors(units), [])
        hold = units["etc/systemd/system/vantio-boot-hold.service"]
        self.assertIn("Before=docker.service containerd.service", hold)
        self.assertIn("Environment=VANTIO_BOOT_HOLD_LIVE=1", hold)
        self.assertIn("Environment=VANTIO_BOOT_HOLD_LIVE=1", units["etc/systemd/system/vantio-pe-loader.service"])
        self.assertIn("Environment=VANTIO_BOOT_HOLD_LIVE=1", units["etc/systemd/system/vantio-pe-enforce-ready.service"])
        self.assertNotIn("ssh.service", hold)
        self.assertNotIn("systemd-networkd.service", hold)
        docker_dropin = parse_unit(units["etc/systemd/system/docker.service.d/vantio-boot-hold.conf"])
        self.assertEqual(docker_dropin["Unit"].get("Requires", []), [])
        ready = units["etc/systemd/system/vantio-pe-enforce-ready.service"]
        self.assertIn("--require-enforce-ready", ready)
        self.assertIn("Requires=vantio-pe-loader.service", ready)
        loader = units["etc/systemd/system/vantio-pe-loader.service"]
        self.assertIn("After=local-fs.target apparmor.service vantio-boot-hold.service docker.service", loader)
        self.assertIn("Restart=on-failure", loader)
        self.assertIn("StartLimitBurst=5", loader)
        self.assertNotIn("Restart=no", loader)
        self.assertIn("vantio-boot-hold.service", loader)

    def test_loader_argv_missing_does_not_release(self) -> None:
        apply_boot(self.root, self.caller, Rec(), self.python)
        with self.assertRaises(BootHoldError) as caught:
            loader_argv(self.root)
        self.assertIn("stay held", str(caught.exception))
        self.assertEqual(status_body(self.root)["state"], "HELD")

    def test_opt_out_is_logged_and_visible(self) -> None:
        apply_boot(self.root, self.caller, Rec(), self.python)
        body = opt_out(self.root, self.caller, Rec(), "maintenance window", self.python)
        self.assertEqual(body["state"], "OPTED_OUT")
        self.assertEqual(status_body(self.root)["health"], "OPTED_OUT")
        audit = (self.root / "var/lib/vantio/boot-hold/audit.log").read_text(encoding="utf-8")
        self.assertIn("opt-out", audit)
        self.assertIn("maintenance window", audit)
        mode = stat.S_IMODE((self.root / "etc/vantio/boot-hold.json").stat().st_mode)
        self.assertEqual(mode & 0o022, 0)

    def test_running_loader_without_attachment_stays_held(self) -> None:
        unattached = dict(READY)
        unattached["enforcement_attachment"] = {"attached": False, "program": "", "cgroup": ""}
        verdict = evaluate_ready(unattached)
        self.assertFalse(verdict["enforce_ready"])
        self.assertEqual(verdict["reason"], "loader-running-not-attached")
        self.assertTrue(verdict["loader_up"])
        self.assertTrue(verdict["program_loaded"])
        apply_boot(self.root, self.caller, Rec(), self.python)
        with self.assertRaises(BootHoldError) as caught:
            release(
                self.root,
                self.caller,
                Rec(),
                require_ready=True,
                break_glass=False,
                operator_flag=False,
                facts_probe=lambda: unattached,
            )
        self.assertIn("not attached", str(caught.exception))
        self.assertEqual(status_body(self.root)["state"], "HELD")
        no_deny = dict(READY)
        no_deny["deny_self_check"] = dict(READY["deny_self_check"])
        no_deny["deny_self_check"]["enrolled_denied"] = False
        self.assertEqual(evaluate_ready(no_deny)["reason"], "deny-self-check-failed")
        self.assertFalse(evaluate_ready(no_deny)["enforce_ready"])

    def test_deny_self_check_requires_both_paths(self) -> None:
        calls: list[list[str]] = []

        def runner(argv: list[str]) -> int:
            calls.append(list(argv))
            if argv[:2] == ["iptables", "-I"]:
                return 0
            if "--slice" in argv and "vantio-enrolled.slice" in argv:
                return 1
            if "--slice" in argv and "system.slice" in argv:
                return 0
            return 0

        result = perform_deny_self_check(runner, host="192.0.2.1", port=443, attached=True)
        self.assertTrue(result["hold_bypassed"])
        self.assertTrue(result["enrolled_denied"])
        self.assertTrue(result["unenrolled_allowed"])
        self.assertTrue(any(call[0] == "iptables" and "-D" in call for call in calls))
        self.assertTrue(any(call[0] == "iptables" and "RETURN" in call and "VANTIO_BOOT_HOLD" in call for call in calls))
        self.assertFalse(any("OUTPUT" in call for call in calls if call and call[0] == "iptables"))
        before = len(calls)
        skipped = perform_deny_self_check(runner, host="192.0.2.1", port=443, attached=False)
        self.assertFalse(skipped["hold_bypassed"])
        self.assertEqual(len(calls), before)

    def test_apply_enables_hold_and_keeps_opt_out(self) -> None:
        body = enable_from_apply(self.root, self.caller, self.runner, self.python)
        self.assertEqual(body["state"], "HELD")
        unit = self.root / "etc/systemd/system/vantio-boot-hold.service"
        link = self.root / "etc/systemd/system/sysinit.target.wants/vantio-boot-hold.service"
        self.assertTrue(unit.is_file())
        self.assertTrue(link.is_symlink())
        self.assertTrue(any("--path" in call and any("vantio-enrolled.slice" in part for part in call) for call in self.runner.calls))
        opted = self.root / "opt-out-host"
        save_policy(opted, {"enabled": False, "hold": True, "ordering": True})
        quiet = Rec()
        again = enable_from_apply(opted, self.caller, quiet, self.python)
        self.assertNotEqual(again["state"], "HELD")
        self.assertFalse(any(len(call) > 1 and call[1] == "-I" for call in quiet.calls))
        self.assertFalse(json.loads((opted / "etc/vantio/boot-hold.json").read_text(encoding="utf-8"))["enabled"])
        self.assertEqual(status_body(opted)["health"], "OPTED_OUT")

    def test_evaluate_ready_rejects_partial_facts(self) -> None:
        self.assertTrue(evaluate_ready(READY)["enforce_ready"])
        almost = dict(READY)
        almost["bpf_programs"] = ""
        self.assertFalse(evaluate_ready(almost)["enforce_ready"])
        almost = dict(READY)
        almost["loader_cmdline"] = "/vantio-loader --iface ens5"
        self.assertFalse(evaluate_ready(almost)["enforce_ready"])
        proc = self.root / "proc/4242"
        proc.mkdir(parents=True)
        (proc / "cmdline").write_bytes(b"/vantio-loader\x00--enforce\x00")
        (proc / "stat").write_text("4242 (vantio-loader) S 1 1 1\n", encoding="utf-8")
        cmdline, health = probe_loader(self.root)
        self.assertIn("--enforce", cmdline)
        self.assertEqual(health, "OK")

    def test_profile_denies_only_the_protected_path(self) -> None:
        text = deny_profile(["/var/lib/app/secrets"])
        self.assertIn("deny /var/lib/app/secrets rwmlkx,", text)
        self.assertNotIn("/etc/ssh", text)
        self.assertIn("profile vantio-boot-hold", allow_profile())
        self.assertNotIn("deny ", allow_profile())
        if shutil.which("apparmor_parser"):
            path = self.root / "profile"
            path.write_text(text, encoding="utf-8")
            completed = subprocess.run(
                ["apparmor_parser", "-Q", "-K", "-T", str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_docs_and_lab_procedure(self) -> None:
        doc = (PACKAGE / "docs/BOOT-HOLD.md").read_text(encoding="utf-8")
        for needle in (
            "--cgroup-parent=/vantio-enrolled.slice",
            "--restart=no",
            "apparmor=vantio-boot-hold",
            "10.250.250.0/24",
            "Slice=vantio-enrolled.slice",
            "vantio-pe-enforce-ready.service",
            "docker compose start",
            "NOT_PROVED",
            "--break-glass --i-am-root-operator",
            "observe-unenrolled",
        ):
            self.assertIn(needle, doc)
        self.assertNotIn("/home/vantioai", doc)
        lab = (REPO / "docs/planning/boot-hold/FD-REBOOT-1-LAB-PROCEDURE.md").read_text(encoding="utf-8")
        for needle in (
            "960577828987",
            "expected_oop_usd=0",
            "NOT_PROVED",
            "Hold alone",
            "Ordering alone",
            "Both together",
            "5+",
            "from t=0",
            "BREAK_GLASS",
            "restart",
            "unenrolled",
            "SSH",
            "Unknown is never PASS",
            "e0b19d55",
            "INTERNAL_CLEAN_HOST_PROOF",
            "t3.small",
        ):
            self.assertIn(needle, lab)
        companion = (REPO / "docs/planning/boot-hold/PE-COMPANION.md").read_text(encoding="utf-8")
        self.assertIn("resolve_cgroup_spec", companion)
        self.assertIn("/sys/fs/cgroup/vantio-enrolled.slice", companion)
        self.assertIn("does not invent a seal", companion)

    def test_cli_refuses_enrolled_identity(self) -> None:
        fixture = self.root / "caller.json"
        fixture.write_text(
            json.dumps(
                {
                    "euid": 0,
                    "pid": 50,
                    "comm": "agent",
                    "cgroup_text": f"0::/{SLICE}/job.service",
                    "pid1_comm": "systemd",
                }
            ),
            encoding="utf-8",
        )
        env_keys = {
            "VANTIO_BOOT_HOLD_ALLOW_CALLER_FIXTURE": "1",
            "VANTIO_BOOT_HOLD_CALLER_FIXTURE": str(fixture),
        }
        previous = {key: os.environ.get(key) for key in env_keys}
        os.environ.update(env_keys)
        self.addCleanup(lambda: _restore_env(previous))
        buffer = StringIO()
        with redirect_stdout(buffer):
            code = main(["release", "--root", str(self.root), "--break-glass", "--i-am-root-operator"])
        self.assertNotEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["state"], "FAILED_SAFE")
        self.assertEqual(payload["reboot_row"], "NOT_PROVED")
        self.assertIn("enrolled workload", payload["message"])
        audit = (self.root / "var/lib/vantio/boot-hold/audit.log").read_text(encoding="utf-8")
        self.assertIn("REFUSED", audit)


class EnforceReadyRegressions(unittest.TestCase):
    def _check(self, *, enrolled_rc: int, unenrolled_rc: int, before: str, mid: str, after: str, enrolled_cg: str, unenrolled_cg: str) -> dict:
        snapshots = [before, mid, after]

        def events() -> str:
            return snapshots.pop(0)

        def reader(marker: str) -> str:
            return enrolled_cg if marker == "enrolled" else unenrolled_cg

        def runner(argv: list[str]) -> int:
            if argv[:2] == ["iptables", "-I"]:
                return 0
            if argv[:2] == ["iptables", "-D"]:
                return 0
            if "--slice" in argv and "vantio-enrolled.slice" in argv:
                return enrolled_rc
            if "--slice" in argv and "system.slice" in argv:
                return unenrolled_rc
            return 1

        return perform_deny_self_check(
            runner,
            host="198.51.100.2",
            port=18080,
            attached=True,
            events=events,
            cgroup_reader=reader,
        )

    def test_probe_outside_enrolled_does_not_pass(self) -> None:
        result = self._check(
            enrolled_rc=1,
            unenrolled_rc=0,
            before="",
            mid="1  CG/SKB  BLOCKED  60 B",
            after="1  CG/SKB  BLOCKED  60 B",
            enrolled_cg="0::/system.slice/ssh.service",
            unenrolled_cg="0::/system.slice/ssh.service",
        )
        self.assertEqual(result["mechanism"], "probe-outside-enrolled")
        self.assertFalse(evaluate_ready({**READY, "deny_self_check": result})["enforce_ready"])

    def test_probe_inside_enrolled_with_event_passes(self) -> None:
        line = "9  0x1  CG/SKB   BLOCKED         60 B  1"
        result = self._check(
            enrolled_rc=1,
            unenrolled_rc=0,
            before="old  CG/SKB   BLOCKED         60 B  0",
            mid="old  CG/SKB   BLOCKED         60 B  0\n" + line,
            after="old  CG/SKB   BLOCKED         60 B  0\n" + line,
            enrolled_cg="0::/vantio-enrolled.slice/run.scope",
            unenrolled_cg="0::/system.slice/run.scope",
        )
        self.assertEqual(result["mechanism"], "phantom-engine")
        self.assertEqual(result["block_events"], 1)
        self.assertTrue(evaluate_ready({**READY, "deny_self_check": result})["enforce_ready"])

    def test_policy_absent_stays_unready(self) -> None:
        facts = dict(READY)
        facts["policy_loaded"] = False
        self.assertFalse(evaluate_ready(facts)["enforce_ready"])

    def test_wrong_policy_version_stays_unready(self) -> None:
        facts = dict(READY)
        facts["loaded_policy_id"] = "--iface ens5 --enforce"
        verdict = evaluate_ready(facts)
        self.assertFalse(verdict["enforce_ready"])
        self.assertEqual(verdict["reason"], "policy-version-mismatch")

    def test_wrong_dest_is_control_unreachable(self) -> None:
        result = self._check(
            enrolled_rc=1,
            unenrolled_rc=1,
            before="",
            mid="1  CG/SKB  BLOCKED  60 B",
            after="1  CG/SKB  BLOCKED  60 B",
            enrolled_cg="0::/vantio-enrolled.slice",
            unenrolled_cg="0::/system.slice",
        )
        self.assertEqual(result["mechanism"], "control-unreachable")
        self.assertFalse(evaluate_ready({**READY, "deny_self_check": result})["enforce_ready"])

    def test_audit_mode_is_not_enforce(self) -> None:
        facts = dict(READY)
        facts["enforce_mode"] = "audit"
        facts["loader_cmdline"] = "/vantio-loader --iface ens5"
        verdict = evaluate_ready(facts)
        self.assertEqual(verdict["reason"], "audit-not-enforce")
        self.assertFalse(verdict["enforce_ready"])

    def test_boot_hold_timeout_without_event_does_not_pass(self) -> None:
        result = self._check(
            enrolled_rc=1,
            unenrolled_rc=0,
            before="",
            mid="",
            after="",
            enrolled_cg="0::/vantio-enrolled.slice",
            unenrolled_cg="0::/system.slice",
        )
        self.assertEqual(result["mechanism"], "unattributed-timeout")
        self.assertEqual(result["block_events"], 0)
        self.assertFalse(evaluate_ready({**READY, "deny_self_check": result})["enforce_ready"])

    def test_stale_block_line_does_not_count(self) -> None:
        stale = "1  CG/SKB  BLOCKED  60 B"
        self.assertEqual(new_block_count(stale, stale), 0)
        result = self._check(
            enrolled_rc=1,
            unenrolled_rc=0,
            before=stale,
            mid=stale,
            after=stale,
            enrolled_cg="0::/vantio-enrolled.slice",
            unenrolled_cg="0::/system.slice",
        )
        self.assertEqual(result["mechanism"], "unattributed-timeout")

    def test_unenrolled_control_must_be_allowed(self) -> None:
        result = self._check(
            enrolled_rc=1,
            unenrolled_rc=1,
            before="",
            mid='{"EventType":"CGROUP_BLOCK","ActionTaken":"BLOCKED"}',
            after='{"EventType":"CGROUP_BLOCK","ActionTaken":"BLOCKED"}',
            enrolled_cg="0::/vantio-enrolled.slice",
            unenrolled_cg="0::/system.slice",
        )
        self.assertFalse(result["unenrolled_allowed"])
        self.assertNotEqual(result["mechanism"], "phantom-engine")

    def test_delayed_attachment_then_ready(self) -> None:
        waiting = dict(READY)
        waiting["enforcement_attachment"] = {"attached": False, "program": "", "cgroup": ""}
        self.assertEqual(evaluate_ready(waiting)["reason"], "loader-running-not-attached")
        self.assertTrue(evaluate_ready(READY)["enforce_ready"])

    def test_attached_without_policy_stays_unready(self) -> None:
        facts = dict(READY)
        facts["policy_loaded"] = False
        facts["bpf_pins"] = []
        verdict = evaluate_ready(facts)
        self.assertTrue(verdict["program_attached"])
        self.assertFalse(verdict["enforce_ready"])

    def test_attached_policy_and_unenrolled_probe_stays_unready(self) -> None:
        result = self._check(
            enrolled_rc=0,
            unenrolled_rc=0,
            before="",
            mid="",
            after="",
            enrolled_cg="0::/user.slice/session.scope",
            unenrolled_cg="0::/system.slice",
        )
        self.assertEqual(result["mechanism"], "probe-outside-enrolled")
        facts = dict(READY)
        facts["deny_self_check"] = result
        self.assertFalse(evaluate_ready(facts)["enforce_ready"])

    def test_lifecycle_keeps_observe_separate(self) -> None:
        self.assertEqual(enforcement_lifecycle(observe_ready=True), "OBSERVE_READY")
        self.assertEqual(
            enforcement_lifecycle(observe_ready=True, ready={"enforce_ready": True}),
            "ENFORCEMENT_READY",
        )
        self.assertEqual(enforcement_lifecycle(hold_active=True), "HELD")
        self.assertEqual(
            enforcement_lifecycle(hold_active=True, ready={"loader_up": True, "program_attached": True}),
            "ENFORCEMENT_ATTACHED_NOT_PROVED",
        )
        self.assertEqual(
            enforcement_lifecycle(ready={"loader_up": True, "program_loaded": False}),
            "ENFORCEMENT_LOADING",
        )
        self.assertEqual(enforcement_lifecycle(break_glass=True, ready={"enforce_ready": True}), "BREAK_GLASS")
        self.assertEqual(enforcement_lifecycle(opted_out=True), "OPTED_OUT")
        self.assertEqual(enforcement_lifecycle(failed_safe=True, opted_out=True), "FAILED_SAFE")
        self.assertEqual(enforcement_lifecycle(), "DEGRADED")

    def test_prepare_enforce_keeps_the_slice_out_of_the_container(self) -> None:
        argv = enforce_container_argv(tag="vantio-phantom-engine:pe-residuals-06696d5", iface="ens5", name="vantio-pe")
        self.assertIn("--cgroupns", argv)
        self.assertIn("host", argv)
        self.assertIn("/sys/fs/cgroup:/sys/fs/cgroup", argv)
        self.assertIn("--cgroup-skb-enforce", argv)
        self.assertIn("--output-file", argv)
        self.assertIn("/var/lib/vantio/pe-events/events.ndjson", argv)
        self.assertIn("--startup-enroll-cgroup", argv)
        self.assertNotIn("--cgroup-parent", argv)
        self.assertNotIn("--privileged", argv)
        calls: list[list[str]] = []

        def docker_run(argv_in: list[str]) -> int:
            calls.append(list(argv_in))
            return 0

        body = prepare_enforce(
            self_root(),
            Caller(euid=0, pid=1, comm="test", cgroup_text="0::/system.slice", pid1_comm="systemd"),
            iface="ens5",
            name="vantio-pe",
            observe_name="",
            docker_run=docker_run,
        )
        self.assertEqual(body["enforcement_lifecycle"], "ENFORCEMENT_LOADING")
        self.assertFalse(body["protected"])
        self.assertEqual(body["state"], "HELD")
        self.assertEqual(calls[0][0], "docker")
        self.assertIn("--cgroup-skb-enforce", calls[0])

    def test_scoped_banner_without_attach_line_is_not_attachment(self) -> None:
        log = "tc enforce : SCOPED (drop enrolled) iface 'ens5'\nPath enforce maps loaded: 1 exact\n"
        self.assertFalse(attachment_from_log(log)["attached"])
        attached = attachment_from_log(
            "cgroup_skb: attached to cgroup id=1 path=/sys/fs/cgroup/vantio-enrolled.slice\n"
        )
        self.assertTrue(attached["attached"])
        self.assertEqual(attached["program"], "cgroup_skb_egress_enforce")

    def test_probe_interface_names_fit_ifnamesiz(self) -> None:
        self.assertLessEqual(len(HOST_IFACE), 15)
        self.assertLessEqual(len(PEER_IFACE), 15)

    def test_stale_loader_log_is_not_attachment_without_a_process(self) -> None:
        root = self_root()
        log = "\n".join(
            [
                "tc enforce : SCOPED (drop enrolled) iface 'ens5'",
                "Path enforce maps loaded: 1 exact",
                "cgroup_skb: attached to cgroup id=1 path=/sys/fs/cgroup/vantio.slice/vantio-enrolled.slice",
            ]
        )
        facts = assemble_host_facts(
            root,
            prog_show="",
            cgroup_show="",
            map_show="",
            loader_log=log,
            pins_current=False,
        )
        self.assertEqual(facts["loader_cmdline"], "")
        self.assertFalse(facts["enforcement_attachment"]["attached"])
        self.assertEqual(facts["enforce_mode"], "")
        self.assertNotIn("cgroup_skb_egress_enforce", facts["bpf_programs"])
        self.assertFalse(facts["policy_loaded"])
        verdict = evaluate_ready(facts)
        self.assertFalse(verdict["enforce_ready"])
        self.assertFalse(verdict["program_attached"])
        self.assertFalse(verdict["loader_up"])

    def test_live_loader_still_accepts_the_attach_line(self) -> None:
        root = self_root()
        proc = root / "proc" / "42"
        proc.mkdir(parents=True)
        (proc / "cmdline").write_bytes(b"/vantio-loader\x00--enforce\x00--iface\x00ens5\x00")
        (proc / "stat").write_text("42 (vantio-loader) S 1 1 1\n", encoding="utf-8")
        log = "cgroup_skb: attached to cgroup id=1 path=/sys/fs/cgroup/vantio.slice/vantio-enrolled.slice\n"
        facts = assemble_host_facts(root, prog_show="", cgroup_show="", map_show="", loader_log=log)
        self.assertTrue(facts["enforcement_attachment"]["attached"])
        self.assertIn("vantio-loader", facts["loader_cmdline"])

    def test_reboot_reloads_the_durable_observe_profile(self) -> None:
        root = self_root()
        stage = root / "var/lib/vantio/pe-stage"
        profile = stage / "apparmor" / "vantio-pe-observe"
        profile.parent.mkdir(parents=True)
        profile.write_text(profile_text(), encoding="utf-8")
        config = root / "var/lib/vantio/config"
        config.mkdir(parents=True)
        (config / "observe.json").write_text(
            json.dumps({"stage_dir": "/var/lib/vantio/pe-stage"}),
            encoding="utf-8",
        )
        calls: list[list[str]] = []

        def runner(argv: list[str]) -> int:
            calls.append(list(argv))
            return 0

        body = reload_observe_profile(root, runner)
        self.assertTrue(body["loaded"])
        self.assertEqual(calls, [["apparmor_parser", "-Kr", str(profile)]])
        self.assertEqual(observe_profile_path(root), profile)

    def test_profile_reload_refuses_a_symlink_or_a_changed_profile(self) -> None:
        root = self_root()
        stage = root / "var/lib/vantio/pe-stage" / "apparmor"
        stage.mkdir(parents=True)
        target = root / "other-profile"
        target.write_text(profile_text(), encoding="utf-8")
        link = stage / "vantio-pe-observe"
        link.symlink_to(target)
        with self.assertRaises(BootHoldError) as missing:
            reload_observe_profile(root, lambda _argv: 0)
        self.assertIn("not on disk", str(missing.exception))
        link.unlink()
        link.write_text(profile_text() + "\n# changed\n", encoding="utf-8")
        with self.assertRaises(BootHoldError) as changed:
            reload_observe_profile(root, lambda _argv: 0)
        self.assertIn("does not match", str(changed.exception))

    def test_profile_reload_failure_does_not_count_as_loaded(self) -> None:
        root = self_root()
        profile = root / "var/lib/vantio/pe-stage" / "apparmor" / "vantio-pe-observe"
        profile.parent.mkdir(parents=True)
        profile.write_text(profile_text(), encoding="utf-8")
        with self.assertRaises(BootHoldError) as caught:
            reload_observe_profile(root, lambda _argv: 1)
        self.assertIn("did not load", str(caught.exception))
        self.assertEqual(caught.exception.state, "HELD")

    def test_policy_id_ignores_unrelated_flags(self) -> None:
        self.assertEqual(
            policy_id_from_cmdline("/vantio-loader --iface ens5 --enforce --cgroup-skb-enforce --startup-enroll-cgroup /sys/fs/cgroup/vantio-enrolled.slice"),
            "--iface ens5 --enforce --cgroup-skb-enforce --startup-enroll-cgroup /sys/fs/cgroup/vantio-enrolled.slice",
        )


def self_root() -> Path:
    path = Path(tempfile.mkdtemp(prefix="vantio-prepare-"))
    return path


def _restore_env(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
