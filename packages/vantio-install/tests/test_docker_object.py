"""Docker object outcomes for rollback and uninstall. No live daemon."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from vantio_install.docker_object import (  # noqa: E402
    FAILED_SAFE,
    IDEMPOTENT_ABSENT,
    REMOVED,
    RESIDUAL_FOUND,
    DockerCommandResult,
    claims_absent_object,
    classify_docker_object_operation,
    docker_object_host_status,
    inspect_container,
    interpret_probe,
    transaction_container_name,
)

TX = "vantio-tx-11111111-1111-4111-8111-111111111111"
NAME = "vantio-pe-111111111111"


def _present(name: str, running: bool, labels: dict | None = None) -> DockerCommandResult:
    body = {
        "Id": "abc123",
        "Name": "/" + name,
        "State": {"Running": running, "Status": "running" if running else "exited"},
        "Config": {"Labels": {} if labels is None else labels},
    }
    return DockerCommandResult(0, False, json.dumps(body), "")


def _failed(stderr: str, stdout: str = "", code: int = 1, timed_out: bool = False) -> DockerCommandResult:
    return DockerCommandResult(code, timed_out, stdout, stderr)


class DockerObjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertEqual(transaction_container_name(TX), NAME)

    def decide(
        self,
        operation: str,
        command: DockerCommandResult,
        probe: DockerCommandResult,
        *,
        transaction_id: str = TX,
        object_name: str = NAME,
        probe_name: str | None = None,
    ) -> str:
        probed = object_name if probe_name is None else probe_name
        before = (command.returncode, command.timed_out, command.stdout, command.stderr)
        inspection = interpret_probe(probed, probe)
        outcome = classify_docker_object_operation(
            operation=operation,
            transaction_id=transaction_id,
            object_name=object_name,
            command=command,
            inspection=inspection,
        )
        after = (command.returncode, command.timed_out, command.stdout, command.stderr)
        self.assertEqual(after, before)
        self.assertEqual(inspection.stdout, probe.stdout)
        self.assertEqual(inspection.stderr, probe.stderr)
        self.assertEqual(inspection.exit_code, probe.returncode)
        self.inspection = inspection
        return outcome

    def test_01_no_such_container(self) -> None:
        message = "Error: No such container: %s\n" % NAME
        outcome = self.decide("docker_stop", _failed(message), _failed(message))
        self.assertEqual(outcome, IDEMPOTENT_ABSENT)
        self.assertEqual(self.inspection.state, "absent")
        source = (PACKAGE / "vantio_install" / "live_executor.py").read_text(encoding="utf-8")
        self.assertNotIn('"No such"', source)
        self.assertNotIn("'No such'", source)

    def test_02_lowercase_no_such_container(self) -> None:
        message = "Error: no such container: %s\n" % NAME
        self.assertEqual(self.decide("docker_rm", _failed(message), _failed(message)), IDEMPOTENT_ABSENT)

    def test_03_no_such_object(self) -> None:
        message = "Error response from daemon: No such object: %s\n" % NAME
        self.assertEqual(self.decide("docker_stop", _failed(message), _failed(message)), IDEMPOTENT_ABSENT)

    def test_04_lowercase_no_such_object(self) -> None:
        named = "Error response from daemon: no such object: %s\n" % NAME
        bare = "Error response from daemon: no such object\n"
        shouted = "Error response from daemon: NO SUCH OBJECT: %s\n" % NAME
        self.assertEqual(self.decide("docker_stop", _failed(named), _failed(named)), IDEMPOTENT_ABSENT)
        self.assertEqual(self.decide("docker_rm", _failed(bare), _failed(bare)), IDEMPOTENT_ABSENT)
        self.assertEqual(self.decide("docker_stop", _failed(shouted), _failed(shouted)), IDEMPOTENT_ABSENT)
        self.assertEqual(self.decide("docker_stop", _failed(bare), _failed("", "", code=1)), FAILED_SAFE)
        self.assertTrue(claims_absent_object(bare, NAME))
        self.assertFalse(claims_absent_object("no such file or directory", NAME))
        self.assertFalse(claims_absent_object(bare + "vantio-pe-ffffffffffff\n", NAME))

    def test_05_already_absent_transaction_owned_object(self) -> None:
        message = json.dumps({"message": "no such object: %s" % NAME})
        for operation in ("docker_stop", "docker_rm"):
            first = self.decide(operation, _failed(message), _failed(message))
            second = self.decide(operation, _failed(message), _failed(message))
            self.assertEqual(first, IDEMPOTENT_ABSENT)
            self.assertEqual(second, IDEMPOTENT_ABSENT)
            self.assertEqual(self.inspection.probed_name, NAME)

    def test_06_successful_stop(self) -> None:
        command = DockerCommandResult(0, False, NAME + "\n", "")
        probe = _present(NAME, False)
        self.assertEqual(self.decide("docker_stop", command, probe), REMOVED)
        self.assertEqual(docker_object_host_status("docker_stop", self.inspection), "VERIFIED")
        self.assertFalse(self.inspection.running)

    def test_07_successful_removal(self) -> None:
        message = "Error: No such container: %s\n" % NAME
        command = DockerCommandResult(0, False, NAME + "\n", "")
        self.assertEqual(self.decide("docker_rm", command, _failed(message)), REMOVED)
        self.assertEqual(docker_object_host_status("docker_rm", self.inspection), "VERIFIED")

    def test_08_docker_daemon_unavailable(self) -> None:
        daemon_and_absent = (
            "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. "
            "Is the docker daemon running? no such object: %s\n" % NAME
        )
        messages = (
            "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?\n",
            "dial unix /var/run/docker.sock: connect: no such file or directory\n",
            daemon_and_absent,
        )
        for message in messages:
            outcome = self.decide("docker_stop", _failed(message), _failed(message))
            self.assertEqual(outcome, FAILED_SAFE)
            self.assertEqual(self.inspection.state, "unknown")
            self.assertEqual(self.inspection.failure_kind, "daemon")
            self.assertEqual(docker_object_host_status("docker_stop", self.inspection), "UNKNOWN")

    def test_09_permission_denied(self) -> None:
        message = (
            'Got permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock: '
            'no such object: %s\n' % NAME
        )
        outcome = self.decide("docker_rm", _failed(message), _failed(message))
        self.assertEqual(outcome, FAILED_SAFE)
        self.assertEqual(self.inspection.failure_kind, "permission")
        self.assertNotEqual(self.inspection.state, "absent")

    def test_10_invalid_object_name(self) -> None:
        called = False

        def run(_argv, _timeout):
            nonlocal called
            called = True
            return _failed("Error: no such object: %s\n" % NAME)

        refused = inspect_container("bad name", run=run)
        self.assertFalse(called)
        self.assertEqual(refused.state, "unknown")
        self.assertEqual(refused.failure_kind, "invalid_name")
        message = "Error: Invalid container name (%s), only [a-zA-Z0-9][a-zA-Z0-9_.-] are allowed\n" % NAME
        self.assertEqual(self.decide("docker_rm", _failed(message), _failed(message)), FAILED_SAFE)
        self.assertEqual(self.inspection.failure_kind, "invalid_name")
        self.assertEqual(
            self.decide("docker_stop", _failed(message), _failed(message), object_name="bad name"),
            FAILED_SAFE,
        )

    def test_11_unknown_error(self) -> None:
        message = "Error response from daemon: driver failed programming external connectivity\n"
        self.assertEqual(self.decide("docker_stop", _failed(message), _failed(message)), FAILED_SAFE)
        self.assertEqual(self.inspection.failure_kind, "unknown")
        timed = _failed("Error: no such object: %s\n" % NAME, timed_out=True)
        self.assertEqual(self.decide("docker_rm", timed, timed), FAILED_SAFE)
        self.assertNotEqual(self.inspection.state, "absent")
        file_missing = _failed("Error: no such file or directory\n")
        self.assertEqual(self.decide("docker_rm", file_missing, file_missing), FAILED_SAFE)
        self.assertFalse(claims_absent_object(file_missing.stderr, NAME))
        absent = _failed("Error: no such object: %s\n" % NAME)
        self.assertEqual(self.decide("docker_rm", _failed(message), absent), FAILED_SAFE)
        offline = _failed("dial tcp 192.0.2.1:2375: connect: network is unreachable\n")
        self.assertEqual(self.decide("docker_stop", offline, offline), FAILED_SAFE)
        self.assertEqual(self.inspection.failure_kind, "connectivity")

    def test_12_empty_stderr_with_nonzero_exit(self) -> None:
        empty = _failed("", "", code=1)
        self.assertEqual(self.decide("docker_stop", empty, empty), FAILED_SAFE)
        self.assertEqual(self.inspection.failure_kind, "empty")
        blank = _failed(" \n\t", "", code=2)
        self.assertEqual(self.decide("docker_rm", blank, blank), FAILED_SAFE)
        stdout_only = _failed("", "Error: something went wrong\n", code=1)
        self.assertEqual(self.decide("docker_rm", stdout_only, stdout_only), FAILED_SAFE)
        self.assertNotEqual(self.inspection.state, "absent")

    def test_13_unrelated_object(self) -> None:
        other = "other-container"
        foreign = "Error: No such container: %s\n" % other
        self.assertEqual(
            self.decide("docker_rm", _failed(foreign), _failed(foreign), object_name=other),
            FAILED_SAFE,
        )
        mixed = "Error: no such container: %s\nError: no such object: %s\n" % (NAME, other)
        self.assertEqual(self.decide("docker_stop", _failed(mixed), _failed(mixed)), FAILED_SAFE)
        self.assertFalse(claims_absent_object(mixed, NAME))
        wrong_body = _present(other, False)
        self.assertEqual(self.decide("docker_rm", DockerCommandResult(0, False, "", ""), wrong_body), FAILED_SAFE)
        relabeled = _present(NAME, False, {"vantio.transaction_id": "vantio-tx-someone-else"})
        self.assertEqual(self.decide("docker_stop", DockerCommandResult(0, False, "", ""), relabeled), FAILED_SAFE)
        owned = "Error: no such object: %s\n" % NAME
        self.assertEqual(
            self.decide("docker_rm", _failed(owned), _failed(owned), probe_name=other),
            FAILED_SAFE,
        )

    def test_14_repeated_rollback(self) -> None:
        message = "Error: no such object: %s\n" % NAME
        for _pass in range(2):
            for operation in ("docker_stop", "docker_rm"):
                outcome = self.decide(operation, _failed(message), _failed(message))
                self.assertEqual(outcome, IDEMPOTENT_ABSENT, _pass)

    def test_15_repeated_uninstall(self) -> None:
        message = "Error response from daemon: no such object\n"
        for _pass in range(2):
            stop = self.decide("docker_stop", _failed(message), _failed(message))
            remove = self.decide("docker_rm", _failed(message), _failed(message))
            self.assertEqual(stop, IDEMPOTENT_ABSENT, _pass)
            self.assertEqual(remove, IDEMPOTENT_ABSENT, _pass)

    def test_16_residual_then_successful_cleanup(self) -> None:
        gone = "Error: no such container: %s\n" % NAME
        running = _present(NAME, True)
        stopped = _present(NAME, False)
        self.assertEqual(
            self.decide("docker_stop", DockerCommandResult(0, False, NAME + "\n", ""), running),
            RESIDUAL_FOUND,
        )
        self.assertEqual(
            self.decide("docker_stop", DockerCommandResult(0, False, NAME + "\n", ""), stopped),
            REMOVED,
        )
        self.assertEqual(
            self.decide("docker_rm", DockerCommandResult(0, False, NAME + "\n", ""), stopped),
            RESIDUAL_FOUND,
        )
        self.assertEqual(docker_object_host_status("docker_rm", self.inspection), "NOT_VERIFIED")
        removed = self.decide("docker_rm", DockerCommandResult(0, False, NAME + "\n", ""), _failed(gone))
        self.assertEqual(removed, REMOVED)

    def test_17_residual_then_cleanup_failure(self) -> None:
        stopped = _present(NAME, False)
        self.assertEqual(
            self.decide("docker_rm", DockerCommandResult(0, False, "", ""), stopped),
            RESIDUAL_FOUND,
        )
        denied = "Got permission denied while trying to connect to the Docker daemon socket\n"
        outcome = self.decide("docker_rm", _failed(denied), stopped)
        self.assertEqual(outcome, FAILED_SAFE)
        self.assertEqual(self.inspection.state, "present")
        down = "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?\n"
        self.assertEqual(self.decide("docker_stop", _failed(down), _present(NAME, True)), FAILED_SAFE)

    def test_18_docker_response_format_drift(self) -> None:
        drifts = (
            "Error: container does not exist: %s\n" % NAME,
            "Error: not found: %s\n" % NAME,
            'rpc error: code = NotFound desc = container "%s" in namespace "moby": not found\n' % NAME,
            "object missing: %s\n" % NAME,
        )
        for message in drifts:
            outcome = self.decide("docker_rm", _failed(message), _failed(message))
            self.assertEqual(outcome, FAILED_SAFE, message)
            self.assertEqual(self.inspection.state, "unknown", message)
            self.assertNotEqual(self.inspection.state, "absent", message)
        legacy = DockerCommandResult(0, False, "false\n", "")
        self.assertEqual(self.decide("docker_stop", legacy, legacy), FAILED_SAFE)
        self.assertEqual(self.inspection.failure_kind, "unknown")
        missing_state = DockerCommandResult(0, False, json.dumps({"Name": "/" + NAME, "Config": {"Labels": {}}}), "")
        self.assertEqual(self.decide("docker_rm", missing_state, missing_state), FAILED_SAFE)

    def test_19_race_inspect_remove_uses_post_operation_state(self) -> None:
        gone = "Error response from daemon: no such object: %s\n" % NAME
        # The command observed a miss. The inspect after the command is authoritative.
        self.assertEqual(self.decide("docker_rm", _failed(gone), _failed(gone)), IDEMPOTENT_ABSENT)
        self.assertEqual(
            self.decide("docker_rm", DockerCommandResult(0, False, NAME + "\n", ""), _failed(gone)),
            REMOVED,
        )
        # A stale absent sentence does not win when the later inspect still sees the object.
        self.assertEqual(self.decide("docker_rm", _failed(gone), _present(NAME, False)), RESIDUAL_FOUND)
        self.assertEqual(self.decide("docker_stop", _failed(gone), _present(NAME, True)), RESIDUAL_FOUND)

    def test_20_object_recreated_after_removal(self) -> None:
        command = DockerCommandResult(0, False, "abc123\n", "")
        recreated = _present(NAME, True)
        self.assertEqual(self.decide("docker_rm", command, recreated), RESIDUAL_FOUND)
        self.assertEqual(docker_object_host_status("docker_rm", self.inspection), "NOT_VERIFIED")
        self.assertEqual(self.inspection.canonical_name, NAME)
        stopped_again = _present(NAME, False)
        self.assertEqual(
            self.decide("docker_rm", DockerCommandResult(0, False, NAME + "\n", ""), stopped_again),
            RESIDUAL_FOUND,
        )


if __name__ == "__main__":
    unittest.main()
