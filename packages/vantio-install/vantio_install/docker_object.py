"""Post-operation decisions for one transaction-owned Docker object.

The primary signal is ``docker inspect`` of the exact object named by the
transaction. Text is only a fallback for the two absent-object sentences
Docker has been observed to print, compared case-insensitively and bound to
that same name. A daemon, permission, connectivity, timeout, malformed-name,
or unrecognized failure is never treated as absence.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass

_OBJECT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_ABSENT_NAMED = re.compile(
    r"no such (?:container|object)\s*:\s*['\"]?/?(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)",
    re.IGNORECASE,
)
_ABSENT_BARE = re.compile(r"no such (?:container|object)\b", re.IGNORECASE)
_OWNED_NAME = re.compile(r"vantio-pe-[A-Za-z0-9_.-]+", re.IGNORECASE)
_INSPECT_FORMAT = "{{json .}}"
_LABEL_TRANSACTION = "vantio.transaction_id"

IDEMPOTENT_ABSENT = "IDEMPOTENT_ABSENT"
REMOVED = "REMOVED"
FAILED_SAFE = "FAILED_SAFE"
RESIDUAL_FOUND = "RESIDUAL_FOUND"

_BLOCKING = frozenset(
    {
        "permission",
        "daemon",
        "connectivity",
        "invalid_name",
        "empty",
        "unknown",
        "timeout",
    }
)
_PERMISSION = (
    "permission denied",
    "operation not permitted",
    "access denied",
)
_DAEMON = (
    "cannot connect to the docker daemon",
    "is the docker daemon running",
    "error during connect",
    "docker daemon",
    "docker.sock",
)
_CONNECTIVITY = (
    "connection refused",
    "network is unreachable",
    "no route to host",
    "temporary failure in name resolution",
    "i/o timeout",
    "context deadline exceeded",
    "tls handshake",
)
_INVALID_NAME = (
    "invalid container name",
    "invalid reference format",
    "invalid object name",
    "not a valid container name",
    "malformed name",
)


@dataclass(frozen=True)
class DockerCommandResult:
    """Stdout and stderr are kept exactly as the process returned them."""

    returncode: int
    timed_out: bool = False
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class DockerObjectInspection:
    """One inspect of ``probed_name``. ``state`` is present, absent, or unknown."""

    probed_name: str
    state: str
    running: bool | None
    canonical_name: str | None
    labels: dict[str, str]
    exit_code: int | None
    stdout: str
    stderr: str
    failure_kind: str | None


def transaction_container_name(transaction_id: str) -> str:
    """Container name owned by this transaction. Empty when the id cannot own one."""
    if not isinstance(transaction_id, str) or len(transaction_id) < 12:
        return ""
    name = "vantio-pe-" + transaction_id[-12:]
    if _OBJECT_NAME.fullmatch(name) is None:
        return ""
    return name


def claims_absent_object(text: str, expected_name: str) -> bool:
    """True only for a recognized absent-object sentence bound to ``expected_name``.

    A bare ``no such object`` / ``no such container`` is accepted because some
    Docker 29 responses omit the name. The caller must already have targeted
    ``expected_name``. A sentence that names a different object is rejected.
    ``no such file`` is not an absent object.
    """
    if not text or not expected_name or _OBJECT_NAME.fullmatch(expected_name) is None:
        return False
    expected = expected_name.casefold()
    if not _mentions_only(text, expected):
        return False
    named = [match.group("name").casefold() for match in _ABSENT_NAMED.finditer(text)]
    if named:
        return all(item == expected for item in named)
    if "no such file" in text.casefold():
        return False
    return _ABSENT_BARE.search(text) is not None


def _mentions_only(text: str, expected: str) -> bool:
    mentioned = [match.casefold() for match in _OWNED_NAME.findall(text)]
    return all(item == expected for item in mentioned)


def probe_failure_kind(text: str, returncode: int, timed_out: bool, expected_name: str) -> str | None:
    """Classify a nonzero Docker response. Exit 0 has no failure kind."""
    if timed_out:
        return "timeout"
    if returncode == 0:
        return None
    folded = text.casefold()
    if any(needle in folded for needle in _PERMISSION):
        return "permission"
    if any(needle in folded for needle in _DAEMON):
        return "daemon"
    if any(needle in folded for needle in _CONNECTIVITY):
        return "connectivity"
    if any(needle in folded for needle in _INVALID_NAME):
        return "invalid_name"
    if not folded.strip():
        return "empty"
    if claims_absent_object(text, expected_name):
        return "absent"
    return "unknown"


def interpret_probe(name: str, completed: DockerCommandResult) -> DockerObjectInspection:
    """Turn one inspect invocation into present, absent, or unknown."""
    if completed.timed_out:
        return _unknown(name, completed, "timeout")
    if completed.returncode == 0:
        parsed = _parse_present(name, completed)
        if parsed is None:
            return _unknown(name, completed, "unknown")
        return parsed
    kind = probe_failure_kind(
        f"{completed.stderr}\n{completed.stdout}",
        completed.returncode,
        False,
        name,
    )
    if kind == "absent":
        return _absent(name, completed)
    return _unknown(name, completed, "unknown" if kind is None else kind)


def inspect_container(name: str, *, run=None) -> DockerObjectInspection:
    """Inspect one container by name. A refused name is unknown, not absent."""
    if _OBJECT_NAME.fullmatch(name) is None:
        return DockerObjectInspection(
            probed_name=name,
            state="unknown",
            running=None,
            canonical_name=None,
            labels={},
            exit_code=None,
            stdout="",
            stderr="",
            failure_kind="invalid_name",
        )
    argv = ["docker", "inspect", "--format", _INSPECT_FORMAT, name]
    if run is None:
        completed = _run_docker(argv, 15)
    else:
        completed = run(argv, 15)
        if not isinstance(completed, DockerCommandResult):
            return _unknown(name, DockerCommandResult(1, False, "", ""), "unknown")
    return interpret_probe(name, completed)


def classify_docker_object_operation(
    *,
    operation: str,
    transaction_id: str,
    object_name: str,
    command: DockerCommandResult,
    inspection: DockerObjectInspection,
) -> str:
    """Decide IDEMPOTENT_ABSENT, REMOVED, FAILED_SAFE, or RESIDUAL_FOUND.

    ``inspection`` is the observation taken after ``command``. An earlier
    inspect is not an input: a race is settled by this post-operation state.
    """
    if operation not in {"docker_stop", "docker_rm"}:
        return FAILED_SAFE
    if object_name != transaction_container_name(transaction_id):
        return FAILED_SAFE
    if inspection.probed_name != object_name:
        return FAILED_SAFE
    if command.timed_out or inspection.failure_kind == "timeout":
        return FAILED_SAFE
    if inspection.state == "present":
        if inspection.canonical_name != object_name:
            return FAILED_SAFE
        if not _label_agrees(inspection.labels, transaction_id):
            return FAILED_SAFE
    kind = probe_failure_kind(
        f"{command.stderr}\n{command.stdout}",
        command.returncode,
        command.timed_out,
        object_name,
    )
    if kind in _BLOCKING:
        return FAILED_SAFE
    if operation == "docker_stop":
        return _classify_stop(command, inspection, kind)
    return _classify_rm(command, inspection, kind)


def docker_object_host_status(operation: str, inspection: DockerObjectInspection) -> str:
    """Host-check view of the same post-operation inspect. Unknown stays unknown."""
    if inspection.state == "unknown":
        return "UNKNOWN"
    if operation == "docker_rm":
        return "VERIFIED" if inspection.state == "absent" else "NOT_VERIFIED"
    if operation == "docker_stop":
        if inspection.state == "absent":
            return "VERIFIED"
        if inspection.state == "present" and inspection.running is False:
            return "VERIFIED"
        return "NOT_VERIFIED"
    return "UNKNOWN"


def _classify_stop(
    command: DockerCommandResult,
    inspection: DockerObjectInspection,
    kind: str | None,
) -> str:
    if command.returncode == 0:
        if inspection.state == "absent":
            return REMOVED
        if inspection.state == "present" and inspection.running is False:
            return REMOVED
        if inspection.state == "present" and inspection.running is True:
            return RESIDUAL_FOUND
        return FAILED_SAFE
    if kind == "absent" and inspection.state == "absent":
        return IDEMPOTENT_ABSENT
    if kind == "absent" and inspection.state == "present":
        return RESIDUAL_FOUND
    return FAILED_SAFE


def _classify_rm(
    command: DockerCommandResult,
    inspection: DockerObjectInspection,
    kind: str | None,
) -> str:
    if command.returncode == 0:
        if inspection.state == "absent":
            return REMOVED
        if inspection.state == "present":
            return RESIDUAL_FOUND
        return FAILED_SAFE
    if kind == "absent" and inspection.state == "absent":
        return IDEMPOTENT_ABSENT
    if kind == "absent" and inspection.state == "present":
        return RESIDUAL_FOUND
    return FAILED_SAFE


def _label_agrees(labels: dict[str, str], transaction_id: str) -> bool:
    recorded = labels.get(_LABEL_TRANSACTION)
    if recorded is None:
        return True
    return recorded == transaction_id


def _parse_present(name: str, completed: DockerCommandResult) -> DockerObjectInspection | None:
    raw = completed.stdout.strip()
    if not raw:
        return None
    try:
        document = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(document, list):
        if len(document) != 1 or not isinstance(document[0], dict):
            return None
        document = document[0]
    if not isinstance(document, dict):
        return None
    raw_name = document.get("Name")
    state = document.get("State")
    config = document.get("Config")
    if not isinstance(raw_name, str) or not isinstance(state, dict):
        return None
    running = state.get("Running")
    if not isinstance(running, bool):
        return None
    labels = _labels(config)
    if labels is None:
        return None
    canonical = raw_name[1:] if raw_name.startswith("/") and not raw_name.startswith("//") else raw_name
    return DockerObjectInspection(
        probed_name=name,
        state="present",
        running=running,
        canonical_name=canonical,
        labels=labels,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        failure_kind=None,
    )


def _labels(config: object) -> dict[str, str] | None:
    if not isinstance(config, dict):
        return None
    raw = config.get("Labels")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        return None
    labels: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or isinstance(value, (dict, list)):
            return None
        labels[key] = "" if value is None else str(value)
    return labels


def _absent(name: str, completed: DockerCommandResult) -> DockerObjectInspection:
    return DockerObjectInspection(
        probed_name=name,
        state="absent",
        running=None,
        canonical_name=None,
        labels={},
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        failure_kind="absent",
    )


def _unknown(name: str, completed: DockerCommandResult, kind: str) -> DockerObjectInspection:
    return DockerObjectInspection(
        probed_name=name,
        state="unknown",
        running=None,
        canonical_name=None,
        labels={},
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        failure_kind=kind,
    )


def _run_docker(argv: list[str], timeout: int) -> DockerCommandResult:
    try:
        completed = subprocess.run(
            argv,
            shell=False,
            check=False,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return DockerCommandResult(124, True, _as_text(exc.stdout), _as_text(exc.stderr))
    except OSError as exc:
        return DockerCommandResult(127, False, "", exc.__class__.__name__)
    return DockerCommandResult(
        completed.returncode,
        False,
        _as_text(completed.stdout),
        _as_text(completed.stderr),
    )


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
