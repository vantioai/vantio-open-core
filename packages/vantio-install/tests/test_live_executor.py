"""Live-executor gates. Negative cases must not call the runner."""

from __future__ import annotations

import ast
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from tests.test_stage_a import AS_OF, TX, Harness  # noqa: E402
from vantio_install.engine import apply, rollback, uninstall, verify_removal  # noqa: E402
from vantio_install.errors import InstallError  # noqa: E402
from vantio_install import constants  # noqa: E402
from vantio_install.live_executor import (  # noqa: E402
    ExecResult,
    ProductionObserver,
    authorize_live,
    catalog_argv,
    confine,
    dispatch,
    reject_argv,
    residual_result,
)
from vantio_install.agent_sdk import (  # noqa: E402
    observed_agent_sdk_npm_version,
    observed_agent_sdk_py_version,
    remove_agent_sdks,
)
from vantio_install.optics_cli import observed_optics_cli_version  # noqa: E402
from vantio_install.util import sha256_file  # noqa: E402
from vantio_install.commands import observe_apparmor_opt  # noqa: E402
from vantio_install.pe_apparmor import pe_apparmor_profile_path, profile_text  # noqa: E402

ENV = "VANTIO_INSTALL_ALLOW_LIVE"


class Lab:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.loaded = False
        self.tagged = None
        self.running = False
        self.cmd: list[str] = []
        self.npm = False
        self.pip = False
        self.clsact: list[str] = []
        self.verified: list[str] = []
        self.apparmor = False

    def runner(self, argv: list[str], timeout: int) -> ExecResult:
        self.calls.append(list(argv))
        if argv[:2] == ["mkdir", "-p"]:
            Path(argv[-1]).mkdir(parents=True, exist_ok=True)
        elif argv[:3] == ["docker", "load", "-i"]:
            self.loaded = True
        elif argv[:2] == ["docker", "tag"]:
            self.tagged = argv[-1]
        elif argv[:2] == ["docker", "stop"]:
            self.running = False
        elif argv[:2] == ["docker", "rm"]:
            self.running = False
            self.cmd = []
        elif argv[:2] == ["docker", "rmi"]:
            self.tagged = None
            self.loaded = False
        elif argv[0] == "docker" and "run" in argv:
            self.running = True
            self.cmd = list(argv)
        elif argv[:2] == ["npm", "install"]:
            self.npm = True
        elif argv[:3] == ["python3", "-m", "pip"]:
            self.pip = True
        elif argv[:3] == ["tc", "qdisc", "replace"]:
            self.clsact.append(argv[4])
        elif argv[:3] == ["tc", "qdisc", "del"]:
            self.clsact = []
        elif argv[:2] == ["apparmor_parser", "-Kr"]:
            self.apparmor = True
        elif argv[:2] == ["apparmor_parser", "-KR"]:
            self.apparmor = False
        return ExecResult(0, False)

    def verify(self, op_type: str, grant) -> str:
        self.verified.append(op_type)
        if op_type == "mkdir_prefix":
            return "VERIFIED" if grant.prefix.is_dir() else "NOT_VERIFIED"
        if op_type == "mkdir_stage":
            return "VERIFIED" if grant.stage.is_dir() else "NOT_VERIFIED"
        if op_type == "mkdir_evidence":
            return "VERIFIED" if grant.evidence.is_dir() else "NOT_VERIFIED"
        if op_type == "install_optics_cli":
            return "VERIFIED" if self.npm else "NOT_VERIFIED"
        if op_type == "install_agent_sdk_npm":
            return "VERIFIED" if self.npm else "NOT_VERIFIED"
        if op_type == "install_agent_sdk_py":
            return "VERIFIED" if self.pip else "NOT_VERIFIED"
        if op_type == "stage_pe_archive":
            target = grant.stage / grant.archive.name
            return "VERIFIED" if target.is_file() else "NOT_VERIFIED"
        if op_type == "docker_load":
            return "VERIFIED" if self.loaded else "NOT_VERIFIED"
        if op_type == "docker_tag":
            return "VERIFIED" if self.tagged == grant.tag else "NOT_VERIFIED"
        if op_type == "write_observe_config":
            payload = json.loads(grant.observe_config.read_text(encoding="utf-8"))
            if payload.get("enforcement") == "NOT_ENABLED" and "--enforce" not in payload.get("cmd", []):
                return "VERIFIED"
            return "NOT_VERIFIED"
        if op_type == "o7_init":
            payload = json.loads((grant.evidence / "O7-RECORD.json").read_text(encoding="utf-8"))
            if payload.get("enforcement") == "NOT_ENABLED" and payload.get("host_enforcement") is False:
                return "VERIFIED"
            return "NOT_VERIFIED"
        if op_type == "tc_clsact":
            return "VERIFIED" if grant.iface in self.clsact else "NOT_VERIFIED"
        if op_type == "write_pe_apparmor":
            path = pe_apparmor_profile_path(grant.stage)
            if path.is_file() and path.read_text(encoding="utf-8") == profile_text():
                return "VERIFIED"
            return "NOT_VERIFIED"
        if op_type == "load_pe_apparmor":
            path = pe_apparmor_profile_path(grant.stage)
            if self.apparmor and path.is_file() and path.read_text(encoding="utf-8") == profile_text():
                return "VERIFIED"
            return "NOT_VERIFIED"
        if op_type == "unload_pe_apparmor":
            return "VERIFIED" if not self.apparmor else "NOT_VERIFIED"
        if op_type == "start_pe_observe":
            opt = observe_apparmor_opt()
            if (
                self.running
                and "--enforce" not in self.cmd
                and "--privileged" not in self.cmd
                and "apparmor=unconfined" not in self.cmd
                and opt in self.cmd
            ):
                return "VERIFIED"
            return "NOT_VERIFIED"
        if op_type in {"docker_stop", "docker_rm"}:
            return "VERIFIED" if not self.running else "NOT_VERIFIED"
        if op_type == "docker_rmi":
            return "VERIFIED" if not self.loaded and self.tagged is None else "NOT_VERIFIED"
        if op_type == "tc_clsact_del":
            return "VERIFIED" if grant.iface not in self.clsact else "NOT_VERIFIED"
        if op_type.startswith("remove_"):
            return "VERIFIED"
        return "NOT_VERIFIED"

    def observed_delta(self, op_type: str, grant) -> dict:
        from vantio_install import constants

        pin = constants.FROZEN_PINS
        if op_type == "install_optics_cli":
            return {"optics_cli_version": pin["optics_cli_version"]}
        if op_type == "docker_tag":
            return {"images": [{"tag": pin["pe_local_tag"], "digest": pin["pe_manifest_digest"], "role": "phantom_engine"}]}
        if op_type == "start_pe_observe":
            return {
                "containers": [
                    {
                        "name": grant.container_name,
                        "role": "phantom_engine",
                        "status": "running",
                        "image": pin["pe_local_tag"],
                        "cmd": ["--iface", grant.iface],
                        "enforce": False,
                    }
                ],
                "processes": ["vantio-loader"],
                "bpf_pins": list(constants.BPF_PINS),
                "clsact_ifaces": [grant.iface],
            }
        if op_type in {"docker_stop", "docker_rm"}:
            return {"containers": [], "processes": [], "bpf_pins": [], "clsact_ifaces": []}
        if op_type == "docker_rmi":
            return {"images": []}
        if op_type == "remove_optics":
            return {"optics_cli_version": None}
        return {}


def npm_sdk_root(prefix: Path) -> Path:
    return prefix / "lib" / "node_modules" / "@vantio" / "agent-sdk"


def py_sdk_site(prefix: Path, layout: str = "debian") -> Path:
    if layout == "debian":
        return prefix / "local" / "lib" / "python3.12" / "dist-packages"
    if layout == "posix":
        return prefix / "lib" / "python3.12" / "site-packages"
    raise AssertionError(layout)


def plant_npm_sdk(prefix: Path, version: str) -> Path:
    package = npm_sdk_root(prefix) / "package.json"
    package.parent.mkdir(parents=True, exist_ok=True)
    package.write_text(json.dumps({"name": "@vantio/agent-sdk", "version": version}) + "\n", encoding="utf-8")
    return package


def plant_py_sdk(
    prefix: Path,
    version: str,
    *,
    metadata: str | None = None,
    layout: str = "debian",
    declare: bool = True,
) -> Path:
    site = py_sdk_site(prefix, layout)
    site.mkdir(parents=True, exist_ok=True)
    for child in list(site.glob("vantio_agent_sdk-*.dist-info")) + list(site.glob("vantio-agent-sdk-*.dist-info")):
        shutil.rmtree(child)
    module = site / "vantio" / "__init__.py"
    module.parent.mkdir(parents=True, exist_ok=True)
    if declare:
        module.write_text('__version__ = "%s"\n' % version, encoding="utf-8")
    else:
        module.write_text("# installed without a declared version\n", encoding="utf-8")
    meta_version = version if metadata is None else metadata
    dist = site / ("vantio_agent_sdk-%s.dist-info" % meta_version)
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: vantio-agent-sdk\nVersion: %s\n" % meta_version,
        encoding="utf-8",
    )
    return module


def plant_cli(prefix: Path, version: str, *, executable: bool = True, manifest: str | None = None) -> Path:
    binary = prefix / "bin" / "vantio"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("#!/bin/sh\nprintf '%s\\n' " + json.dumps(version) + "\n", encoding="utf-8")
    binary.chmod(0o755 if executable else 0o644)
    if manifest is not None:
        package = prefix / "lib" / "node_modules" / "@vantio" / "cli" / "package.json"
        package.parent.mkdir(parents=True, exist_ok=True)
        package.write_text(json.dumps({"name": "@vantio/cli", "version": manifest}) + "\n", encoding="utf-8")
    return binary


class PrefixGate:
    """Production checks for prefix residuals. Lab checks for simulated PE operations.

    AppArmor load and unload stay on the lab observer. That observer records
    the apparmor_parser result and does not read securityfs.
    """

    _PRODUCTION = frozenset(
        {
            "install_optics_cli",
            "install_agent_sdk_npm",
            "install_agent_sdk_py",
            "remove_optics",
            "remove_sdks",
        }
    )

    def __init__(self, lab: Lab) -> None:
        self.lab = lab
        self.production = ProductionObserver()

    def verify(self, op_type: str, grant) -> str:
        if op_type in self._PRODUCTION:
            return self.production.verify(op_type, grant)
        return self.lab.verify(op_type, grant)

    def observed_delta(self, op_type: str, grant) -> dict:
        if op_type in self._PRODUCTION:
            return self.production.observed_delta(op_type, grant)
        return self.lab.observed_delta(op_type, grant)


class OpticsGate:
    """Production host check for Optics, lab observer for every other operation."""

    def __init__(self, lab: Lab, version: str) -> None:
        self.lab = lab
        self.version = version
        self.production = ProductionObserver()

    def runner(self, argv: list[str], timeout: int) -> ExecResult:
        result = self.lab.runner(argv, timeout)
        filename = constants.FROZEN_PINS["optics_cli_filename"]
        if argv[:2] == ["npm", "install"] and str(argv[-1]).endswith(filename):
            prefix = Path(argv[argv.index("--prefix") + 1])
            plant_cli(prefix, self.version, manifest=self.version)
        return result

    def verify(self, op_type: str, grant) -> str:
        if op_type in {"install_optics_cli", "remove_optics"}:
            return self.production.verify(op_type, grant)
        return self.lab.verify(op_type, grant)

    def observed_delta(self, op_type: str, grant) -> dict:
        if op_type in {"install_optics_cli", "remove_optics"}:
            return self.production.observed_delta(op_type, grant)
        return self.lab.observed_delta(op_type, grant)


class SdkGate:
    """Production host check for Agent SDKs, lab observer for every other operation."""

    def __init__(self, lab: Lab, npm_version: str | None, py_version: str | None) -> None:
        self.lab = lab
        self.npm_version = npm_version
        self.py_version = py_version
        self.production = ProductionObserver()

    def runner(self, argv: list[str], timeout: int) -> ExecResult:
        result = self.lab.runner(argv, timeout)
        pins = constants.FROZEN_PINS
        if argv[:2] == ["npm", "install"] and str(argv[-1]).endswith(pins["agent_sdk_npm_filename"]) and self.npm_version:
            plant_npm_sdk(Path(argv[argv.index("--prefix") + 1]), self.npm_version)
        wheel = pins["agent_sdk_py_wheel"]
        if argv[:3] == ["python3", "-m", "pip"] and str(argv[-1]).endswith(wheel) and self.py_version:
            plant_py_sdk(Path(argv[argv.index("--prefix") + 1]), self.py_version)
        return result

    def verify(self, op_type: str, grant) -> str:
        if op_type in {"install_agent_sdk_npm", "install_agent_sdk_py", "remove_sdks"}:
            return self.production.verify(op_type, grant)
        return self.lab.verify(op_type, grant)

    def observed_delta(self, op_type: str, grant) -> dict:
        if op_type in {"install_agent_sdk_npm", "install_agent_sdk_py", "remove_sdks"}:
            return self.production.observed_delta(op_type, grant)
        return self.lab.observed_delta(op_type, grant)


class LiveExecutorTests(unittest.TestCase):
    def make(self) -> Harness:
        harness = Harness()
        self.addCleanup(harness.close)
        return harness

    def set_env(self, value: str | None) -> None:
        old = os.environ.get(ENV)
        if value is None:
            os.environ.pop(ENV, None)
        else:
            os.environ[ENV] = value

        def restore() -> None:
            if old is None:
                os.environ.pop(ENV, None)
            else:
                os.environ[ENV] = old

        self.addCleanup(restore)

    def planned(self) -> Harness:
        harness = self.make()
        code, body = harness.run("plan")
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "PLANNED")
        return harness

    def parts(self, harness: Harness):
        tx_dir = harness.tx_file("TRANSACTION.json").parent
        tx = json.loads((tx_dir / "TRANSACTION.json").read_text(encoding="utf-8"))
        config = json.loads(harness.config_path.read_text(encoding="utf-8"))
        host = json.loads(harness.tx_file("HOST-SNAPSHOT.json").read_text(encoding="utf-8"))
        return tx, tx_dir, config, host

    def grant_for(self, harness: Harness, *, command: str = "apply", host=None, config=None, euid: int = 0, plan_sha: str | None = None, accept: bool = True):
        tx, tx_dir, loaded, snapshot = self.parts(harness)
        plan = tx_dir / "PLAN.json"
        return authorize_live(
            command=command,
            tx=tx,
            tx_dir=tx_dir,
            config=config or loaded,
            bundle=harness.bundle,
            host=host or snapshot,
            plan_path=plan,
            plan_sha256=plan_sha if plan_sha is not None else sha256_file(plan),
            accept_live_mutations=accept,
            euid=euid,
        )

    def arm(self, harness: Harness, state: str = "APPLYING") -> None:
        path = harness.tx_file("TRANSACTION.json")
        tx = json.loads(path.read_text(encoding="utf-8"))
        tx["state"] = state
        path.write_text(json.dumps(tx), encoding="utf-8")

    def ctx(self, harness: Harness, command: str, lab: Lab, *, flag: bool = True, euid: int = 0):
        plan = harness.tx_file("PLAN.json")
        return {
            "command": command,
            "bundle": harness.bundle,
            "config_path": harness.config_path,
            "state_dir": harness.state,
            "evidence_dir": harness.evidence,
            "fixture_host": None,
            "transaction_id": TX,
            "as_of": AS_OF,
            "yes": True,
            "scope": "all",
            "dry_run_flag": False,
            "accept_live_mutations": flag,
            "plan_path": plan,
            "plan_sha256": sha256_file(plan),
            "live_runner": lab.runner,
            "live_observer": lab,
            "live_euid": euid,
        }

    def test_live_env_alone_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        lab = Lab()
        before = harness.snapshot().get("containers")
        with self.assertRaises(InstallError) as caught:
            apply(self.ctx(harness, "apply", lab, flag=False))
        self.assertEqual(caught.exception.failure_class, "FAILED_SAFE")
        self.assertEqual(caught.exception.exit_code, 4)
        self.assertEqual(lab.calls, [])
        self.assertEqual(json.loads(harness.tx_file("TRANSACTION.json").read_text())["state"], "PLANNED")
        self.assertEqual(harness.snapshot().get("containers"), before)
        self.assertFalse(harness.prefix.exists())

    def test_live_flag_alone_refuses(self) -> None:
        harness = self.planned()
        self.set_env(None)
        lab = Lab()
        with self.assertRaises(InstallError) as caught:
            apply(self.ctx(harness, "apply", lab, flag=True))
        self.assertEqual(caught.exception.exit_code, 4)
        self.assertIn("together", str(caught.exception))
        self.assertEqual(lab.calls, [])
        self.assertEqual(json.loads(harness.tx_file("TRANSACTION.json").read_text())["state"], "PLANNED")

    def test_live_env_not_exact_one_refuses(self) -> None:
        harness = self.planned()
        self.set_env(None)
        for value in ("true", "yes", "0", ""):
            os.environ[ENV] = value
            with self.assertRaises(InstallError):
                self.grant_for(harness)
        os.environ.pop(ENV, None)

    def test_live_flag_rejected_on_plan_status_verify(self) -> None:
        harness = self.make()
        from vantio_install.cli import main

        for command in ("plan", "status", "verify-removal"):
            buf_code = []
            import io
            from contextlib import redirect_stdout

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = main(harness.argv(command) + ["--i-accept-live-mutations"])
            body = json.loads(buf.getvalue())
            buf_code.append(code)
            self.assertEqual(code, 4, body)
            self.assertEqual(body["state"], "FAILED_SAFE")
            self.assertIn("only accepted on apply", body["message"])
        self.assertFalse(harness.prefix.exists())

    def test_live_missing_privilege_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        host = harness.snapshot()
        host["privilege_mode"] = "UNKNOWN"
        host["sudo_available"] = False
        host["principal_can_talk_to_docker"] = False
        with self.assertRaises(InstallError) as caught:
            self.grant_for(harness, host=host, euid=1000)
        self.assertIn("root", str(caught.exception))

    def test_live_preflight_blocked_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        host = harness.snapshot()
        host["docker_binary"] = False
        with self.assertRaises(InstallError) as caught:
            self.grant_for(harness, host=host)
        self.assertIn("PF-DOCKER", str(caught.exception))

    def test_live_unknown_mandatory_preflight_refuses(self) -> None:
        from vantio_install.live_executor import _fail

        with self.assertRaises(InstallError) as caught:
            _fail("Mandatory preflight PF-BTF is UNKNOWN.", failure_class="FAILED_SAFE")
        self.assertIn("UNKNOWN", str(caught.exception))
        harness = self.planned()
        self.set_env("1")
        host = harness.snapshot()
        host["mem_total_kib"] = None
        with self.assertRaises(InstallError) as caught:
            self.grant_for(harness, host=host)
        self.assertIn("Memory was not observed", str(caught.exception))

    def test_live_unapproved_limitation_refuses(self) -> None:
        harness = self.make()
        harness.config["install_motion"] = "operator-remote-assist"
        code, body = harness.run("plan")
        self.assertEqual(code, 0, body)
        self.set_env("1")
        with self.assertRaises(InstallError) as caught:
            self.grant_for(harness)
        self.assertIn("PF-OPERATOR-SSH-ASSUMPTION", str(caught.exception))

    def test_live_rolled_back_transaction_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        path = harness.tx_file("TRANSACTION.json")
        tx = json.loads(path.read_text(encoding="utf-8"))
        tx["state"] = "ROLLED_BACK"
        path.write_text(json.dumps(tx), encoding="utf-8")
        with self.assertRaises(InstallError) as caught:
            self.grant_for(harness)
        self.assertIn("ROLLED_BACK", str(caught.exception))
        tx["state"] = "HEALTHY"
        path.write_text(json.dumps(tx), encoding="utf-8")
        lab = Lab()
        with self.assertRaises(InstallError) as caught:
            apply(self.ctx(harness, "apply", lab))
        self.assertIn("committed", str(caught.exception))
        self.assertEqual(lab.calls, [])

    def test_live_invalidated_plan_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        plan = harness.tx_file("PLAN.json")
        doc = json.loads(plan.read_text(encoding="utf-8"))
        doc["rollback_steps"] = []
        plan.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(InstallError) as caught:
            self.grant_for(harness, plan_sha=sha256_file(plan))
        self.assertIn("rollback", str(caught.exception))

    def test_live_missing_plan_hash_binding_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        tx, tx_dir, config, host = self.parts(harness)
        with self.assertRaises(InstallError) as caught:
            authorize_live(
                command="apply",
                tx=tx,
                tx_dir=tx_dir,
                config=config,
                bundle=harness.bundle,
                host=host,
                plan_path=None,
                plan_sha256=None,
                accept_live_mutations=True,
                euid=0,
            )
        self.assertIn("--plan", str(caught.exception))

    def test_live_plan_sha256_mismatch_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        with self.assertRaises(InstallError) as caught:
            self.grant_for(harness, plan_sha="0" * 64)
        self.assertIn("plan hash", str(caught.exception))

    def test_live_artifact_hash_mismatch_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        grant = self.grant_for(harness)
        archive = grant.archive
        archive.write_bytes(b"tampered-archive\n")
        self.arm(harness, "APPLYING")
        lab = Lab()
        with self.assertRaises(InstallError) as caught:
            dispatch(grant, "stage_pe_archive", None, runner=lab.runner, observer=lab)
        self.assertIn("changed after authorization", str(caught.exception))
        self.assertEqual(lab.calls, [])

    def test_live_pe_identity_mismatch_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        from tests.factory import refresh_sums
        from vantio_install import constants

        manifest = harness.bundle / "artifacts" / "phantom-engine" / "PHANTOM-ARTIFACT-MANIFEST.json"
        doc = json.loads(manifest.read_text(encoding="utf-8"))
        doc["source_commit"] = constants.FROZEN_PINS["pe_prior_candidate_commit"]
        manifest.write_text(json.dumps(doc), encoding="utf-8")
        refresh_sums(harness.bundle)
        original = constants.FROZEN_PINS["pe_source_commit"]
        constants.FROZEN_PINS["pe_source_commit"] = constants.FROZEN_PINS["pe_prior_candidate_commit"]
        try:
            with self.assertRaises(InstallError) as caught:
                self.grant_for(harness)
            self.assertIn("tip", str(caught.exception))
        finally:
            constants.FROZEN_PINS["pe_source_commit"] = original

    def test_live_arch_not_x86_64_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        host = harness.snapshot()
        host["uname_m"] = "aarch64"
        with self.assertRaises(InstallError) as caught:
            self.grant_for(harness, host=host)
        self.assertIn("x86_64", str(caught.exception))

    def test_live_missing_tracefs_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        host = harness.snapshot()
        host["tracefs_mounted"] = False
        with self.assertRaises(InstallError) as caught:
            self.grant_for(harness, host=host)
        self.assertIn("tracefs", str(caught.exception))

    def test_older_plan_operation_list_names_the_writer_installer(self) -> None:
        harness = self.planned()
        self.set_env("1")
        plan = harness.tx_file("PLAN.json")
        doc = json.loads(plan.read_text(encoding="utf-8"))
        original = list(doc["live_operations"])
        doc["live_operations"] = [op for op in original if "apparmor" not in op]
        self.assertTrue(doc["live_operations"])
        self.assertNotEqual(doc["live_operations"], original)
        plan.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(InstallError) as caught:
            self.grant_for(harness, plan_sha=sha256_file(plan))
        self.assertIn("installer that wrote it", str(caught.exception))
        doc["live_operations"] = []
        plan.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(InstallError) as caught:
            self.grant_for(harness, plan_sha=sha256_file(plan))
        self.assertIn("missing the live operation list", str(caught.exception))

    def test_live_missing_btf_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        host = harness.snapshot()
        host["btf_vmlinux_exists"] = False
        with self.assertRaises(InstallError) as caught:
            self.grant_for(harness, host=host)
        self.assertIn("BTF", str(caught.exception))

    def test_live_path_escape_refuses(self) -> None:
        harness = self.planned()
        stage = harness.stage
        stage.mkdir(parents=True)
        with self.assertRaises(InstallError):
            confine(stage / ".." / ".." / ".." / "escaped", [stage])
        link = stage / "link"
        link.symlink_to(harness.root)
        with self.assertRaises(InstallError):
            confine(link / "file", [stage])

    def test_live_enforce_mode_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        config = json.loads(harness.config_path.read_text(encoding="utf-8"))
        config["enforcement"] = "ENABLED"
        with self.assertRaises(InstallError) as caught:
            self.grant_for(harness, config=config)
        self.assertIn("observe-only", str(caught.exception))

    def test_live_unknown_operation_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        grant = self.grant_for(harness)
        self.arm(harness)
        lab = Lab()
        with self.assertRaises(InstallError) as caught:
            dispatch(grant, "systemctl", ["systemctl", "start", "vantio"], runner=lab.runner, observer=lab)
        self.assertIn("allowlist", str(caught.exception))
        self.assertEqual(lab.calls, [])

    def test_live_extra_argv_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        grant = self.grant_for(harness)
        self.arm(harness)
        lab = Lab()
        argv = catalog_argv("start_pe_observe", grant) + ["--privileged"]
        with self.assertRaises(InstallError) as caught:
            dispatch(grant, "start_pe_observe", argv, runner=lab.runner, observer=lab)
        self.assertIn("privileged", str(caught.exception))
        self.assertEqual(lab.calls, [])
        unconfined = catalog_argv("start_pe_observe", grant)
        slot = unconfined.index(observe_apparmor_opt())
        unconfined[slot] = "apparmor=unconfined"
        with self.assertRaises(InstallError) as caught:
            dispatch(grant, "start_pe_observe", unconfined, runner=lab.runner, observer=lab)
        self.assertIn("AppArmor", str(caught.exception))
        self.assertEqual(lab.calls, [])
        default_profile = catalog_argv("start_pe_observe", grant)
        default_profile[default_profile.index(observe_apparmor_opt())] = "apparmor=docker-default"
        with self.assertRaises(InstallError) as caught:
            dispatch(grant, "start_pe_observe", default_profile, runner=lab.runner, observer=lab)
        self.assertIn("AppArmor", str(caught.exception))
        self.assertEqual(lab.calls, [])
        forged = ["apparmor_parser", "-r", "/tmp/other-profile"]
        with self.assertRaises(InstallError) as caught:
            dispatch(grant, "load_pe_apparmor", forged, runner=lab.runner, observer=lab)
        self.assertIn("allowlisted", str(caught.exception))
        self.assertEqual(lab.calls, [])
        swapped = pe_apparmor_profile_path(grant.stage)
        swapped.parent.mkdir(parents=True, exist_ok=True)
        swapped.write_text("profile other { file, }\n", encoding="utf-8")
        with self.assertRaises(InstallError) as caught:
            dispatch(grant, "load_pe_apparmor", catalog_argv("load_pe_apparmor", grant), runner=lab.runner, observer=lab)
        self.assertIn("bytes changed", str(caught.exception))
        self.assertEqual(lab.calls, [])

    def test_live_mutable_tag_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        grant = self.grant_for(harness)
        self.arm(harness)
        lab = Lab()
        argv = ["docker", "tag", grant.tag, "vantio-phantom-engine:latest"]
        with self.assertRaises(InstallError) as caught:
            dispatch(grant, "docker_tag", argv, runner=lab.runner, observer=lab)
        self.assertIn("mutable", str(caught.exception))
        self.assertEqual(lab.calls, [])

    def test_live_arbitrary_image_package_iface_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        grant = self.grant_for(harness)
        self.arm(harness)
        lab = Lab()
        image = catalog_argv("start_pe_observe", grant)
        image[-3] = "public/image:unpinned"
        package = catalog_argv("install_optics_cli", grant)
        package[-1] = "/tmp/not-the-sealed-cli.tgz"
        iface = catalog_argv("tc_clsact", grant)
        iface[4] = "eth99"
        for op, argv in (
            ("start_pe_observe", image),
            ("install_optics_cli", package),
            ("tc_clsact", iface),
        ):
            with self.assertRaises(InstallError):
                dispatch(grant, op, argv, runner=lab.runner, observer=lab)
        self.assertEqual(lab.calls, [])

    def test_live_shell_injection_refuses(self) -> None:
        source = (PACKAGE / "vantio_install" / "live_executor.py").read_text(encoding="utf-8")
        self.assertIn("shell=False", source)
        self.assertNotIn("shell=True", source)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotEqual(node.func.attr, "system")
        with self.assertRaises(InstallError):
            reject_argv(["bash", "-c", "docker run --privileged x"])
        with self.assertRaises(InstallError):
            reject_argv(["docker", "run", "image;touch /tmp/pwned"])
        with self.assertRaises(InstallError):
            reject_argv("docker run --enforce")  # type: ignore[arg-type]

    def test_live_rollback_without_dual_gate_refuses(self) -> None:
        harness = self.planned()
        code, body = harness.run("apply", yes=True)
        self.assertEqual(body["state"], "HEALTHY", body)
        self.assertEqual(code, 0)
        containers = harness.snapshot().get("containers")
        self.set_env("1")
        lab = Lab()
        with self.assertRaises(InstallError):
            rollback(self.ctx(harness, "rollback", lab, flag=False))
        self.assertEqual(lab.calls, [])
        self.assertEqual(json.loads(harness.tx_file("TRANSACTION.json").read_text())["state"], "HEALTHY")
        self.assertEqual(harness.snapshot().get("containers"), containers)

    def test_live_uninstall_without_transaction_refuses(self) -> None:
        harness = self.planned()
        self.set_env("1")
        tx_path = harness.tx_file("TRANSACTION.json")
        tx = json.loads(tx_path.read_text(encoding="utf-8"))
        tx["state"] = "HEALTHY"
        tx_path.write_text(json.dumps(tx), encoding="utf-8")
        plan = harness.tx_file("PLAN.json")
        doc = json.loads(plan.read_text(encoding="utf-8"))
        doc["transaction_id"] = "vantio-tx-22222222-2222-4222-8222-222222222222"
        plan.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(InstallError) as caught:
            self.grant_for(harness, command="uninstall", plan_sha=sha256_file(plan))
        self.assertIn("different transaction", str(caught.exception))

    def test_live_residual_found_is_not_pass(self) -> None:
        self.assertEqual(residual_result([{"kind": "container"}], []), "RESIDUAL_FOUND")
        self.assertEqual(residual_result([], []), "EMPTY")
        self.assertNotEqual(residual_result([{"kind": "bpf_pin"}], []), "PASS")
        self.assertEqual(residual_result([], ["bpf"]), "UNKNOWN")
        harness = self.planned()
        code, body = harness.run("apply", yes=True)
        self.assertEqual(body["state"], "HEALTHY", body)
        path = harness.tx_file("TRANSACTION.json")
        tx = json.loads(path.read_text(encoding="utf-8"))
        tx["state"] = "UNINSTALLED"
        path.write_text(json.dumps(tx), encoding="utf-8")
        from vantio_install.cli import main
        import io
        from contextlib import redirect_stdout

        args = [arg for arg in harness.argv("verify-removal") if arg != "--fixture-host"]
        # argv always inserts the fixture path after the flag. Drop the pair.
        cleaned = []
        skip = False
        for arg in harness.argv("verify-removal"):
            if skip:
                skip = False
                continue
            if arg == "--fixture-host":
                skip = True
                continue
            cleaned.append(arg)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(cleaned)
        body = json.loads(buf.getvalue())
        self.assertEqual(code, 2, body)
        self.assertEqual(body["residual_result"], "RESIDUAL_FOUND")
        self.assertNotEqual(body["residual_result"], "PASS")
        self.assertEqual(body["proof_state"], "NOT_PROVED")
        self.assertEqual(body["state"], "RESIDUAL_FOUND")

    def test_live_exit_zero_without_verification_is_not_success(self) -> None:
        harness = self.planned()
        self.set_env("1")
        grant = self.grant_for(harness)
        self.arm(harness)

        class Silent:
            def runner(self, argv, timeout):
                return ExecResult(0, False)

            def verify(self, op_type, grant):
                return "NOT_VERIFIED"

            def observed_delta(self, op_type, grant):
                return {}

        lab = Silent()
        with self.assertRaises(InstallError) as caught:
            dispatch(grant, "docker_load", catalog_argv("docker_load", grant), runner=lab.runner, observer=lab)
        self.assertEqual(caught.exception.failure_class, "ROLLBACK_REQUIRED")
        self.assertNotEqual(caught.exception.state, "HEALTHY")

    def test_live_timeout_is_interrupted(self) -> None:
        harness = self.planned()
        self.set_env("1")
        grant = self.grant_for(harness)
        self.arm(harness)

        def runner(argv, timeout):
            return ExecResult(0, True)

        class Observer:
            def verify(self, op_type, grant):
                raise AssertionError("a timeout must not be verified")

            def observed_delta(self, op_type, grant):
                return {}

        with self.assertRaises(InstallError) as caught:
            dispatch(grant, "docker_load", catalog_argv("docker_load", grant), runner=runner, observer=Observer())
        self.assertEqual(caught.exception.state, "INTERRUPTED")
        self.assertEqual(caught.exception.failure_class, "INTERRUPTED")
        self.assertEqual(caught.exception.exit_code, 5)

    def test_live_verification_failure_requires_rollback(self) -> None:
        harness = self.planned()
        self.set_env("1")
        grant = self.grant_for(harness)
        self.arm(harness)

        class Unknown:
            def runner(self, argv, timeout):
                return ExecResult(0, False)

            def verify(self, op_type, grant):
                return "UNKNOWN"

            def observed_delta(self, op_type, grant):
                return {"containers": [{"role": "phantom_engine", "status": "running"}]}

        with self.assertRaises(InstallError) as caught:
            dispatch(grant, "start_pe_observe", catalog_argv("start_pe_observe", grant), runner=Unknown().runner, observer=Unknown())
        self.assertEqual(caught.exception.failure_class, "ROLLBACK_REQUIRED")
        text = (harness.tx_file("LIVE-OPS.jsonl")).read_text(encoding="utf-8")
        self.assertIn("PENDING", text)
        self.assertNotIn("VERIFIED", text)

    def test_live_allowlisted_apply_records_argv_and_verifies(self) -> None:
        harness = self.planned()
        self.set_env("1")
        low = copy.deepcopy(harness.snapshot())
        low["mem_total_kib"] = 2 * 1024 * 1024
        bounded = self.grant_for(harness, host=low)
        self.assertEqual(bounded.command, "apply")
        self.assertEqual(bounded.transaction_id, TX)
        lab = Lab()
        code, body = apply(self.ctx(harness, "apply", lab))
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "HEALTHY", body)
        self.assertEqual(body["proof_state"], "NOT_PROVED")
        self.assertTrue(lab.calls)
        self.assertIn("start_pe_observe", lab.verified)
        joined = " ".join(" ".join(argv) for argv in lab.calls)
        self.assertNotIn("--enforce", joined)
        self.assertNotIn("--privileged", joined)
        self.assertNotIn("apparmor=unconfined", joined)
        self.assertNotIn("PERFMON", joined)
        self.assertNotIn("VANTIO_PHANTOM_DENY", joined)
        self.assertIn(observe_apparmor_opt(), joined)
        self.assertIn("apparmor_parser -Kr", joined)
        self.assertIn("/sys/fs/bpf:/sys/fs/bpf", joined)
        self.assertIn("/sys/kernel/tracing:/sys/kernel/tracing", joined)
        self.assertNotIn("/sys/kernel/debug/tracing", joined)
        self.assertEqual(joined.count("--security-opt"), 1)
        ops = (harness.tx_file("LIVE-OPS.jsonl")).read_text(encoding="utf-8")
        self.assertLess(ops.index("PENDING"), ops.index("VERIFIED"))
        code, body = rollback(self.ctx(harness, "rollback", lab))
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "ROLLED_BACK", body)
        self.assertEqual(body["proof_state"], "NOT_PROVED")
        self.assertTrue(any(argv[:2] == ["docker", "stop"] for argv in lab.calls))
        self.assertTrue(any(argv[:2] == ["apparmor_parser", "-KR"] for argv in lab.calls))

    def test_optics_cli_present_passes_host_check_and_checkpoints(self) -> None:
        harness = self.planned()
        self.set_env("1")
        version = constants.FROZEN_PINS["optics_cli_version"]
        gate = OpticsGate(Lab(), version)
        code, body = apply(self.ctx(harness, "apply", gate))
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "HEALTHY", body)
        tx = json.loads(harness.tx_file("TRANSACTION.json").read_text(encoding="utf-8"))
        self.assertIn("install_optics_cli", tx["completed_steps"])
        binary = harness.prefix / "bin" / "vantio"
        self.assertTrue(binary.is_file())
        self.assertEqual(harness.snapshot().get("optics_cli_version"), version)
        self.assertFalse(harness.tx_file("PARTIAL-MUTATIONS.json").exists())
        code, body = rollback(self.ctx(harness, "rollback", gate))
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "ROLLED_BACK", body)
        self.assertFalse(binary.exists())
        self.assertFalse((harness.prefix / "lib" / "node_modules" / "@vantio" / "cli").exists())

    def test_optics_host_check_uses_binary_not_the_pin_constant(self) -> None:
        harness = self.planned()
        self.set_env("1")
        grant = self.grant_for(harness)
        observer = ProductionObserver()
        self.assertEqual(observer.verify("install_optics_cli", grant), "NOT_VERIFIED")
        version = constants.FROZEN_PINS["optics_cli_version"]
        plant_cli(harness.prefix, version, manifest="9.9.9")
        self.assertEqual(observer.verify("install_optics_cli", grant), "VERIFIED")
        self.assertEqual(observer.observed_delta("install_optics_cli", grant)["optics_cli_version"], version)
        plant_cli(harness.prefix, "9.9.9", manifest=version)
        self.assertEqual(observed_optics_cli_version(harness.prefix), "9.9.9")
        self.assertEqual(observer.verify("install_optics_cli", grant), "NOT_VERIFIED")
        plant_cli(harness.prefix, version, executable=False, manifest=version)
        self.assertEqual(observer.verify("install_optics_cli", grant), "VERIFIED")

    def test_missing_optics_cli_requires_rollback(self) -> None:
        harness = self.planned()
        self.set_env("1")
        lab = Lab()
        ctx = self.ctx(harness, "apply", lab)
        ctx["live_observer"] = ProductionObserver()
        code, body = apply(ctx)
        self.assertEqual(code, 4, body)
        self.assertEqual(body["state"], "FAILED_SAFE")
        self.assertEqual(body["live_failure_class"], "ROLLBACK_REQUIRED")
        tx = json.loads(harness.tx_file("TRANSACTION.json").read_text(encoding="utf-8"))
        self.assertNotIn("install_optics_cli", tx["completed_steps"])
        self.assertIn("install_optics_cli", tx["rollback_required_steps"])
        partial = json.loads(harness.tx_file("PARTIAL-MUTATIONS.json").read_text(encoding="utf-8"))
        self.assertIn("install_optics_cli", partial["steps"])
        self.assertFalse((harness.prefix / "bin" / "vantio").exists())
        self.assertIsNone(harness.snapshot().get("optics_cli_version"))
        rollback_ctx = self.ctx(harness, "rollback", lab)
        rollback_ctx["live_observer"] = ProductionObserver()
        code, body = rollback(rollback_ctx)
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "ROLLED_BACK", body)

    def test_wrong_optics_version_rolls_back_uncheckpointed_prefix(self) -> None:
        harness = self.planned()
        self.set_env("1")
        lab = Lab()

        def runner(argv: list[str], timeout: int) -> ExecResult:
            result = lab.runner(argv, timeout)
            filename = constants.FROZEN_PINS["optics_cli_filename"]
            if argv[:2] == ["npm", "install"] and str(argv[-1]).endswith(filename):
                plant_cli(Path(argv[argv.index("--prefix") + 1]), "9.9.9", manifest="9.9.9")
            return result

        ctx = self.ctx(harness, "apply", lab)
        ctx["live_runner"] = runner
        ctx["live_observer"] = ProductionObserver()
        code, body = apply(ctx)
        self.assertEqual(code, 4, body)
        self.assertEqual(body["live_failure_class"], "ROLLBACK_REQUIRED")
        binary = harness.prefix / "bin" / "vantio"
        self.assertTrue(binary.is_file())
        tx = json.loads(harness.tx_file("TRANSACTION.json").read_text(encoding="utf-8"))
        self.assertNotIn("install_optics_cli", tx["completed_steps"])
        rollback_ctx = self.ctx(harness, "rollback", lab)
        rollback_ctx["live_observer"] = ProductionObserver()
        code, body = rollback(rollback_ctx)
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "ROLLED_BACK", body)
        self.assertFalse(binary.exists())
        self.assertFalse((harness.prefix / "lib" / "node_modules" / "@vantio" / "cli").exists())

    def test_sdk_packages_present_pass_host_check_and_checkpoint(self) -> None:
        harness = self.planned()
        self.set_env("1")
        pins = constants.FROZEN_PINS
        gate = SdkGate(Lab(), pins["agent_sdk_npm_version"], pins["agent_sdk_py_version"])
        code, body = apply(self.ctx(harness, "apply", gate))
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "HEALTHY", body)
        tx = json.loads(harness.tx_file("TRANSACTION.json").read_text(encoding="utf-8"))
        self.assertIn("install_agent_sdks", tx["completed_steps"])
        self.assertTrue((npm_sdk_root(harness.prefix) / "package.json").is_file())
        self.assertTrue((py_sdk_site(harness.prefix) / "vantio" / "__init__.py").is_file())
        self.assertEqual(harness.snapshot().get("agent_sdk_npm_version"), pins["agent_sdk_npm_version"])
        self.assertEqual(harness.snapshot().get("agent_sdk_py_version"), pins["agent_sdk_py_version"])
        self.assertFalse(harness.tx_file("PARTIAL-MUTATIONS.json").exists())
        code, body = rollback(self.ctx(harness, "rollback", gate))
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "ROLLED_BACK", body)
        self.assertFalse(npm_sdk_root(harness.prefix).exists())
        self.assertFalse((py_sdk_site(harness.prefix) / "vantio").exists())
        self.assertFalse(list(py_sdk_site(harness.prefix).glob("vantio_agent_sdk-*.dist-info")))
        self.assertIsNone(harness.snapshot().get("agent_sdk_npm_version"))
        self.assertIsNone(harness.snapshot().get("agent_sdk_py_version"))

    def test_sdk_host_check_uses_package_tree_not_the_pin_constant(self) -> None:
        harness = self.planned()
        self.set_env("1")
        grant = self.grant_for(harness)
        observer = ProductionObserver()
        pins = constants.FROZEN_PINS
        npm_pin = pins["agent_sdk_npm_version"]
        py_pin = pins["agent_sdk_py_version"]
        self.assertEqual(observer.verify("install_agent_sdk_npm", grant), "NOT_VERIFIED")
        self.assertEqual(observer.verify("install_agent_sdk_py", grant), "NOT_VERIFIED")
        plant_npm_sdk(harness.prefix, npm_pin)
        self.assertEqual(observer.verify("install_agent_sdk_npm", grant), "VERIFIED")
        self.assertEqual(observer.observed_delta("install_agent_sdk_npm", grant)["agent_sdk_npm_version"], npm_pin)
        plant_npm_sdk(harness.prefix, "9.9.9")
        self.assertEqual(observed_agent_sdk_npm_version(harness.prefix), "9.9.9")
        self.assertEqual(observer.verify("install_agent_sdk_npm", grant), "NOT_VERIFIED")
        plant_py_sdk(harness.prefix, "9.9.9", metadata=py_pin)
        self.assertEqual(observed_agent_sdk_py_version(harness.prefix), "9.9.9")
        self.assertEqual(observer.verify("install_agent_sdk_py", grant), "NOT_VERIFIED")
        plant_py_sdk(harness.prefix, py_pin, metadata="9.9.9")
        self.assertEqual(observer.verify("install_agent_sdk_py", grant), "VERIFIED")
        self.assertEqual(observer.observed_delta("install_agent_sdk_py", grant)["agent_sdk_py_version"], py_pin)
        plant_py_sdk(harness.prefix, py_pin, metadata=py_pin, declare=False)
        self.assertEqual(observed_agent_sdk_py_version(harness.prefix), py_pin)
        self.assertEqual(observer.verify("install_agent_sdk_py", grant), "VERIFIED")
        plant_py_sdk(harness.prefix, py_pin, metadata="9.9.9", declare=False)
        self.assertEqual(observer.verify("install_agent_sdk_py", grant), "NOT_VERIFIED")
        plant_py_sdk(harness.prefix, "9.9.9")
        plant_py_sdk(harness.prefix, py_pin, layout="posix")
        self.assertIsNone(observed_agent_sdk_py_version(harness.prefix))
        self.assertEqual(observer.verify("install_agent_sdk_py", grant), "NOT_VERIFIED")
        shutil.rmtree(py_sdk_site(harness.prefix))
        self.assertEqual(observer.verify("install_agent_sdk_py", grant), "VERIFIED")
        posix = py_sdk_site(harness.prefix, "posix")
        module = posix / "vantio"
        dist = posix / ("vantio_agent_sdk-%s.dist-info" % py_pin)
        shutil.rmtree(module)
        self.assertTrue(dist.is_dir())
        self.assertEqual(observer.verify("install_agent_sdk_py", grant), "NOT_VERIFIED")
        self.assertEqual(observer.verify("remove_sdks", grant), "NOT_VERIFIED")
        cli = harness.prefix / "lib" / "node_modules" / "@vantio" / "cli" / "package.json"
        cli.parent.mkdir(parents=True, exist_ok=True)
        cli.write_text('{"name":"@vantio/cli","version":"0.3.24"}\n', encoding="utf-8")
        remove_agent_sdks(harness.prefix)
        self.assertTrue(cli.is_file())
        receipt = harness.prefix / "agent-sdk-receipt.json"
        receipt.write_text("{}\n", encoding="utf-8")
        self.assertEqual(observer.verify("remove_sdks", grant), "NOT_VERIFIED")
        remove_agent_sdks(harness.prefix)
        self.assertEqual(observer.verify("remove_sdks", grant), "VERIFIED")
        self.assertFalse(receipt.exists())
        self.assertFalse(npm_sdk_root(harness.prefix).exists())
        self.assertFalse(module.exists())
        self.assertFalse(dist.exists())

    def test_missing_sdks_require_rollback(self) -> None:
        harness = self.planned()
        self.set_env("1")
        gate = SdkGate(Lab(), None, None)
        code, body = apply(self.ctx(harness, "apply", gate))
        self.assertEqual(code, 4, body)
        self.assertEqual(body["state"], "FAILED_SAFE")
        self.assertEqual(body["live_failure_class"], "ROLLBACK_REQUIRED")
        tx = json.loads(harness.tx_file("TRANSACTION.json").read_text(encoding="utf-8"))
        self.assertIn("install_optics_cli", tx["completed_steps"])
        self.assertNotIn("install_agent_sdks", tx["completed_steps"])
        self.assertIn("install_agent_sdks", tx["rollback_required_steps"])
        partial = json.loads(harness.tx_file("PARTIAL-MUTATIONS.json").read_text(encoding="utf-8"))
        self.assertIn("install_agent_sdks", partial["steps"])
        self.assertFalse(npm_sdk_root(harness.prefix).exists())
        self.assertIsNone(harness.snapshot().get("agent_sdk_npm_version"))
        self.assertIsNone(harness.snapshot().get("agent_sdk_py_version"))
        code, body = rollback(self.ctx(harness, "rollback", gate))
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "ROLLED_BACK", body)

    def test_wrong_sdk_version_rolls_back_uncheckpointed_trees(self) -> None:
        harness = self.planned()
        self.set_env("1")
        pins = constants.FROZEN_PINS
        gate = SdkGate(Lab(), pins["agent_sdk_npm_version"], "9.9.9")
        code, body = apply(self.ctx(harness, "apply", gate))
        self.assertEqual(code, 4, body)
        self.assertEqual(body["live_failure_class"], "ROLLBACK_REQUIRED")
        npm_tree = npm_sdk_root(harness.prefix)
        py_module = py_sdk_site(harness.prefix) / "vantio"
        self.assertTrue((npm_tree / "package.json").is_file())
        self.assertTrue(py_module.is_dir())
        tx = json.loads(harness.tx_file("TRANSACTION.json").read_text(encoding="utf-8"))
        self.assertNotIn("install_agent_sdks", tx["completed_steps"])
        partial = json.loads(harness.tx_file("PARTIAL-MUTATIONS.json").read_text(encoding="utf-8"))
        self.assertIn("install_agent_sdks", partial["steps"])
        code, body = rollback(self.ctx(harness, "rollback", gate))
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "ROLLED_BACK", body)
        self.assertFalse(npm_tree.exists())
        self.assertFalse(py_module.exists())
        self.assertFalse(list(py_sdk_site(harness.prefix).glob("vantio_agent_sdk-*.dist-info")))

    def verify_live(self, harness: Harness, scope: str = "all") -> tuple[int, dict]:
        return verify_removal(
            {
                "command": "verify-removal",
                "bundle": harness.bundle,
                "config_path": harness.config_path,
                "state_dir": harness.state,
                "evidence_dir": harness.evidence,
                "fixture_host": None,
                "transaction_id": TX,
                "as_of": AS_OF,
                "scope": scope,
                "accept_live_mutations": False,
                "yes": False,
                "dry_run_flag": False,
            }
        )

    def plant_residual_prefix(self, harness: Harness) -> None:
        pins = constants.FROZEN_PINS
        plant_cli(harness.prefix, pins["optics_cli_version"], manifest=pins["optics_cli_version"])
        plant_npm_sdk(harness.prefix, pins["agent_sdk_npm_version"])
        plant_py_sdk(harness.prefix, pins["agent_sdk_py_version"])

    def assert_prefix_residuals_gone(self, harness: Harness) -> None:
        self.assertFalse((harness.prefix / "bin" / "vantio").exists())
        self.assertFalse(npm_sdk_root(harness.prefix).exists())
        self.assertFalse((py_sdk_site(harness.prefix) / "vantio").exists())
        self.assertFalse(list(py_sdk_site(harness.prefix).glob("vantio_agent_sdk-*.dist-info")))

    def test_apparmor_host_check_uses_a_fixture_profile_list(self) -> None:
        harness = self.planned()
        self.set_env("1")
        grant = self.grant_for(harness)
        directory = Path(tempfile.mkdtemp(prefix="vantio-aa-obs-"))
        self.addCleanup(lambda: shutil.rmtree(directory, ignore_errors=True))
        absent = directory / "no-profiles"
        self.assertEqual(
            ProductionObserver(apparmor_profiles=absent).verify("unload_pe_apparmor", grant),
            "VERIFIED",
        )
        unreadable = directory / "not-a-file"
        unreadable.mkdir()
        self.assertEqual(
            ProductionObserver(apparmor_profiles=unreadable).verify("unload_pe_apparmor", grant),
            "UNKNOWN",
        )
        listed = directory / "profiles"
        listed.write_text("vantio-pe-observe (enforce)\n", encoding="utf-8")
        self.assertEqual(
            ProductionObserver(apparmor_profiles=listed).verify("unload_pe_apparmor", grant),
            "NOT_VERIFIED",
        )
        self.assertEqual(Lab().verify("unload_pe_apparmor", grant), "VERIFIED")

    def test_residual_found_dual_gated_rollback_clears_prefix(self) -> None:
        harness = self.planned()
        code, body = harness.run("apply", yes=True)
        self.assertEqual(body["state"], "HEALTHY", body)
        code, body = harness.run("rollback", yes=True)
        self.assertEqual(body["state"], "ROLLED_BACK", body)
        code, body = harness.run("verify-removal", scope="all")
        self.assertEqual(body["state"], "VERIFIED_REMOVED", body)
        self.plant_residual_prefix(harness)
        code, body = self.verify_live(harness)
        self.assertEqual(code, 2, body)
        self.assertEqual(body["state"], "RESIDUAL_FOUND", body)
        self.assertEqual(body["residual_result"], "RESIDUAL_FOUND")
        self.assertNotEqual(body["state"], "VERIFIED_REMOVED")
        self.assertTrue(any(item.get("path") == "bin/vantio" for item in body["residual_items"]))
        binary = harness.prefix / "bin" / "vantio"
        self.assertTrue(binary.is_file())
        lab = Lab()
        with self.assertRaises(InstallError) as caught:
            apply(self.ctx(harness, "apply", lab))
        self.assertIn("RESIDUAL_FOUND", str(caught.exception))
        self.assertEqual(lab.calls, [])
        self.assertTrue(binary.is_file())
        with self.assertRaises(InstallError):
            rollback(self.ctx(harness, "rollback", lab, flag=False))
        self.assertTrue(binary.is_file())
        self.assertEqual(json.loads(harness.tx_file("TRANSACTION.json").read_text())["state"], "RESIDUAL_FOUND")
        self.set_env("1")
        ctx = self.ctx(harness, "rollback", lab)
        ctx["live_observer"] = PrefixGate(lab)
        code, body = rollback(ctx)
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "ROLLED_BACK", body)
        self.assert_prefix_residuals_gone(harness)
        code, body = self.verify_live(harness)
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "VERIFIED_REMOVED", body)
        self.assertEqual(body["residual_result"], "EMPTY")

    def test_residual_found_dual_gated_uninstall_clears_prefix(self) -> None:
        harness = self.planned()
        code, body = harness.run("apply", yes=True)
        self.assertEqual(body["state"], "HEALTHY", body)
        code, body = harness.run("rollback", yes=True)
        self.assertEqual(body["state"], "ROLLED_BACK", body)
        self.plant_residual_prefix(harness)
        code, body = self.verify_live(harness)
        self.assertEqual(body["state"], "RESIDUAL_FOUND", body)
        self.assertNotEqual(body["residual_result"], "EMPTY")
        self.set_env("1")
        lab = Lab()
        blocked = self.ctx(harness, "uninstall", lab, flag=False)
        blocked["scope"] = "optics"
        with self.assertRaises(InstallError):
            uninstall(blocked)
        self.assertTrue((harness.prefix / "bin" / "vantio").is_file())
        self.assertEqual(json.loads(harness.tx_file("TRANSACTION.json").read_text())["state"], "RESIDUAL_FOUND")
        ctx = self.ctx(harness, "uninstall", lab)
        ctx["scope"] = "pe"
        ctx["live_observer"] = PrefixGate(lab)
        code, body = uninstall(ctx)
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "UNINSTALLED", body)
        self.assertTrue((harness.prefix / "bin" / "vantio").is_file())
        self.assertTrue(any(argv[:2] == ["apparmor_parser", "-KR"] for argv in lab.calls))
        code, body = self.verify_live(harness)
        self.assertEqual(body["state"], "RESIDUAL_FOUND", body)
        self.assertNotEqual(body["state"], "VERIFIED_REMOVED")
        ctx = self.ctx(harness, "uninstall", lab)
        ctx["scope"] = "optics"
        ctx["live_observer"] = PrefixGate(lab)
        code, body = uninstall(ctx)
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "UNINSTALLED", body)
        self.assert_prefix_residuals_gone(harness)
        code, body = self.verify_live(harness)
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "VERIFIED_REMOVED", body)
        self.assertEqual(body["residual_result"], "EMPTY")


if __name__ == "__main__":
    unittest.main()
