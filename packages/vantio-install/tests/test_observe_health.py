"""Observe host check: a stopped container is not a detached loader."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from vantio_install import constants  # noqa: E402
from vantio_install.observe_health import observe_lifecycle, wait_for_observe_host  # noqa: E402
from vantio_install.pe_apparmor import OBSERVE_INSPECT_FORMAT, parse_observe_inspect  # noqa: E402

CMD = '["--iface","ens5"]'


def line(status: str, pid: int, running: str, privileged: str, profile: str = "vantio-pe-observe") -> str:
    return f"{status} {pid} {running} {privileged} {profile} {CMD}"


def sample(**overrides: object) -> dict:
    base = {
        "lifecycle": "detached",
        "security_ok": True,
        "pins": list(constants.BPF_PINS),
        "pins_error": False,
        "loader": True,
        "clsact": True,
    }
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


if __name__ == "__main__":
    unittest.main()
