"""Live-executor gates. Negative cases must not call the runner."""

from __future__ import annotations

import ast
import copy
import json
import os
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from tests.test_stage_a import AS_OF, TX, Harness  # noqa: E402
from vantio_install.engine import apply, rollback  # noqa: E402
from vantio_install.errors import InstallError  # noqa: E402
from vantio_install.live_executor import (  # noqa: E402
    ExecResult,
    authorize_live,
    catalog_argv,
    confine,
    dispatch,
    reject_argv,
    residual_result,
)
from vantio_install.util import sha256_file  # noqa: E402

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
        if op_type == "start_pe_observe":
            if self.running and "--enforce" not in self.cmd and "--privileged" not in self.cmd:
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
        self.assertNotIn("VANTIO_PHANTOM_DENY", joined)
        ops = (harness.tx_file("LIVE-OPS.jsonl")).read_text(encoding="utf-8")
        self.assertLess(ops.index("PENDING"), ops.index("VERIFIED"))
        code, body = rollback(self.ctx(harness, "rollback", lab))
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "ROLLED_BACK", body)
        self.assertEqual(body["proof_state"], "NOT_PROVED")
        self.assertTrue(any(argv[:2] == ["docker", "stop"] for argv in lab.calls))


if __name__ == "__main__":
    unittest.main()
