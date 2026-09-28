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
from dataclasses import dataclass
from pathlib import Path

from vantio_install import constants
from vantio_install.commands import (
    docker_load_argv,
    docker_rmi_argv,
    docker_start_argv,
    docker_stop_rm_argv,
    docker_tag_argv,
    mkdir_argv,
    npm_install_argv,
    observe_container_argv,
    observe_env,
    pip_wheel_argv,
    tc_clsact_argv,
    tc_clsact_del_argv,
)
from vantio_install.errors import InstallError
from vantio_install.manifest import artifact_paths, load_manifest
from vantio_install.optics_cli import (
    observed_optics_cli_version,
    optics_cli_present,
    optics_cli_verified,
    remove_optics_prefix,
)
from vantio_install.paths import assert_safe_root
from vantio_install.preflight import run_preflight
from vantio_install.util import read_json, sha256_file, write_json

_ENV_GATE = "VANTIO_INSTALL_ALLOW_LIVE"
_IFACE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,14}$")
_SHELLS = {"sh", "bash", "dash", "zsh", "busybox", "sudo", "su"}
_META = (";", "|", "&", "`", "$(", "\n", "\r", ">", "<")
_ALLOWED_EXE = {"mkdir", "npm", "python3", "docker", "tc"}

STEP_OPERATIONS = {
    "install_optics_cli": ("mkdir_prefix", "install_optics_cli"),
    "install_agent_sdks": ("install_agent_sdk_npm", "install_agent_sdk_py"),
    "stage_pe_archive": ("mkdir_stage", "stage_pe_archive"),
    "docker_load": ("docker_load", "docker_tag"),
    "write_observe_config": ("mkdir_evidence", "write_observe_config", "o7_init"),
    "start_pe_observe": ("tc_clsact", "start_pe_observe"),
}

ROLLBACK_OPERATIONS = {
    "start_pe_observe": ("docker_stop", "docker_rm", "tc_clsact_del"),
    "docker_load": ("docker_rmi",),
    "stage_pe_archive": ("remove_stage",),
    "write_observe_config": ("remove_observe_config", "remove_o7_record"),
    "install_agent_sdks": ("remove_sdks",),
    "install_optics_cli": ("remove_optics",),
}

_START_STATES = {
    "apply": {"PLANNED", "INTERRUPTED", "APPLYING"},
    "rollback": {"HEALTHY", "DEGRADED", "FAILED_SAFE", "INTERRUPTED", "APPLYING", "ROLLING_BACK"},
    "uninstall": {"HEALTHY", "DEGRADED", "FAILED_SAFE", "INTERRUPTED", "UNINSTALLING"},
}

_RUNTIME_STATES = {
    "apply": {"APPLYING"},
    "rollback": {"ROLLING_BACK"},
    "uninstall": {"UNINSTALLING"},
}

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
    def __init__(self, returncode: int, timed_out: bool = False) -> None:
        self.returncode = returncode
        self.timed_out = timed_out


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
    if euid == 0:
        return True
    mode = str(host.get("privilege_mode", "UNKNOWN"))
    if mode == "sudo" and host.get("sudo_available") is True:
        return True
    if mode == "docker_group" and host.get("principal_can_talk_to_docker") is True:
        return True
    return False


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


def catalog_argv(op_type: str, grant: LiveGrant) -> list[str] | None:
    """Argv for process operations. None means a confined filesystem operation."""
    pin = constants.FROZEN_PINS
    prefix = str(grant.prefix)
    iface = grant.iface
    mapping: dict[str, list[str] | None] = {
        "mkdir_prefix": mkdir_argv(prefix),
        "mkdir_stage": mkdir_argv(str(grant.stage)),
        "mkdir_evidence": mkdir_argv(str(grant.evidence)),
        "install_optics_cli": npm_install_argv(str(grant.optics_tarball), prefix),
        "install_agent_sdk_npm": npm_install_argv(str(grant.sdk_npm), prefix),
        "install_agent_sdk_py": pip_wheel_argv(str(grant.sdk_wheel), prefix),
        "stage_pe_archive": None,
        "docker_load": docker_load_argv(str(grant.stage / grant.archive.name)),
        "docker_tag": docker_tag_argv(pin["pe_manifest_digest"], pin["pe_local_tag"]),
        "write_observe_config": None,
        "o7_init": None,
        "tc_clsact": tc_clsact_argv(iface),
        "start_pe_observe": observe_container_argv(tag=pin["pe_local_tag"], iface=iface, name=grant.container_name),
        "restart_pe_observe": docker_start_argv(grant.container_name),
        "docker_stop": docker_stop_rm_argv(grant.container_name)[0],
        "docker_rm": docker_stop_rm_argv(grant.container_name)[1],
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
    if argv is not None:
        reject_argv(argv)
        if "--enforce" in argv or "--privileged" in argv or "VANTIO_PHANTOM_DENY" in argv:
            _fail("An allowlisted command included an enforce flag.", failure_class="FAILED_SAFE")
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
        try:
            completed = subprocess.run(
                checked,
                shell=False,
                check=False,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ExecResult(124, True)
        except OSError as exc:
            _fail(f"The live command could not start: {exc.__class__.__name__}.", failure_class="FAILED_SAFE")
        return ExecResult(completed.returncode, False)
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
        if grant.stage.exists():
            confine(grant.stage, [grant.stage.parent])
            shutil.rmtree(grant.stage)
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
    if op_type == "remove_optics":
        remove_optics_prefix(grant.prefix)
        return
    if op_type == "remove_sdks":
        path = confine(grant.prefix / "agent-sdk-receipt.json", [grant.prefix])
        if path.is_file():
            path.unlink()
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
        if "--enforce" in supplied or "--privileged" in supplied or any("VANTIO_PHANTOM_DENY" in item for item in supplied):
            _fail("Refusing an enforce or privileged flag.", failure_class="FAILED_SAFE")
        if any(item.endswith(":latest") or item == "latest" for item in supplied):
            _fail("Refusing a mutable image tag.", failure_class="FAILED_SAFE")
        if supplied != list(expected):
            _fail(f"Refusing argv that is not the allowlisted command for {op_type}.", failure_class="FAILED_SAFE")
    if op_type in {"docker_load", "docker_tag", "stage_pe_archive", "start_pe_observe"}:
        _rehash_archive(grant)
    _rehash_inputs(op_type, grant)
    _append_op(grant, {"op": op_type, "phase": "PENDING", "transaction_id": grant.transaction_id})
    result: ExecResult | None = None
    if expected is not None:
        result = run_allowlisted(expected, timeout, runner)
        if result.timed_out:
            _append_op(grant, {"op": op_type, "phase": "INTERRUPTED", "transaction_id": grant.transaction_id})
            _fail(
                f"{op_type} timed out. The transaction is interrupted.",
                failure_class="INTERRUPTED",
                state="INTERRUPTED",
                exit_code=constants.EXIT_INTERRUPTED,
            )
    else:
        _filesystem(op_type, grant)
        result = ExecResult(0, False)
    if op_type == "install_optics_cli" and result.returncode == 0 and not result.timed_out:
        note_partial_mutation(grant.tx_dir, "install_optics_cli")
    status = observer.verify(op_type, grant) if observer is not None else "NOT_VERIFIED"
    if status != "VERIFIED" or result.returncode != 0:
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
    _append_op(grant, {"op": op_type, "phase": "VERIFIED", "transaction_id": grant.transaction_id})
    return delta


def execute_step(grant: LiveGrant, step_id: str, kind: str, runner, observer) -> tuple[list[dict], list[list[str]]]:
    table = STEP_OPERATIONS if kind == "apply" else ROLLBACK_OPERATIONS
    if step_id not in table:
        return [], []
    deltas: list[dict] = []
    recorded: list[list[str]] = []
    for op_type in table[step_id]:
        argv = catalog_argv(op_type, grant)
        delta = dispatch(grant, op_type, argv, runner=runner, observer=observer)
        deltas.append(delta)
        if argv:
            recorded.append(argv)
    return deltas, recorded


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
        _fail("Live mutations need root or the documented sudo or docker privilege.", failure_class="FAILED_SAFE")
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
    if state in _CLOSED or (command == "apply" and state in {"HEALTHY", "DEGRADED"}):
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
    if plan_doc.get("live_operations") != live_operation_ids():
        _fail("The plan is missing the live operation list.", failure_class="FAILED_SAFE")

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
        host=host,
        resuming=True,
        plan_present=True,
        config_present=True,
        bundle_digest_match=True,
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
    )


class ProductionObserver:
    """Read-only host checks. They do not receive the mutation's exit code."""

    def verify(self, op_type: str, grant: LiveGrant) -> str:
        try:
            if op_type == "install_optics_cli":
                expected = constants.FROZEN_PINS["optics_cli_version"]
                return "VERIFIED" if optics_cli_verified(grant.prefix, expected) else "NOT_VERIFIED"
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
            if op_type == "remove_optics":
                return "VERIFIED" if not optics_cli_present(grant.prefix) else "NOT_VERIFIED"
            if op_type in {"remove_stage", "remove_observe_config", "remove_o7_record", "remove_sdks"}:
                return "VERIFIED"
            if op_type == "docker_load":
                return _docker_image_present(constants.FROZEN_PINS["pe_manifest_digest"])
            if op_type == "docker_tag":
                return _docker_image_present(grant.tag)
            if op_type in {"start_pe_observe", "restart_pe_observe"}:
                running = _docker_running_observe(grant.container_name) == "VERIFIED"
                pins = _host_pins()
                loader = _loader_running()
                clsact = _tc_has_clsact(grant.iface) == "VERIFIED"
                if running and pins == list(constants.BPF_PINS) and loader and clsact:
                    return "VERIFIED"
                return "NOT_VERIFIED"
            if op_type in {"docker_stop", "docker_rm"}:
                return "VERIFIED" if _docker_running_observe(grant.container_name) == "NOT_VERIFIED" else "NOT_VERIFIED"
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
        if op_type == "install_optics_cli":
            version = observed_optics_cli_version(grant.prefix)
            if version:
                return {"optics_cli_version": version}
            return {}
        if op_type == "docker_tag":
            return {
                "images": [
                    {"tag": pin["pe_local_tag"], "digest": pin["pe_manifest_digest"], "role": "phantom_engine"}
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
            pins = _host_pins()
            if pins:
                delta["bpf_pins"] = pins
            if _tc_has_clsact(grant.iface) == "VERIFIED":
                delta["clsact_ifaces"] = [grant.iface]
            return delta
        if op_type in {"docker_stop", "docker_rm"}:
            return {"containers": [], "processes": [], "bpf_pins": [], "clsact_ifaces": []}
        if op_type == "docker_rmi":
            return {"images": []}
        if op_type == "remove_optics":
            return {"optics_cli_version": None}
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


def _docker_running_observe(name: str) -> str:
    text = _read_only(["docker", "inspect", "--format", "{{.State.Running}} {{json .Config.Cmd}}", name])
    if not text:
        return "NOT_VERIFIED"
    if text.startswith("true ") and "--enforce" not in text:
        return "VERIFIED"
    return "NOT_VERIFIED"


def _host_pins() -> list[str]:
    root = Path("/sys/fs/bpf")
    found = []
    for name in constants.BPF_PINS:
        try:
            if (root / name).exists():
                found.append(name)
        except OSError:
            continue
    return found


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
