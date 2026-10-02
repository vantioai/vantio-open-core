"""Observe host check: a stopped container is not a detached loader."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from vantio_install import constants  # noqa: E402
from vantio_install.observe_health import (  # noqa: E402
    OBSERVE_READY_WAIT_S,
    egress_program_attached,
    facts_from_logs,
    host_check_failure_text,
    observe_lifecycle,
    parse_docker_time,
    pins_are_current,
    readiness_gaps,
    ready_observe_sample,
    wait_for_observe_host,
)
from vantio_install.pe_apparmor import OBSERVE_INSPECT_FORMAT, parse_observe_inspect  # noqa: E402

CMD = '["--iface","ens5"]'


def line(status: str, pid: int, running: str, privileged: str, profile: str = "vantio-pe-observe") -> str:
    return f"{status} {pid} {running} {privileged} {profile} {CMD}"


def sample(**overrides: object) -> dict:
    base = ready_observe_sample()
    base.update(overrides)
    return base


class ObserveHealthTests(unittest.TestCase):
    def test_inspect_format_records_status_and_pid(self) -> None:
        self.assertIn("{{.State.Status}}", OBSERVE_INSPECT_FORMAT)
        self.assertIn("{{.State.Pid}}", OBSERVE_INSPECT_FORMAT)
        self.assertLess(OBSERVE_INSPECT_FORMAT.index("Status"), OBSERVE_INSPECT_FORMAT.index("Pid"))

    def test_exit_zero_shape_splits_stopped_from_detached(self) -> None:
        stopped = parse_observe_inspect(line("exited", 0, "false", "false"))
        detached = parse_observe_inspect(line("running", 4242, "true", "false"))
        created = parse_observe_inspect(line("created", 0, "false", "false"))
        self.assertEqual(observe_lifecycle(stopped), "stopped")
        self.assertEqual(observe_lifecycle(detached), "detached")
        self.assertEqual(observe_lifecycle(created), "starting")
        self.assertEqual(stopped["pid"], 0)
        self.assertGreater(detached["pid"], 0)

    def test_stopped_container_is_not_verified(self) -> None:
        calls = {"n": 0}

        def read() -> dict:
            calls["n"] += 1
            return sample(lifecycle="stopped", security_ok=False)

        status = wait_for_observe_host(
            read,
            wait_s=20,
            poll_s=0.25,
            clock=lambda: 0.0,
            sleeper=lambda _seconds: (_ for _ in ()).throw(AssertionError("slept")),
        )
        self.assertEqual(status, "NOT_VERIFIED")
        self.assertEqual(calls["n"], 1)

    def test_detached_container_is_verified_once_the_loader_is_healthy(self) -> None:
        reads = [
            sample(pins=list(constants.BPF_PINS)[:2], loader=False),
            sample(),
        ]

        def read() -> dict:
            return reads.pop(0)

        times = iter((0.0, 0.4))
        status = wait_for_observe_host(
            read,
            wait_s=20,
            poll_s=0.25,
            clock=lambda: next(times),
            sleeper=lambda _seconds: None,
        )
        self.assertEqual(status, "VERIFIED")
        self.assertEqual(reads, [])

    def test_created_container_can_become_a_healthy_detached_loader(self) -> None:
        reads = [sample(lifecycle="starting", security_ok=False, pins=[], loader=False), sample()]

        def read() -> dict:
            return reads.pop(0)

        times = iter((0.0, 1.0))
        status = wait_for_observe_host(
            read,
            wait_s=20,
            poll_s=0.25,
            clock=lambda: next(times),
            sleeper=lambda _seconds: None,
        )
        self.assertEqual(status, "VERIFIED")

    def test_detached_container_that_never_loads_is_not_verified(self) -> None:
        def read() -> dict:
            return sample(pins=[], loader=False, clsact=False)

        times = iter((0.0, 20.0))
        status = wait_for_observe_host(
            read,
            wait_s=20,
            poll_s=0.25,
            clock=lambda: next(times),
            sleeper=lambda _seconds: None,
        )
        self.assertEqual(status, "NOT_VERIFIED")

    def test_unreadable_pins_stay_unknown(self) -> None:
        def read() -> dict:
            return sample(pins_error=True, pins=[])

        status = wait_for_observe_host(
            read,
            wait_s=20,
            poll_s=0.25,
            clock=lambda: 0.0,
            sleeper=lambda _seconds: (_ for _ in ()).throw(AssertionError("slept")),
        )
        self.assertEqual(status, "UNKNOWN")

    def test_wait_bound_stays_twenty_seconds(self) -> None:
        self.assertEqual(OBSERVE_READY_WAIT_S, 20.0)

    def test_healthy_persistent_loader_is_verified_without_waiting(self) -> None:
        status = wait_for_observe_host(
            ready_observe_sample,
            wait_s=20,
            poll_s=0.25,
            clock=lambda: 0.0,
            sleeper=lambda _seconds: (_ for _ in ()).throw(AssertionError("slept")),
        )
        self.assertEqual(status, "VERIFIED")
        self.assertEqual(readiness_gaps(ready_observe_sample()), [])

    def test_bootstrap_exit_is_not_a_supported_contract(self) -> None:
        stopped = sample(
            lifecycle="stopped",
            security_ok=False,
            self_check=True,
            exit_code=0,
        )
        status = wait_for_observe_host(
            lambda: stopped,
            wait_s=20,
            poll_s=0.25,
            clock=lambda: 0.0,
            sleeper=lambda _seconds: (_ for _ in ()).throw(AssertionError("slept")),
        )
        self.assertEqual(status, "NOT_VERIFIED")
        self.assertIn("container-stopped", readiness_gaps(stopped))
        self.assertIn("exit-code-0", readiness_gaps(stopped))

    def test_exit_zero_before_attachment_is_not_verified(self) -> None:
        early = sample(pins=[], pins_current=False, loader=False, programs=False, paths_active=False, self_check=False)
        times = iter((0.0, 20.0))
        status = wait_for_observe_host(
            lambda: early,
            wait_s=20,
            poll_s=0.25,
            clock=lambda: next(times),
            sleeper=lambda _seconds: None,
        )
        self.assertEqual(status, "NOT_VERIFIED")
        gaps = readiness_gaps(early)
        self.assertTrue(any(item.startswith("pins-missing:") for item in gaps))
        self.assertIn("tc-program-missing", gaps)
        self.assertIn("Rollback is required.", host_check_failure_text("start_pe_observe", early))

    def test_partial_attachment_is_not_verified(self) -> None:
        partial = sample(programs=False, paths_active=False)
        self.assertIn("tc-program-missing", readiness_gaps(partial))
        self.assertIn("file-paths-not-loaded", readiness_gaps(partial))
        self.assertNotEqual(readiness_gaps(partial), [])

    def test_stale_pins_are_not_ready(self) -> None:
        stale = sample(pins_current=False)
        self.assertEqual(readiness_gaps(stale), ["pins-stale"])
        started = parse_docker_time("2026-09-28T04:21:20.81983403Z")
        self.assertIsNotNone(started)
        assert started is not None
        self.assertFalse(pins_are_current([started - 30] * len(constants.BPF_PINS), started))
        self.assertTrue(pins_are_current([started + 1] * len(constants.BPF_PINS), started))

    def test_wrong_interface_is_not_ready(self) -> None:
        wrong = sample(iface_ok=False, clsact=False)
        gaps = readiness_gaps(wrong)
        self.assertIn("iface-mismatch", gaps)
        self.assertIn("clsact-missing", gaps)
        logs = _active_log("eth0")
        self.assertFalse(facts_from_logs(logs, "ens5")["iface_ok"])
        self.assertTrue(facts_from_logs(logs, "eth0")["iface_ok"])

    def test_delayed_readiness_verifies_before_the_bound(self) -> None:
        reads = [
            sample(self_check=False, programs=False, paths_active=False),
            ready_observe_sample(),
        ]

        def read() -> dict:
            return reads.pop(0)

        times = iter((0.0, 1.0))
        status = wait_for_observe_host(
            read,
            wait_s=20,
            poll_s=0.25,
            clock=lambda: next(times),
            sleeper=lambda _seconds: None,
        )
        self.assertEqual(status, "VERIFIED")
        self.assertEqual(reads, [])

    def test_loader_crash_does_not_wait(self) -> None:
        crashed = sample(lifecycle="stopped", security_ok=False, exit_code=1)
        status = wait_for_observe_host(
            lambda: crashed,
            wait_s=20,
            poll_s=0.25,
            clock=lambda: 0.0,
            sleeper=lambda _seconds: (_ for _ in ()).throw(AssertionError("slept")),
        )
        self.assertEqual(status, "NOT_VERIFIED")
        self.assertIn("exit-code-1", readiness_gaps(crashed))

    def test_timeout_names_the_missing_contract(self) -> None:
        waiting = sample(self_check=False)
        times = iter((0.0, 20.0))
        status = wait_for_observe_host(
            lambda: waiting,
            wait_s=20,
            poll_s=0.25,
            clock=lambda: next(times),
            sleeper=lambda _seconds: None,
        )
        self.assertEqual(status, "NOT_VERIFIED")
        self.assertIn("self-check", host_check_failure_text("start_pe_observe", waiting))

    def test_boot_hold_handoff_is_not_an_observe_pass(self) -> None:
        handed = sample(boot_hold="HANDOFF")
        self.assertEqual(readiness_gaps(handed), ["boot-hold"])
        absent = sample(boot_hold="")
        self.assertIn("boot-hold", readiness_gaps(absent))

    def test_extended_inspect_keeps_exit_and_start(self) -> None:
        cmd = '["--iface","ens5"]'
        text = (
            "running 4242 true false vantio-pe-observe 0 "
            "2026-09-28T04:21:20.81983403Z 0001-01-01T00:00:00Z "
            f"sha256:abc {cmd}"
        )
        parsed = parse_observe_inspect(text)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["exit_code"], 0)
        self.assertEqual(parsed["pid"], 4242)
        self.assertEqual(parsed["container_id"], "sha256:abc")
        self.assertEqual(observe_lifecycle(parsed), "detached")
        self.assertIn("{{.State.ExitCode}}", OBSERVE_INSPECT_FORMAT)
        self.assertIn("{{.Id}}", OBSERVE_INSPECT_FORMAT)

    def test_sealed_loader_log_satisfies_the_observe_policy(self) -> None:
        facts = facts_from_logs(_active_log("ens5"), "ens5")
        self.assertTrue(facts["paths_active"])
        self.assertTrue(facts["policy_loaded"])
        self.assertTrue(facts["self_check"])
        self.assertTrue(facts["cgroup_attached"])
        denied = _active_log("ens5").replace("AUDIT (log only)", "NODE-WIDE DLP (drop all)")
        self.assertFalse(facts_from_logs(denied, "ens5")["policy_loaded"])
        banner_only = _active_log("ens5").replace(
            "[DEBUG] Absolute Control path DENY disabled (VANTIO_PHANTOM_DENY!=1); observe-only mode\n",
            "",
        )
        self.assertTrue(facts_from_logs(banner_only, "ens5")["policy_loaded"])
        self.assertTrue(egress_program_attached(None, banner_only, "ens5"))
        self.assertTrue(egress_program_attached("filter protocol all pref 49152 bpf", "", "ens5"))
        self.assertFalse(egress_program_attached("", "Phantom Engine active\n", "ens5"))

    def test_each_incomplete_state_asks_for_rollback(self) -> None:
        cases = [
            sample(lifecycle="stopped", security_ok=False, exit_code=1),
            sample(pins=list(constants.BPF_PINS)[:2], pins_current=False),
            sample(pins_current=False),
            sample(iface_ok=False),
            sample(self_check=False),
            sample(lifecycle="detached", loader=False, programs=False),
            sample(boot_hold="RELEASED"),
        ]
        for body in cases:
            text = host_check_failure_text("start_pe_observe", body)
            self.assertIn("Rollback is required.", text)
            self.assertNotIn("()", text)
            self.assertTrue(readiness_gaps(body))


def _active_log(iface: str) -> str:
    return (
        "Path observe maps loaded: 5 exact, 3 directory prefixes\n"
        "Path enforce maps loaded: 1 exact, 1 directory prefixes\n"
        "[ ∅ VANTIO ] Phantom Engine active\n"
        f"  tc enforce : AUDIT (log only)  iface '{iface}'\n"
        "  press Ctrl-C to stop\n"
        "sock owner attached: remember_owner_connect4 at /sys/fs/cgroup\n"
        "[DEBUG] Absolute Control path DENY disabled (VANTIO_PHANTOM_DENY!=1); observe-only mode\n"
    )


if __name__ == "__main__":
    unittest.main()
