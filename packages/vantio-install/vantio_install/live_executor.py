"""Typed live mutations. Argv only. Exit 0 is not success without a host check.

The fixture mutator does not import this module. A live command runs only
after both gates and every additional check in authorize_live.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from vantio_install import bpf_pins, constants
from vantio_install.docker_object import (
    FAILED_SAFE as DOCKER_FAILED_SAFE,
    IDEMPOTENT_ABSENT,
    REMOVED as DOCKER_REMOVED,
    RESIDUAL_FOUND as DOCKER_RESIDUAL_FOUND,
    DockerCommandResult,
    classify_docker_object_operation,
    docker_object_host_status,
    inspect_container,
)
from vantio_install.commands import (
    apparmor_parser_load_argv,
    apparmor_parser_remove_argv,
    apt_install_npm_argv,
    docker_load_argv,
    docker_rmi_argv,
    docker_start_argv,
    docker_stop_rm_argv,
    docker_tag_argv,
    mkdir_argv,
    npm_install_argv,
    npm_version_argv,
    observe_apparmor_opt,
    observe_binds,
    observe_container_argv,
    observe_env,
    pip_wheel_argv,
    tc_clsact_argv,
    tc_clsact_del_argv,
)
from vantio_install.pe_apparmor import (
    OBSERVE_INSPECT_FORMAT,
    apparmor_profile_loaded,
    pe_apparmor_profile_path,
    profile_text,
)
from vantio_install.agent_sdk import (
    agent_sdk_npm_verified,
    agent_sdk_present,
    agent_sdk_py_verified,
    observed_agent_sdk_npm_version,
    observed_agent_sdk_py_version,
    remove_agent_sdks,
)
from vantio_install.errors import InstallError
from vantio_install.oci_load import OciArchiveError, OciLoadPlan, load_output_rejected, materialize, plan_load
from vantio_install.host import probe_tracefs_mounted
from vantio_install.manifest import artifact_paths, load_manifest
from vantio_install.optics_cli import (
    observed_optics_cli_version,
    optics_cli_present,
    optics_cli_verified,
    remove_optics_prefix,
)
from vantio_install.paths import assert_safe_root
from vantio_install.state_machine import RESIDUAL_STATES
from vantio_install.observe_health import (
    OBSERVE_READY_POLL_S,
    OBSERVE_READY_WAIT_S,
    observe_sample_from_inspect,
    wait_for_observe_host,
)
from vantio_install.preflight import npm_requirement, run_preflight
from vantio_install.stage_remove import remove_stage_nofollow
from vantio_install.util import read_json, sha256_file, write_json

_ENV_GATE = "VANTIO_INSTALL_ALLOW_LIVE"
_IFACE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,14}$")
_SHELLS = {"sh", "bash", "dash", "zsh", "busybox", "sudo", "su"}
_META = (";", "|", "&", "`", "$(", "\n", "\r", ">", "<")
_ALLOWED_EXE = {"mkdir", "npm", "python3", "docker", "tc", "apparmor_parser", "apt-get"}

STEP_OPERATIONS = {
    "ensure_node": ("ensure_npm",),
    "install_optics_cli": ("mkdir_prefix", "install_optics_cli"),
    "install_agent_sdks": ("install_agent_sdk_npm", "install_agent_sdk_py"),
    "stage_pe_archive": ("mkdir_stage", "stage_pe_archive"),
    "docker_load": ("docker_load", "docker_tag"),
    "write_observe_config": ("mkdir_evidence", "write_observe_config", "o7_init"),
    "start_pe_observe": ("tc_clsact", "write_pe_apparmor", "load_pe_apparmor", "start_pe_observe"),
}

ROLLBACK_OPERATIONS = {
    "start_pe_observe": (
        "docker_stop",
        "docker_rm",
        "unpin_bpf_maps",
        "unload_pe_apparmor",
        "remove_pe_apparmor",
        "tc_clsact_del",
    ),
    "docker_load": ("docker_rmi",),
    "stage_pe_archive": ("remove_stage",),
    "write_observe_config": ("remove_observe_config", "remove_o7_record"),
    "install_agent_sdks": ("remove_sdks",),
    "install_optics_cli": ("remove_optics",),
}

# Host steps recorded after the command returns 0 and before the host check.
_PARTIAL_ON_EXIT = {
    "install_optics_cli": "install_optics_cli",
    "install_agent_sdk_npm": "install_agent_sdks",
    "install_agent_sdk_py": "install_agent_sdks",
    "load_pe_apparmor": "start_pe_observe",
}

_START_STATES = {
    "apply": {"PLANNED", "INTERRUPTED", "APPLYING"},
    "rollback": {"HEALTHY", "DEGRADED", "FAILED_SAFE", "INTERRUPTED", "APPLYING", "ROLLING_BACK"} | RESIDUAL_STATES,
    "uninstall": {"HEALTHY", "DEGRADED", "FAILED_SAFE", "INTERRUPTED", "UNINSTALLING"} | RESIDUAL_STATES,
}

_RUNTIME_STATES = {
    "apply": {"APPLYING"},
    "rollback": {"ROLLING_BACK"},
    "uninstall": {"UNINSTALLING"},
}

_TRACEFS_RECORDED = "Live mutations require a non-empty tracefs at /sys/kernel/tracing."
_TRACEFS_PROBE = (
    "The saved host snapshot has no tracefs fact. "
    "The live probe did not find a non-empty tracefs at /sys/kernel/tracing."
)
_RECOVERY_COMMANDS = frozenset({"rollback", "uninstall"})

_CLOSED = {
    "ROLLED_BACK",
    "UNINSTALLED",
    "VERIFIED_REMOVED",
    "RESIDUAL_PRESENT",
    "RESIDUAL_FOUND",
    "UNSUPPORTED",
    "PREFLIGHT_BLOCKED",
}


def live_operation_ids() -> list[str]:
    rows: list[str] = []
    for step in constants.APPLY_STEPS:
        rows.extend(STEP_OPERATIONS.get(step, ()))
    return rows


def rollback_operation_ids() -> list[str]:
    rows: list[str] = []
    for step in reversed(constants.APPLY_STEPS):
        rows.extend(ROLLBACK_OPERATIONS.get(step, ()))
    return rows


class ExecResult:
    def __init__(
        self,
        returncode: int,
        timed_out: bool = False,
        stdout: str = "",
        stderr: str = "",
        disposition: str | None = None,
    ) -> None:
        self.returncode = returncode
        self.timed_out = timed_out
        self.stdout = stdout
        self.stderr = stderr
        self.disposition = disposition


@dataclass(frozen=True)
class LiveGrant:
    command: str
    transaction_id: str
    plan_sha256: str
    bundle_digest: str
    iface: str
    prefix: Path
    stage: Path
    evidence: Path
    bundle: Path
    tx_dir: Path
    tag: str
    archive: Path
    optics_tarball: Path
    sdk_npm: Path
    sdk_wheel: Path
    container_name: str
    observe_config: Path
    npm_action: str


def _fail(message: str, *, failure_class: str = "FAILED_SAFE", state: str = "FAILED_SAFE", exit_code: int = 4) -> None:
    raise InstallError(message, exit_code=exit_code, state=state, failure_class=failure_class)


def guard_readonly_command(ctx: dict) -> None:
    """The live flag is refused on commands that must not mutate the host."""
    if not ctx.get("accept_live_mutations"):
        return
    command = str(ctx.get("command") or "")
    if command not in constants.LIVE_MUTATING_COMMANDS:
        _fail(
            "The live mutation flag is only accepted on apply, rollback, and uninstall.",
            failure_class="FAILED_SAFE",
        )


def reject_argv(argv: object) -> list[str]:
    if isinstance(argv, str) or not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
        _fail("Live commands accept an argv list. A shell string is refused.", failure_class="FAILED_SAFE")
    exe = Path(argv[0]).name
    if exe in _SHELLS or exe not in _ALLOWED_EXE:
        _fail(f"Executable {exe} is not on the live allowlist.", failure_class="FAILED_SAFE")
    if exe == "apt-get" and list(argv) != apt_install_npm_argv():
        _fail(
            "apt-get is allowlisted only to install the Ubuntu npm package.",
            failure_class="FAILED_SAFE",
        )
    for item in argv:
        if any(token in item for token in _META):
            _fail("An argument contains a shell metacharacter and is refused.", failure_class="FAILED_SAFE")
    return list(argv)


def confine(path: Path, roots: list[Path]) -> Path:
    resolved = path.resolve(strict=False)
    for root in roots:
        base = root.resolve(strict=False)
        if resolved == base or base in resolved.parents:
            return resolved
    _fail("A live path escapes the transaction roots.", failure_class="FAILED_SAFE")
    raise AssertionError("confine always raises or returns")


def residual_result(items: list, probe_errors: list | None = None) -> str:
    """Removal is EMPTY or RESIDUAL_FOUND. It is never PASS."""
    if probe_errors:
        return "UNKNOWN"
    if items:
        return "RESIDUAL_FOUND"
    return "EMPTY"


def _env_open(env: dict[str, str]) -> bool:
    return env.get(_ENV_GATE) == "1"


def _privilege_ok(host: dict, euid: int) -> bool:
    """Live mutations require effective root.

    ``privilege_mode`` ``sudo`` means ``sudo`` is on ``PATH``. ``docker_group``
    means this principal can write the Docker socket. Neither fact is a grant,
    and this function does not exec sudo.
    """
    del host
    return euid == 0


def _iface_ok(host: dict, iface: str) -> bool:
    if not isinstance(iface, str) or not _IFACE.fullmatch(iface):
        return False
    ifaces = host.get("ifaces")
    if not isinstance(ifaces, dict):
        return False
    return ifaces.get(iface) == "up"


def _observe_only(config: dict) -> bool:
    return (
        config.get("install_mode") == "observe-only"
        and config.get("enforcement") == "NOT_ENABLED"
        and config.get("path_deny") == "disabled"
        and str(config.get("otlp", "DISABLED")) == "DISABLED"
        and config.get("traffic_control", "audit-only") == "audit-only"
    )


def _reject_forbidden_live_argv(argv: list[str]) -> None:
    if "--enforce" in argv or "--privileged" in argv or any("VANTIO_PHANTOM_DENY" in item for item in argv):
        _fail("Refusing an enforce or privileged flag.", failure_class="FAILED_SAFE")
    named = observe_apparmor_opt()
    for item in argv:
        if item.startswith("apparmor=") and item != named:
            _fail(
                "Refusing an AppArmor setting other than the observe-only profile.",
                failure_class="FAILED_SAFE",
            )


def _require_observe_apparmor(argv: list[str]) -> None:
    opt = observe_apparmor_opt()
    caps = [argv[index + 1] for index, item in enumerate(argv) if item == "--cap-add"]
    if argv.count("--security-opt") != 1 or argv.count(opt) != 1:
        _fail("The observe container argv is missing its AppArmor profile.", failure_class="FAILED_SAFE")
    if caps != ["NET_ADMIN", "BPF", "SYS_ADMIN"]:
        _fail("The observe container capability list changed.", failure_class="FAILED_SAFE")


def _require_observe_mounts(argv: list[str]) -> None:
    volumes = [argv[index + 1] for index, item in enumerate(argv) if item == "-v" and index + 1 < len(argv)]
    if volumes != observe_binds():
        _fail("The observe container mount list changed.", failure_class="FAILED_SAFE")


def _observe_profile_file(grant: LiveGrant) -> Path:
    return confine(pe_apparmor_profile_path(grant.stage), [grant.stage])


def _profile_bytes_match(grant: LiveGrant) -> bool:
    path = _observe_profile_file(grant)
    return path.is_file() and path.read_text(encoding="utf-8") == profile_text()


def _require_apparmor_parser_argv(op_type: str, argv: list[str]) -> None:
    flag = "-Kr" if op_type == "load_pe_apparmor" else "-KR"
    if argv[:2] != ["apparmor_parser", flag]:
        _fail("The AppArmor parser argv is not the allowlisted form.", failure_class="FAILED_SAFE")
    if not argv[-1].endswith("/" + constants.PE_OBSERVE_APPARMOR_PROFILE):
        _fail("The AppArmor parser argv is not the observe profile path.", failure_class="FAILED_SAFE")


def oci_plan_for(grant: LiveGrant) -> OciLoadPlan:
    """The docker load file for this grant. The sealed archive stays put."""
    staged = grant.stage / grant.archive.name
    source = staged if staged.is_file() else grant.archive
    pin = constants.FROZEN_PINS
    try:
        return plan_load(
            source,
            grant.stage,
            fallback_digest=pin["pe_manifest_digest"],
            image_tag=pin["pe_local_tag"],
        )
    except OciArchiveError as exc:
        _fail(str(exc), failure_class="FAILED_SAFE")
        raise AssertionError("oci plan failure always raises")


def catalog_argv(op_type: str, grant: LiveGrant) -> list[str] | None:
    """Argv for process operations. None means a confined filesystem operation."""
    pin = constants.FROZEN_PINS
    prefix = str(grant.prefix)
    iface = grant.iface
    if grant.npm_action == "present":
        ensure_npm = npm_version_argv()
    elif grant.npm_action == "remediate":
        ensure_npm = apt_install_npm_argv()
    else:
        ensure_npm = None
    load_plan = oci_plan_for(grant) if op_type in {"docker_load", "docker_tag"} else None
    mapping: dict[str, list[str] | None] = {
        "ensure_npm": ensure_npm,
        "mkdir_prefix": mkdir_argv(prefix),
        "mkdir_stage": mkdir_argv(str(grant.stage)),
        "mkdir_evidence": mkdir_argv(str(grant.evidence)),
        "install_optics_cli": npm_install_argv(str(grant.optics_tarball), prefix),
        "install_agent_sdk_npm": npm_install_argv(str(grant.sdk_npm), prefix),
        "install_agent_sdk_py": pip_wheel_argv(str(grant.sdk_wheel), prefix),
        "stage_pe_archive": None,
        "docker_load": docker_load_argv(str(load_plan.load_path if load_plan else grant.stage / grant.archive.name)),
        "docker_tag": docker_tag_argv(
            load_plan.image_digest if load_plan else pin["pe_manifest_digest"],
            pin["pe_local_tag"],
        ),
        "write_observe_config": None,
        "o7_init": None,
        "tc_clsact": tc_clsact_argv(iface),
        "write_pe_apparmor": None,
        "load_pe_apparmor": apparmor_parser_load_argv(str(pe_apparmor_profile_path(grant.stage))),
        "start_pe_observe": observe_container_argv(tag=pin["pe_local_tag"], iface=iface, name=grant.container_name),
        "unload_pe_apparmor": apparmor_parser_remove_argv(str(pe_apparmor_profile_path(grant.stage))),
        "remove_pe_apparmor": None,
        "restart_pe_observe": docker_start_argv(grant.container_name),
        "docker_stop": docker_stop_rm_argv(grant.container_name)[0],
        "docker_rm": docker_stop_rm_argv(grant.container_name)[1],
        "unpin_bpf_maps": None,
        "docker_rmi": docker_rmi_argv(pin["pe_local_tag"]),
        "tc_clsact_del": tc_clsact_del_argv(iface),
        "remove_stage": None,
        "remove_observe_config": None,
        "remove_o7_record": None,
        "remove_optics": None,
        "remove_sdks": None,
    }
    if op_type not in mapping:
        _fail(f"Operation {op_type} is not on the live allowlist.", failure_class="FAILED_SAFE")
    argv = mapping[op_type]
    if op_type == "ensure_npm" and argv is None:
        _fail(
            "Install the Ubuntu npm package. The nodejs package does not include the npm binary.",
            failure_class="FAILED_SAFE",
        )
    if argv is not None:
        reject_argv(argv)
        _reject_forbidden_live_argv(argv)
        if op_type == "start_pe_observe":
            _require_observe_apparmor(argv)
            _require_observe_mounts(argv)
        if op_type in {"load_pe_apparmor", "unload_pe_apparmor"}:
            _require_apparmor_parser_argv(op_type, argv)
        if op_type == "docker_tag" and (argv[-1] != pin["pe_local_tag"] or argv[-1].endswith(":latest")):
            _fail("Refusing a mutable image tag.", failure_class="FAILED_SAFE")
    return argv


def _append_op(grant: LiveGrant, record: dict) -> None:
    path = grant.tx_dir / "LIVE-OPS.jsonl"
    line = json.dumps(record, sort_keys=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _rehash_plan(grant: LiveGrant) -> None:
    path = grant.tx_dir / "PLAN.json"
    if sha256_file(path) != grant.plan_sha256:
        _fail("The plan bytes changed after authorization.", failure_class="FAILED_SAFE")


def _rehash_archive(grant: LiveGrant) -> None:
    pin = constants.FROZEN_PINS
    if not grant.archive.is_file():
        _fail("The sealed Phantom Engine archive is not on disk.", failure_class="FAILED_SAFE")
    if sha256_file(grant.archive) != pin["pe_archive_sha256"]:
        _fail("The sealed archive hash changed after authorization.", failure_class="FAILED_SAFE")


def _rehash_inputs(op_type: str, grant: LiveGrant) -> None:
    pin = constants.FROZEN_PINS
    needed = {
        "install_optics_cli": (grant.optics_tarball, "optics_cli_sha256"),
        "install_agent_sdk_npm": (grant.sdk_npm, "agent_sdk_npm_sha256"),
        "install_agent_sdk_py": (grant.sdk_wheel, "agent_sdk_py_wheel_sha256"),
    }
    if op_type not in needed:
        return
    path, key = needed[op_type]
    if not path.is_file() or sha256_file(path) != pin[key]:
        _fail(f"The {op_type} artifact hash changed after authorization.", failure_class="FAILED_SAFE")


def _runtime_tx(grant: LiveGrant) -> dict:
    path = grant.tx_dir / "TRANSACTION.json"
    tx = read_json(path)
    if tx.get("transaction_id") != grant.transaction_id:
        _fail("The transaction id changed after authorization.", failure_class="FAILED_SAFE")
    if tx.get("bundle_digest") != grant.bundle_digest:
        _fail("The bundle digest changed after authorization.", failure_class="FAILED_SAFE")
    if tx.get("state") not in _RUNTIME_STATES[grant.command]:
        _fail(
            f"Refusing a live {grant.command} while the transaction is {tx.get('state')}.",
            failure_class="FAILED_SAFE",
        )
    return tx


def run_allowlisted(argv: list[str], timeout: int, runner) -> ExecResult:
    checked = reject_argv(argv)
    if runner is None:
        env = None
        if Path(checked[0]).name == "apt-get":
            env = os.environ.copy()
            env["DEBIAN_FRONTEND"] = "noninteractive"
        try:
            completed = subprocess.run(
                checked,
                shell=False,
                check=False,
                capture_output=True,
                timeout=timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            return ExecResult(124, True, _captured_text(exc.stdout), _captured_text(exc.stderr))
        except OSError as exc:
            if Path(checked[0]).name == "apt-get":
                _fail(
                    "The Ubuntu npm package could not be installed because apt-get is not on PATH. "
                    "Install the Ubuntu npm package. The nodejs package does not include the npm binary.",
                    failure_class="FAILED_SAFE",
                )
            _fail(f"The live command could not start: {exc.__class__.__name__}.", failure_class="FAILED_SAFE")
        return ExecResult(
            completed.returncode,
            False,
            _captured_text(completed.stdout),
            _captured_text(completed.stderr),
        )
    result = runner(checked, timeout)
    if not isinstance(result, ExecResult):
        _fail("The live runner returned an unexpected result.", failure_class="FAILED_SAFE")
    return result


def _filesystem(op_type: str, grant: LiveGrant) -> None:
    roots = [grant.prefix, grant.stage, grant.evidence, grant.tx_dir]
    pin = constants.FROZEN_PINS
    if op_type == "stage_pe_archive":
        _rehash_archive(grant)
        target = confine(grant.stage / grant.archive.name, [grant.stage])
        grant.stage.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(grant.archive, target)
        if sha256_file(target) != pin["pe_archive_sha256"]:
            _fail("The staged archive does not match the pin after copy.", failure_class="ROLLBACK_REQUIRED")
        return
    if op_type == "write_observe_config":
        path = confine(grant.observe_config, [grant.tx_dir])
        payload = {
            "install_mode": "observe-only",
            "enforcement": "NOT_ENABLED",
            "otlp": "DISABLED",
            "path_deny": "disabled",
            "traffic_control": "audit-only",
            "iface": grant.iface,
            "env": observe_env(),
            "cmd": ["--iface", grant.iface],
        }
        if "--enforce" in payload["cmd"] or "VANTIO_PHANTOM_DENY" in payload["env"]:
            _fail("Refusing to write an enforcing config.", failure_class="FAILED_SAFE")
        write_json(path, payload)
        return
    if op_type == "o7_init":
        path = confine(grant.evidence / "O7-RECORD.json", [grant.evidence])
        write_json(
            path,
            {
                "record_plane": "observe",
                "enforcement": "NOT_ENABLED",
                "host_enforcement": False,
                "transaction_id": grant.transaction_id,
            },
        )
        return
    if op_type == "remove_stage":
        remove_stage_nofollow(grant.stage)
        return
    if op_type == "remove_observe_config":
        path = confine(grant.observe_config, [grant.tx_dir])
        if path.is_file():
            path.unlink()
        return
    if op_type == "remove_o7_record":
        path = confine(grant.evidence / "O7-RECORD.json", [grant.evidence])
        if path.is_file():
            path.unlink()
        return
    if op_type == "write_pe_apparmor":
        path = confine(pe_apparmor_profile_path(grant.stage), [grant.stage])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(profile_text(), encoding="utf-8")
        if path.read_text(encoding="utf-8") != profile_text():
            _fail("The observe AppArmor profile bytes changed while writing.", failure_class="FAILED_SAFE")
        return
    if op_type == "remove_pe_apparmor":
        path = confine(pe_apparmor_profile_path(grant.stage), [grant.stage])
        if path.is_file() or path.is_symlink():
            path.unlink()
        return
    if op_type == "remove_optics":
        remove_optics_prefix(grant.prefix)
        return
    if op_type == "remove_sdks":
        remove_agent_sdks(grant.prefix)
        return
    if op_type == "unpin_bpf_maps":
        bpf_pins.unlink_known_pins(bpf_pins.default_bpffs())
        return
    _fail(f"Filesystem operation {op_type} is not on the live allowlist.", failure_class="FAILED_SAFE")


def partial_mutation_steps(tx_dir: Path) -> list[str]:
    path = tx_dir / "PARTIAL-MUTATIONS.json"
    if not path.is_file():
        return []
    try:
        document = read_json(path)
    except (OSError, json.JSONDecodeError):
        return []
    steps = document.get("steps") if isinstance(document, dict) else None
    if not isinstance(steps, list):
        return []
    return [step for step in steps if isinstance(step, str) and step in constants.HOST_MUTATION_STEPS]


def note_partial_mutation(tx_dir: Path, step_id: str) -> None:
    """Record a host change before its host check so rollback can still see it."""
    if step_id not in constants.HOST_MUTATION_STEPS:
        return
    steps = partial_mutation_steps(tx_dir)
    if step_id not in steps:
        steps.append(step_id)
    write_json(tx_dir / "PARTIAL-MUTATIONS.json", {"steps": steps})


def clear_partial_mutation(tx_dir: Path, step_id: str) -> None:
    path = tx_dir / "PARTIAL-MUTATIONS.json"
    if not path.is_file():
        return
    steps = [step for step in partial_mutation_steps(tx_dir) if step != step_id]
    if steps:
        write_json(path, {"steps": steps})
        return
    path.unlink()


def dispatch(
    grant: LiveGrant,
    op_type: str,
    argv: list[str] | None,
    *,
    runner,
    observer,
    timeout: int = 60,
) -> dict:
    """Run one allowlisted operation. Success requires verification, not exit 0."""
    _rehash_plan(grant)
    _runtime_tx(grant)
    expected = catalog_argv(op_type, grant)
    if expected is None:
        if argv not in (None, []):
            _fail("A filesystem operation does not accept extra argv.", failure_class="FAILED_SAFE")
    else:
        supplied = list(argv if argv is not None else expected)
        reject_argv(supplied)
        _reject_forbidden_live_argv(supplied)
        if any(item.endswith(":latest") or item == "latest" for item in supplied):
            _fail("Refusing a mutable image tag.", failure_class="FAILED_SAFE")
        if supplied != list(expected):
            _fail(f"Refusing argv that is not the allowlisted command for {op_type}.", failure_class="FAILED_SAFE")
    if op_type == "load_pe_apparmor" and not _profile_bytes_match(grant):
        _fail("The observe AppArmor profile bytes changed before load.", failure_class="FAILED_SAFE")
    if op_type == "unload_pe_apparmor" and not _profile_bytes_match(grant):
        path = _observe_profile_file(grant)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(profile_text(), encoding="utf-8")
    if op_type in {"docker_load", "docker_tag", "stage_pe_archive", "start_pe_observe"}:
        _rehash_archive(grant)
    _rehash_inputs(op_type, grant)
    if op_type == "ensure_npm" and grant.npm_action == "remediate" and runner is None and os.geteuid() != 0:
        _fail(
            "Install the Ubuntu npm package. The nodejs package does not include the npm binary.",
            failure_class="FAILED_SAFE",
        )
    _append_op(grant, {"op": op_type, "phase": "PENDING", "transaction_id": grant.transaction_id})
    result: ExecResult | None = None
    if expected is not None:
        if op_type == "docker_load":
            _materialize_load(grant)
        result = run_allowlisted(expected, timeout, runner)
        if runner is None:
            result = _recover_absent_target(op_type, grant, result)
        if result.timed_out:
            _append_op(grant, {"op": op_type, "phase": "INTERRUPTED", "transaction_id": grant.transaction_id})
            _fail(
                f"{op_type} timed out. The transaction is interrupted.",
                failure_class="INTERRUPTED",
                state="INTERRUPTED",
                exit_code=constants.EXIT_INTERRUPTED,
            )
        if op_type == "docker_load" and load_output_rejected(result.stdout, result.stderr):
            failure = "ROLLBACK_REQUIRED" if result.returncode == 0 else "FAILED_SAFE"
            _append_op(grant, {"op": op_type, "phase": failure, "transaction_id": grant.transaction_id})
            _fail(
                "docker load printed an unpack error, so the layer is not on the host. "
                "The installer does not change Docker's storage driver.",
                failure_class=failure,
            )
    else:
        _filesystem(op_type, grant)
        result = ExecResult(0, False)
    partial_step = _PARTIAL_ON_EXIT.get(op_type)
    if partial_step and result.returncode == 0 and not result.timed_out:
        note_partial_mutation(grant.tx_dir, partial_step)
    if result.disposition in {DOCKER_FAILED_SAFE, DOCKER_RESIDUAL_FOUND}:
        _record_docker_failure(grant, op_type, result)
    status = observer.verify(op_type, grant) if observer is not None else "NOT_VERIFIED"
    if result.disposition in {IDEMPOTENT_ABSENT, DOCKER_REMOVED} and status == "NOT_VERIFIED":
        result.disposition = DOCKER_RESIDUAL_FOUND
        _record_docker_failure(grant, op_type, result)
    if result.disposition in {IDEMPOTENT_ABSENT, DOCKER_REMOVED} and status not in {"VERIFIED", "NOT_VERIFIED"}:
        result.disposition = DOCKER_FAILED_SAFE
        _record_docker_failure(grant, op_type, result)
    code_ok = result.returncode == 0 or result.disposition == IDEMPOTENT_ABSENT
    if status != "VERIFIED" or not code_ok:
        failure = "ROLLBACK_REQUIRED" if result.returncode == 0 else "FAILED_SAFE"
        _append_op(grant, {"op": op_type, "phase": failure, "transaction_id": grant.transaction_id})
        if failure == "ROLLBACK_REQUIRED":
            _fail(
                f"{op_type} returned exit 0 and the host check did not verify it. Rollback is required.",
                failure_class="ROLLBACK_REQUIRED",
            )
        _fail(f"{op_type} failed the host check.", failure_class="FAILED_SAFE")
    delta = observer.observed_delta(op_type, grant) if observer is not None else {}
    if not isinstance(delta, dict):
        _fail("The host check returned an unexpected observation.", failure_class="ROLLBACK_REQUIRED")
    verified = {"op": op_type, "phase": "VERIFIED", "transaction_id": grant.transaction_id}
    if result.disposition:
        verified["docker_object"] = result.disposition
        verified["docker_exit_code"] = result.returncode
    _append_op(grant, verified)
    return delta


def _materialize_load(grant: LiveGrant) -> None:
    plan = oci_plan_for(grant)
    if not plan.rewrite:
        return
    try:
        materialize(plan)
    except OciArchiveError as exc:
        _fail(str(exc), failure_class="FAILED_SAFE")


def execute_step(grant: LiveGrant, step_id: str, kind: str, runner, observer) -> tuple[list[dict], list[list[str]]]:
    table = STEP_OPERATIONS if kind == "apply" else ROLLBACK_OPERATIONS
    if step_id not in table:
        return [], []
    deltas: list[dict] = []
    recorded: list[list[str]] = []
    for op_type in table[step_id]:
        argv = catalog_argv(op_type, grant)
        timeout = 180 if op_type == "ensure_npm" else 60
        delta = dispatch(grant, op_type, argv, runner=runner, observer=observer, timeout=timeout)
        deltas.append(delta)
        if argv:
            recorded.append(argv)
    return deltas, recorded


def resolve_tracefs_host(
    host: dict,
    *,
    command: str,
    probe: Callable[[], bool] | None = None,
) -> tuple[dict, bool]:
    """Decide tracefs for a live command without rewriting the saved snapshot.

    A missing ``tracefs_mounted`` key is unrecorded. It is not an observation
    that the mount is absent. Apply fills that gap from a live probe. Rollback
    and uninstall do not need the mount, so an unrecorded key does not block them.
    A recorded false or unknown value stays a refusal on every command.
    """
    if "tracefs_mounted" in host:
        if host.get("tracefs_mounted") is not True:
            _fail(_TRACEFS_RECORDED, failure_class="FAILED_SAFE")
        return host, False
    if command in _RECOVERY_COMMANDS:
        return host, True
    live = probe_tracefs_mounted() if probe is None else probe()
    if live is not True:
        _fail(_TRACEFS_PROBE, failure_class="FAILED_SAFE")
    return {**host, "tracefs_mounted": True}, False


def authorize_live(
    *,
    command: str,
    tx: dict,
    tx_dir: Path,
    config: dict,
    bundle: Path,
    host: dict,
    plan_path: Path | None,
    plan_sha256: str | None,
    accept_live_mutations: bool,
    env: dict[str, str] | None = None,
    euid: int | None = None,
    tracefs_probe: Callable[[], bool] | None = None,
) -> LiveGrant:
    """Return a grant or refuse before any host mutation."""
    env = os.environ if env is None else env
    euid = os.geteuid() if euid is None else euid
    if command not in constants.LIVE_MUTATING_COMMANDS:
        _fail("The live mutation flag is only accepted on apply, rollback, and uninstall.")
    env_open = _env_open(env)
    if env_open != bool(accept_live_mutations) or not env_open or not accept_live_mutations:
        _fail(
            "Live mutations need VANTIO_INSTALL_ALLOW_LIVE=1 and --i-accept-live-mutations together.",
            failure_class="FAILED_SAFE",
        )
    if not _privilege_ok(host, euid):
        _fail(
            "Live mutations need effective root. sudo on PATH is not privilege.",
            failure_class="FAILED_SAFE",
        )
    if not _observe_only(config):
        _fail("Live mutations run observe-only. Enforcement stays off.", failure_class="FAILED_SAFE")
    arch = str(host.get("uname_m", "UNKNOWN"))
    if arch not in {"x86_64", "amd64"}:
        _fail("Live mutations require x86_64.", failure_class="FAILED_SAFE")
    if host.get("btf_vmlinux_exists") is not True:
        _fail("Live mutations require kernel BTF.", failure_class="FAILED_SAFE")
    kernel = str(host.get("kernel") or "")
    if not kernel or kernel == "UNKNOWN":
        _fail("Live mutations require an observed kernel.", failure_class="FAILED_SAFE")
    if host.get("cgroup_version") != "cgroup2" or host.get("bpffs_mounted") is not True:
        _fail("Live mutations require cgroup v2 and bpffs.", failure_class="FAILED_SAFE")
    iface = str(config.get("iface") or "")
    if not _iface_ok(host, iface):
        _fail("The planned interface is not an up interface on this host.", failure_class="FAILED_SAFE")

    state = str(tx.get("state") or "")
    # RESIDUAL_FOUND and RESIDUAL_PRESENT stay closed for apply. Rollback and
    # uninstall are the recovery commands that may start from those states.
    if state in _CLOSED and state not in _START_STATES[command]:
        _fail(
            f"The transaction is {state} and is not an open plan for live {command}.",
            failure_class="FAILED_SAFE",
        )
    if command == "apply" and state in {"HEALTHY", "DEGRADED"}:
        _fail(
            f"The transaction is {state} and is not an open plan for live {command}.",
            failure_class="FAILED_SAFE",
        )
    if command == "apply" and state == "INTERRUPTED" and tx.get("phase") == "rollback":
        _fail("This interrupted transaction resumes with rollback.", failure_class="FAILED_SAFE")
    if state not in _START_STATES[command]:
        _fail(f"Live {command} cannot start from {state}.", failure_class="FAILED_SAFE")
    if tx.get("transaction_id") is None:
        _fail("The transaction id is missing.", failure_class="FAILED_SAFE")

    plan_file = tx_dir / "PLAN.json"
    if plan_path is None or not str(plan_sha256 or "").strip() or not plan_file.is_file():
        _fail("Live apply needs --plan and --plan-sha256 for this transaction.", failure_class="FAILED_SAFE")
    supplied = Path(plan_path)
    if not supplied.is_file():
        _fail("The --plan file was not found.", failure_class="FAILED_SAFE")
    supplied_hash = sha256_file(supplied)
    current_hash = sha256_file(plan_file)
    if supplied_hash != plan_sha256 or current_hash != plan_sha256 or supplied_hash != current_hash:
        _fail("The plan hash does not match this transaction.", failure_class="FAILED_SAFE")
    plan_doc = read_json(plan_file)
    if plan_doc.get("transaction_id") != tx.get("transaction_id"):
        _fail("The plan is bound to a different transaction.", failure_class="FAILED_SAFE")
    expected_rollback = [step for step in reversed(constants.APPLY_STEPS) if step in constants.HOST_MUTATION_STEPS]
    if plan_doc.get("rollback_steps") != expected_rollback:
        _fail("The plan is missing the rollback steps.", failure_class="FAILED_SAFE")
    residual = plan_doc.get("residual_checks")
    if not isinstance(residual, list) or not residual:
        _fail("The plan is missing residual checks.", failure_class="FAILED_SAFE")
    recorded_ops = plan_doc.get("live_operations")
    expected_ops = live_operation_ids()
    if not isinstance(recorded_ops, list) or not recorded_ops:
        _fail("The plan is missing the live operation list.", failure_class="FAILED_SAFE")
    if recorded_ops != expected_ops:
        _fail(
            "This installer refuses a plan whose live operation list does not match. "
            "Roll that plan back with the installer that wrote it.",
            failure_class="FAILED_SAFE",
        )
    # After the operation list. A parent snapshot with no tracefs_mounted key
    # must not be reported as a missing host mount.
    checked_host, allow_unrecorded_tracefs = resolve_tracefs_host(
        host,
        command=command,
        probe=tracefs_probe,
    )

    evidence = Path(str(tx.get("evidence_dir") or ""))
    if not evidence.is_dir() or not (evidence / "TRANSACTION.json").is_file():
        _fail("Evidence for this transaction is not initialized.", failure_class="FAILED_SAFE")

    prefix = assert_safe_root(str(config.get("prefix") or ""), label="prefix")
    stage = assert_safe_root(str(config.get("stage_dir") or ""), label="stage_dir")
    assert_safe_root(str(evidence), label="evidence_dir")
    roots = config.get("workload_roots")
    if not isinstance(roots, list) or not roots:
        _fail("workload_roots must be a non-empty list.", failure_class="FAILED_SAFE")
    for item in roots:
        assert_safe_root(str(item), label="workload_roots")

    report = run_preflight(
        bundle=bundle,
        config={**config, "transaction_id": tx["transaction_id"]},
        host=checked_host,
        resuming=True,
        plan_present=True,
        config_present=True,
        bundle_digest_match=True,
        allow_unrecorded_tracefs=allow_unrecorded_tracefs,
    )
    for row in report["checks"]:
        if row["result"] == "UNKNOWN":
            _fail(f"Mandatory preflight {row['id']} is UNKNOWN.", failure_class="FAILED_SAFE")
    overall = report["overall"]
    if overall == "READY_WITH_LIMITATIONS":
        ids = {row["id"] for row in report["limitations"]}
        if not ids or not ids <= constants.APPROVED_LIVE_LIMITATIONS:
            _fail(
                "A live install refuses a limitation other than bounded memory: "
                + ", ".join(sorted(ids)),
                failure_class="FAILED_SAFE",
            )
        for row in report["checks"]:
            if row["id"] == "PF-MEM" and row["observed"].get("resource_class") == "UNKNOWN":
                _fail("Memory was not observed. Mandatory preflight stays UNKNOWN.", failure_class="FAILED_SAFE")
    elif overall != "READY":
        bad = [row["id"] for row in report["checks"] if row["result"] not in {"PASS", "LIMITATION"}]
        _fail("Mandatory preflight is not ready: " + ", ".join(bad), failure_class="FAILED_SAFE")

    pin = constants.FROZEN_PINS
    canon = constants.LIVE_CANONICAL_IDENTITY
    if pin["pe_source_commit"] != canon["pe_source_commit"]:
        _fail("The Phantom Engine tip pin does not match the sealed identity.", failure_class="FAILED_SAFE")
    if pin["pe_manifest_digest"] != canon["pe_manifest_digest"]:
        _fail("The Phantom Engine manifest pin does not match the sealed identity.", failure_class="FAILED_SAFE")
    paths = artifact_paths(bundle, pin)
    archive = paths["pe_archive"]
    if not archive.is_file() or sha256_file(archive) != pin["pe_archive_sha256"]:
        _fail("The sealed archive hash does not match the pin table.", failure_class="FAILED_SAFE")
    for key, filename_key in (
        ("optics_cli", "optics_cli_sha256"),
        ("agent_sdk_npm", "agent_sdk_npm_sha256"),
        ("agent_sdk_py_wheel", "agent_sdk_py_wheel_sha256"),
    ):
        path = paths[key]
        if not path.is_file() or sha256_file(path) != pin[filename_key]:
            _fail(f"The {key} artifact hash does not match the pin table.", failure_class="FAILED_SAFE")
    manifest = read_json(paths["pe_manifest"])
    if manifest.get("source_commit") != canon["pe_source_commit"]:
        _fail("The Phantom Engine manifest commit does not match the sealed tip.", failure_class="FAILED_SAFE")
    if manifest.get("manifest_digest") != canon["pe_manifest_digest"]:
        _fail("The Phantom Engine manifest digest does not match the sealed digest.", failure_class="FAILED_SAFE")
    deployment = load_manifest(bundle)
    products = deployment.get("products") or {}
    if products.get("phantom_engine") != canon["pe_source_commit"]:
        _fail("The bundle manifest Phantom Engine tip does not match the sealed tip.", failure_class="FAILED_SAFE")
    digests = plan_doc.get("artifact_digests") or {}
    if digests.get("pe_source_commit") != canon["pe_source_commit"]:
        _fail("The plan Phantom Engine tip does not match the sealed tip.", failure_class="FAILED_SAFE")
    if digests.get("pe_manifest_digest") != canon["pe_manifest_digest"]:
        _fail("The plan manifest digest does not match the sealed digest.", failure_class="FAILED_SAFE")
    if digests.get("pe_archive_sha256") != pin["pe_archive_sha256"]:
        _fail("The plan archive hash does not match the bytes on disk.", failure_class="FAILED_SAFE")

    return LiveGrant(
        command=command,
        transaction_id=str(tx["transaction_id"]),
        plan_sha256=current_hash,
        bundle_digest=str(tx.get("bundle_digest")),
        iface=iface,
        prefix=prefix,
        stage=stage,
        evidence=evidence,
        bundle=bundle,
        tx_dir=tx_dir,
        tag=pin["pe_local_tag"],
        archive=archive,
        optics_tarball=paths["optics_cli"],
        sdk_npm=paths["agent_sdk_npm"],
        sdk_wheel=paths["agent_sdk_py_wheel"],
        container_name=f"vantio-pe-{str(tx['transaction_id'])[-12:]}",
        observe_config=tx_dir / "observe-config.json",
        npm_action=npm_requirement(host)["action"],
    )


class ProductionObserver:
    """Read-only host checks. They do not receive the mutation's exit code.

    apparmor_profiles overrides the kernel profile list. Production leaves it
    unset and reads /sys/kernel/security/apparmor/profiles. Tests pass a
    fixture path so they do not touch securityfs.
    """

    def __init__(
        self,
        apparmor_profiles: Path | None = None,
        *,
        observe_sampler: Callable[[LiveGrant], dict] | None = None,
        observe_wait_s: float = OBSERVE_READY_WAIT_S,
        observe_poll_s: float = OBSERVE_READY_POLL_S,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self.apparmor_profiles = apparmor_profiles
        self.observe_sampler = observe_sampler
        self.observe_wait_s = observe_wait_s
        self.observe_poll_s = observe_poll_s
        self.clock = clock
        self.sleeper = sleeper

    def verify(self, op_type: str, grant: LiveGrant) -> str:
        try:
            if op_type == "ensure_npm":
                return "VERIFIED" if shutil.which("npm") else "NOT_VERIFIED"
            if op_type == "install_optics_cli":
                expected = constants.FROZEN_PINS["optics_cli_version"]
                return "VERIFIED" if optics_cli_verified(grant.prefix, expected) else "NOT_VERIFIED"
            if op_type == "install_agent_sdk_npm":
                expected = constants.FROZEN_PINS["agent_sdk_npm_version"]
                return "VERIFIED" if agent_sdk_npm_verified(grant.prefix, expected) else "NOT_VERIFIED"
            if op_type == "install_agent_sdk_py":
                expected = constants.FROZEN_PINS["agent_sdk_py_version"]
                return "VERIFIED" if agent_sdk_py_verified(grant.prefix, expected) else "NOT_VERIFIED"
            if op_type in {"mkdir_prefix", "mkdir_stage", "mkdir_evidence"}:
                path = {
                    "mkdir_prefix": grant.prefix,
                    "mkdir_stage": grant.stage,
                    "mkdir_evidence": grant.evidence,
                }[op_type]
                return "VERIFIED" if path.is_dir() else "NOT_VERIFIED"
            if op_type == "stage_pe_archive":
                target = grant.stage / grant.archive.name
                if target.is_file() and sha256_file(target) == constants.FROZEN_PINS["pe_archive_sha256"]:
                    return "VERIFIED"
                return "NOT_VERIFIED"
            if op_type == "write_observe_config":
                payload = read_json(grant.observe_config)
                if payload.get("enforcement") == "NOT_ENABLED" and "--enforce" not in (payload.get("cmd") or []):
                    return "VERIFIED"
                return "NOT_VERIFIED"
            if op_type == "o7_init":
                payload = read_json(grant.evidence / "O7-RECORD.json")
                if payload.get("enforcement") == "NOT_ENABLED" and payload.get("host_enforcement") is False:
                    return "VERIFIED"
                return "NOT_VERIFIED"
            if op_type == "write_pe_apparmor":
                path = pe_apparmor_profile_path(grant.stage)
                if path.is_file() and path.read_text(encoding="utf-8") == profile_text():
                    return "VERIFIED"
                return "NOT_VERIFIED"
            if op_type == "load_pe_apparmor":
                path = pe_apparmor_profile_path(grant.stage)
                if not path.is_file() or path.read_text(encoding="utf-8") != profile_text():
                    return "NOT_VERIFIED"
                loaded = apparmor_profile_loaded(
                    constants.PE_OBSERVE_APPARMOR_PROFILE,
                    self.apparmor_profiles,
                )
                if loaded is True:
                    return "VERIFIED"
                return "UNKNOWN" if loaded is None else "NOT_VERIFIED"
            if op_type == "unload_pe_apparmor":
                loaded = apparmor_profile_loaded(
                    constants.PE_OBSERVE_APPARMOR_PROFILE,
                    self.apparmor_profiles,
                )
                if loaded is False:
                    return "VERIFIED"
                return "UNKNOWN" if loaded is None else "NOT_VERIFIED"
            if op_type == "remove_pe_apparmor":
                path = pe_apparmor_profile_path(grant.stage)
                return "VERIFIED" if not path.exists() else "NOT_VERIFIED"
            if op_type == "remove_optics":
                return "VERIFIED" if not optics_cli_present(grant.prefix) else "NOT_VERIFIED"
            if op_type == "remove_sdks":
                return "VERIFIED" if not agent_sdk_present(grant.prefix) else "NOT_VERIFIED"
            if op_type in {"remove_stage", "remove_observe_config", "remove_o7_record"}:
                return "VERIFIED"
            if op_type == "docker_load":
                return _docker_image_present(oci_plan_for(grant).image_digest)
            if op_type == "docker_tag":
                return _docker_image_present(grant.tag)
            if op_type in {"start_pe_observe", "restart_pe_observe"}:

                def sample() -> dict:
                    if self.observe_sampler is not None:
                        return self.observe_sampler(grant)
                    return _observe_sample(grant.container_name, grant.iface)

                return wait_for_observe_host(
                    sample,
                    wait_s=self.observe_wait_s,
                    poll_s=self.observe_poll_s,
                    clock=self.clock or time.monotonic,
                    sleeper=self.sleeper or time.sleep,
                )
            if op_type == "unpin_bpf_maps":
                pins, pin_errors = _host_pins()
                if pin_errors:
                    return "UNKNOWN"
                return "VERIFIED" if not pins else "NOT_VERIFIED"
            if op_type == "docker_stop":
                return _docker_stopped(grant.container_name)
            if op_type == "docker_rm":
                return _docker_removed(grant.container_name)
            if op_type == "docker_rmi":
                return "VERIFIED" if _docker_image_present(grant.tag) == "NOT_VERIFIED" else "NOT_VERIFIED"
            if op_type == "tc_clsact":
                return _tc_has_clsact(grant.iface)
            if op_type == "tc_clsact_del":
                return "VERIFIED" if _tc_has_clsact(grant.iface) == "NOT_VERIFIED" else "NOT_VERIFIED"
        except (OSError, ValueError, KeyError):
            return "UNKNOWN"
        return "NOT_VERIFIED"

    def observed_delta(self, op_type: str, grant: LiveGrant) -> dict:
        pin = constants.FROZEN_PINS
        if op_type == "ensure_npm":
            version = _observed_npm_version()
            if version:
                return {"npm_version": version}
            return {}
        if op_type == "install_optics_cli":
            version = observed_optics_cli_version(grant.prefix)
            if version:
                return {"optics_cli_version": version}
            return {}
        if op_type == "install_agent_sdk_npm":
            version = observed_agent_sdk_npm_version(grant.prefix)
            if version:
                return {"agent_sdk_npm_version": version}
            return {}
        if op_type == "install_agent_sdk_py":
            version = observed_agent_sdk_py_version(grant.prefix)
            if version:
                return {"agent_sdk_py_version": version}
            return {}
        if op_type == "docker_tag":
            return {
                "images": [
                    {
                        "tag": pin["pe_local_tag"],
                        "digest": oci_plan_for(grant).image_digest,
                        "role": "phantom_engine",
                    }
                ]
            }
        if op_type == "start_pe_observe":
            delta: dict = {
                "containers": [
                    {
                        "name": grant.container_name,
                        "role": "phantom_engine",
                        "status": "running",
                        "image": pin["pe_local_tag"],
                        "cmd": ["--iface", grant.iface],
                        "enforce": False,
                    }
                ]
            }
            if _loader_running():
                delta["processes"] = ["vantio-loader"]
            pins, pin_errors = _host_pins()
            if pins and not pin_errors:
                delta["bpf_pins"] = pins
            if _tc_has_clsact(grant.iface) == "VERIFIED":
                delta["clsact_ifaces"] = [grant.iface]
            return delta
        if op_type in {"docker_stop", "docker_rm"}:
            # The container stop does not unpin maps. Record the live names.
            # An empty list here used to clear the snapshot while pins remained.
            stopped: dict = {"containers": [], "processes": [], "clsact_ifaces": []}
            pins, pin_errors = _host_pins()
            if not pin_errors:
                stopped["bpf_pins"] = pins
            return stopped
        if op_type == "unpin_bpf_maps":
            pins, pin_errors = _host_pins()
            if pin_errors:
                return {}
            return {"bpf_pins": pins}
        if op_type == "docker_rmi":
            return {"images": []}
        if op_type == "remove_optics":
            return {"optics_cli_version": None}
        if op_type == "remove_sdks":
            return {"agent_sdk_npm_version": None, "agent_sdk_py_version": None}
        return {}


def _read_only(argv: list[str]) -> str | None:
    checked = reject_argv(argv)
    try:
        completed = subprocess.run(checked, shell=False, check=False, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def _docker_image_present(tag: str) -> str:
    text = _read_only(["docker", "image", "inspect", "--format", "{{.Id}}", tag])
    return "VERIFIED" if text else "NOT_VERIFIED"


def _docker_inspect_line(name: str) -> str | None:
    return _read_only(["docker", "inspect", "--format", OBSERVE_INSPECT_FORMAT, name])


def _observe_sample(name: str, iface: str) -> dict:
    text = _docker_inspect_line(name)
    lifecycle, security_ok = observe_sample_from_inspect(text)
    pins, pin_errors = _host_pins()
    return {
        "lifecycle": lifecycle,
        "security_ok": security_ok,
        "pins": pins,
        "pins_error": bool(pin_errors),
        "loader": _loader_running(),
        "clsact": _tc_has_clsact(iface) == "VERIFIED",
    }


def _observed_npm_version() -> str | None:
    npm = shutil.which("npm")
    if not npm:
        return None
    text = _read_only([npm, "--version"])
    if not text:
        return None
    return text.strip() or None


def _docker_stopped(name: str) -> str:
    return docker_object_host_status("docker_stop", inspect_container(name))


def _docker_removed(name: str) -> str:
    return docker_object_host_status("docker_rm", inspect_container(name))


def _recover_absent_target(op_type: str, grant: LiveGrant, result: ExecResult) -> ExecResult:
    """Classify a Docker miss. Keep the original exit code, stdout, and stderr.

    Only a post-operation inspect that agrees the transaction-owned object is
    already gone can mark the command idempotent. Other Docker failures stay
    on the result and fail closed.
    """
    if result.timed_out:
        return result
    if op_type in {"docker_stop", "docker_rm"}:
        inspection = inspect_container(grant.container_name)
        result.disposition = classify_docker_object_operation(
            operation=op_type,
            transaction_id=grant.transaction_id,
            object_name=grant.container_name,
            command=DockerCommandResult(result.returncode, result.timed_out, result.stdout, result.stderr),
            inspection=inspection,
        )
        return result
    if result.returncode == 0:
        return result
    if op_type == "unload_pe_apparmor" and apparmor_profile_loaded(constants.PE_OBSERVE_APPARMOR_PROFILE) is False:
        return ExecResult(0, False, result.stdout, result.stderr)
    return result


def _record_docker_failure(grant: LiveGrant, op_type: str, result: ExecResult) -> None:
    if result.disposition in {DOCKER_FAILED_SAFE, DOCKER_RESIDUAL_FOUND}:
        phase = result.disposition
    else:
        phase = DOCKER_FAILED_SAFE
    _append_op(
        grant,
        {
            "op": op_type,
            "phase": phase,
            "transaction_id": grant.transaction_id,
            "docker_exit_code": result.returncode,
        },
    )
    if phase == DOCKER_RESIDUAL_FOUND:
        _fail(f"{op_type} left residual product state.", failure_class="FAILED_SAFE")
    _fail(f"{op_type} failed the host check.", failure_class="FAILED_SAFE")


def _captured_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _host_pins() -> tuple[list[str], list[str]]:
    return bpf_pins.scan_known_pins(bpf_pins.default_bpffs())


def _loader_running() -> bool:
    proc = Path("/proc")
    if not proc.is_dir():
        return False
    try:
        entries = list(proc.iterdir())
    except OSError:
        return False
    for entry in entries:
        if not entry.name.isdigit():
            continue
        comm = entry / "comm"
        try:
            if comm.is_file() and comm.read_text(encoding="utf-8", errors="replace").strip() == "vantio-loader":
                return True
        except OSError:
            continue
    return False


def _tc_has_clsact(iface: str) -> str:
    if not _IFACE.fullmatch(iface):
        return "NOT_VERIFIED"
    text = _read_only(["tc", "qdisc", "show", "dev", iface])
    if text and "clsact" in text:
        return "VERIFIED"
    return "NOT_VERIFIED"
