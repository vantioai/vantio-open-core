"""Source-level fixture tests for the Stage A installer. No AWS and no live Docker."""

from __future__ import annotations

import ast
import compileall
import copy
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE))

from tests.factory import default_files, host, pins_for, refresh_sums, write_bundle  # noqa: E402
from vantio_install import constants  # noqa: E402
from vantio_install.cli import main  # noqa: E402
from vantio_install.commands import observe_container_argv  # noqa: E402
from vantio_install.health import derive  # noqa: E402
from vantio_install.state_machine import transition  # noqa: E402
from vantio_install.support_bundle import build_support_bundle  # noqa: E402
from vantio_install.verifier import _recompute_health, verify  # noqa: E402
from vantio_install.errors import InstallError
from vantio_install.agent_sdk import remove_agent_sdks  # noqa: E402
from vantio_install.optics_cli import remove_optics_prefix  # noqa: E402

TX = "vantio-tx-11111111-1111-4111-8111-111111111111"
AS_OF = "2026-09-27T20:00:00-04:00"
NEEDLES = ("/home/vantioai", "vantio-sandbox", "absolute_control/secret.token")


class Harness:
    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="vantio-install-test-"))
        self.bundle = self.root / "bundle"
        self.state = self.root / "state" / "vantio" / "install"
        self.evidence = self.root / "evidence" / "vantio" / "tx"
        self.workload = self.root / "workload" / "roots" / "app"
        self.stage = self.root / "stage" / "vantio" / "pe"
        self.prefix = self.root / "prefix" / "vantio" / "opt"
        self.workload.mkdir(parents=True)
        self.files = files or default_files()
        self._orig = copy.deepcopy(constants.FROZEN_PINS)
        self.pins = pins_for(self.files)
        constants.FROZEN_PINS = self.pins
        write_bundle(self.bundle, self.pins, self.files)
        self.host = host()
        self.host_path = self.root / "host.json"
        self.config = {
            "install_mode": "observe-only",
            "enforcement": "NOT_ENABLED",
            "iface": "ens5",
            "workload_roots": [str(self.workload)],
            "evidence_root": str(self.evidence),
            "dry_run": True,
            "otlp": "DISABLED",
            "path_deny": "disabled",
            "traffic_control": "audit-only",
            "transfer_required": False,
            "transfer_source_cidrs": [],
            "artifact_source": "sealed_archive",
            "install_motion": "customer-local",
            "enterprise_inclusion": "OPTIONAL_SOURCE_ONLY_NOT_PACKAGED_AUTHORITY",
            "non_interactive": True,
            "stage_dir": str(self.stage),
            "prefix": str(self.prefix),
        }
        self.config_path = self.root / "config.json"

    def close(self) -> None:
        constants.FROZEN_PINS = self._orig
        shutil.rmtree(self.root, ignore_errors=True)

    def flush(self) -> None:
        self.host_path.write_text(json.dumps(self.host), encoding="utf-8")
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def argv(self, command: str, *, yes: bool = False, scope: str | None = None, state=None, evidence=None) -> list[str]:
        args = [
            command,
            "--bundle",
            str(self.bundle),
            "--config",
            str(self.config_path),
            "--state-dir",
            str(state or self.state),
            "--evidence-dir",
            str(evidence or self.evidence),
            "--fixture-host",
            str(self.host_path),
            "--transaction-id",
            TX,
            "--as-of",
            AS_OF,
            "--json",
        ]
        if yes:
            args.append("--yes")
        if scope:
            args.extend(["--scope", scope])
        return args

    def run(self, command: str, **kwargs) -> tuple[int, dict]:
        self.flush()
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(self.argv(command, **kwargs))
        return code, json.loads(buf.getvalue())

    def tx_file(self, name: str) -> Path:
        return self.state / "transactions" / TX / name

    def snapshot(self) -> dict:
        return json.loads(self.tx_file("HOST-SNAPSHOT.json").read_text(encoding="utf-8"))


class StageAInstallerTests(unittest.TestCase):
    def make(self, files: dict[str, bytes] | None = None) -> Harness:
        harness = Harness(files)
        self.addCleanup(harness.close)
        return harness

    def test_frozen_identities_and_cli_package_untouched(self) -> None:
        pins = constants.FROZEN_PINS
        self.assertEqual(pins["pe_source_commit"], "fab81efc08110506ff90847495197e7051a253b5")
        self.assertEqual(pins["pe_archive_sha256"], "72719cf4c590805378188da38a0d43c540e6722328268bde3955f07d2c3a9128")
        self.assertEqual(pins["pe_manifest_digest"], "sha256:4d932b93bf4c20983142d5f9bff1ea060d9407a19a5e8c9f59db29f7a4122553")
        self.assertEqual(pins["optics_cli_version"], "0.3.24")
        self.assertEqual(pins["optics_cli_sha256"], "82fe13ad6fc916ac67a670bd95fbf18b24389ecb383d81246e1d52cb96712a1f")
        self.assertEqual(pins["agent_sdk_npm_version"], "0.2.4")
        self.assertEqual(pins["agent_sdk_py_version"], "3.1.0")
        cli = json.loads((REPO / "packages" / "vantio-cli" / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(cli["version"], "0.3.24")
        sdk = json.loads((REPO / "packages" / "vantio-agent-sdk" / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(sdk["version"], "0.2.4")
        pyproject = (REPO / "packages" / "vantio-agent-sdk-py" / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = "3.1.0"', pyproject)

    def test_preflight_is_read_only(self) -> None:
        harness = self.make()
        code, body = harness.run("plan")
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "PLANNED")
        self.assertEqual(body["proof_state"], "NOT_PROVED")
        self.assertFalse(harness.prefix.exists())
        self.assertFalse(harness.stage.exists())
        self.assertEqual(harness.snapshot().get("containers"), [])
        self.assertNotIn("CUSTOMER_VALIDATED", json.dumps(body))
        archive = harness.bundle / "artifacts" / "phantom-engine" / harness.pins["pe_archive_name"]
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), harness.pins["pe_archive_sha256"])

    def test_plan_determinism(self) -> None:
        harness = self.make()
        code_a, body_a = harness.run("plan")
        code_b, body_b = harness.run(
            "plan",
            state=harness.root / "state-b" / "vantio" / "install",
            evidence=harness.root / "evidence-b" / "vantio" / "tx",
        )
        self.assertEqual(code_a, 0)
        self.assertEqual(code_b, 0)
        self.assertEqual(body_a["planned_steps"], body_b["planned_steps"])
        self.assertEqual(body_a["artifact_digests"], body_b["artifact_digests"])
        self.assertEqual(body_a["preflight_status"], body_b["preflight_status"])
        self.assertEqual(body_a["state"], body_b["state"])

    def test_repeat_plan_does_not_mutate(self) -> None:
        harness = self.make()
        harness.run("plan")
        code, body = harness.run("plan")
        self.assertEqual(code, 0)
        self.assertTrue(body.get("replayed"))
        self.assertFalse(harness.prefix.exists())

    def test_manifest_missing_section_blocks(self) -> None:
        harness = self.make()
        manifest = json.loads((harness.bundle / "MANIFEST.json").read_text(encoding="utf-8"))
        del manifest["bundle_id"]
        (harness.bundle / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
        refresh_sums(harness.bundle)
        code, body = harness.run("plan")
        self.assertEqual(code, 2, body)
        self.assertEqual(body["state"], "PREFLIGHT_BLOCKED")
        self.assertIn("PF-MANIFEST", body["failed_or_limiting_checks"])

    def test_artifact_mismatch_refuses(self) -> None:
        harness = self.make()
        archive = harness.bundle / "artifacts" / "phantom-engine" / harness.pins["pe_archive_name"]
        archive.write_bytes(archive.read_bytes() + b"drift")
        refresh_sums(harness.bundle)
        code, body = harness.run("plan")
        self.assertEqual(code, 2, body)
        self.assertIn("PF-ARTIFACT-PE", body["failed_or_limiting_checks"])
        self.assertFalse(harness.stage.exists())

    def test_tip_drift_refuses(self) -> None:
        harness = self.make()
        path = harness.bundle / "artifacts" / "phantom-engine" / "PHANTOM-ARTIFACT-MANIFEST.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["source_commit"] = constants.FROZEN_PINS["pe_prior_candidate_commit"]
        path.write_text(json.dumps(doc), encoding="utf-8")
        refresh_sums(harness.bundle)
        code, body = harness.run("plan")
        self.assertEqual(code, 2, body)
        self.assertIn("PF-ARTIFACT-PE", body["failed_or_limiting_checks"])

    def test_unsupported_platform_refuses_apply(self) -> None:
        harness = self.make()
        harness.host["uname_m"] = "aarch64"
        code, body = harness.run("plan")
        self.assertEqual(code, 3, body)
        self.assertEqual(body["state"], "UNSUPPORTED")
        apply_code, apply_body = harness.run("apply", yes=True)
        self.assertEqual(apply_code, 3, apply_body)
        self.assertFalse(harness.prefix.exists())

    def test_relative_and_dangerous_roots_refused(self) -> None:
        harness = self.make()
        harness.config["workload_roots"] = ["relative/workload"]
        code, body = harness.run("plan")
        self.assertEqual(code, 10, body)
        self.assertEqual(body["state"], "FAILED_SAFE")
        harness.config["workload_roots"] = ["/"]
        code, body = harness.run("plan")
        self.assertEqual(code, 10, body)
        harness.config["workload_roots"] = ["../etc/passwd"]
        code, body = harness.run("plan")
        self.assertEqual(code, 10, body)
        home = str(Path("/home") / "example" / "node" / "work")
        harness.config["workload_roots"] = [home]
        code, body = harness.run("plan")
        self.assertEqual(code, 10, body)
        self.assertFalse((harness.state / "transactions").exists())

    def test_disclosure_scan_blocks_matching_hash(self) -> None:
        needle = constants.DISCLOSURE_FORBIDDEN[0].encode("utf-8")
        files = default_files()
        files["archive"] = b"oci\n" + needle + b"\n"
        harness = self.make(files)
        code, body = harness.run("plan")
        self.assertEqual(code, 2, body)
        self.assertIn("PF-DISCLOSURE", body["failed_or_limiting_checks"])

    def test_ghcr_zero_cidr_and_enforce_refused(self) -> None:
        harness = self.make()
        harness.config["artifact_source"] = "ghcr"
        code, body = harness.run("plan")
        self.assertEqual(code, 2, body)
        self.assertIn("PF-GHCR-DEFAULT", body["failed_or_limiting_checks"])
        harness.config["artifact_source"] = "sealed_archive"
        harness.config["transfer_required"] = True
        harness.config["transfer_source_cidrs"] = ["0.0.0.0/0"]
        code, body = harness.run("plan")
        self.assertEqual(code, 2, body)
        self.assertIn("PF-TRANSFER-ALLOWLIST", body["failed_or_limiting_checks"])
        text = json.dumps(body)
        self.assertNotIn("open 0.0.0.0/0", text)
        harness.config["transfer_required"] = False
        harness.config["transfer_source_cidrs"] = []
        harness.config["enforcement"] = "ENABLED"
        code, body = harness.run("plan")
        self.assertEqual(code, 2, body)
        self.assertIn("PF-ENFORCEMENT-DEFAULT", body["failed_or_limiting_checks"])

    def test_docker_permission_and_memory_limitation(self) -> None:
        harness = self.make()
        harness.host["principal_can_talk_to_docker"] = False
        harness.host["sudo_available"] = False
        harness.host["privilege_mode"] = "UNKNOWN"
        code, body = harness.run("plan")
        self.assertEqual(code, 2, body)
        self.assertIn("PF-DOCKER-PERM", body["failed_or_limiting_checks"])
        harness.host = host()
        harness.host["mem_total_kib"] = int(1.9 * 1024 * 1024)
        code, body = harness.run("plan")
        self.assertEqual(code, 0, body)
        self.assertEqual(body["preflight_status"], "READY_WITH_LIMITATIONS")
        self.assertTrue(any(row["id"] == "PF-MEM" for row in body["limitations"]))
        apply_code, apply_body = harness.run("apply", yes=True)
        self.assertEqual(apply_code, 0, apply_body)
        self.assertEqual(apply_body["state"], "DEGRADED")
        self.assertEqual(apply_body["health_overall"], "PASS_WITH_LIMITATIONS")
        self.assertNotEqual(apply_body["health_overall"], "PASS")

    def test_apply_healthy_and_idempotent(self) -> None:
        harness = self.make()
        plan_code, plan_body = harness.run("plan")
        self.assertEqual(plan_code, 0, plan_body)
        code, body = harness.run("apply", yes=True)
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "HEALTHY")
        self.assertEqual(body["health_overall"], "PASS")
        self.assertEqual(body["proof_state"], "NOT_PROVED")
        self.assertEqual(body["enforcement"], "NOT_ENABLED")
        snap = harness.snapshot()
        self.assertEqual(len(snap["containers"]), 1)
        self.assertNotIn("--enforce", snap["containers"][0]["cmd"])
        joined = " ".join(" ".join(argv) for argv in snap["recorded_argv"])
        self.assertNotIn("--enforce", joined)
        self.assertNotIn("VANTIO_PHANTOM_DENY", joined)
        again, replay = harness.run("apply", yes=True)
        self.assertEqual(again, 0, replay)
        self.assertTrue(replay.get("replayed"))
        self.assertEqual(len(harness.snapshot()["containers"]), 1)

    def test_interrupted_resume_and_digest_mismatch(self) -> None:
        harness = self.make()
        harness.run("plan")
        harness.config["interrupt_after_step"] = "stage_pe_archive"
        code, body = harness.run("apply", yes=True)
        self.assertEqual(code, 5, body)
        self.assertEqual(body["state"], "INTERRUPTED")
        self.assertNotEqual(body.get("health_overall"), "PASS")
        self.assertEqual(harness.snapshot().get("containers"), [])
        status_code, status_body = harness.run("status")
        self.assertEqual(status_code, 5, status_body)
        self.assertEqual(status_body["state"], "INTERRUPTED")
        del harness.config["interrupt_after_step"]
        code, body = harness.run("apply", yes=True)
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "HEALTHY")
        self.assertEqual(len(harness.snapshot()["containers"]), 1)

        harness = self.make()
        harness.run("plan")
        harness.config["interrupt_after_step"] = "stage_pe_archive"
        harness.run("apply", yes=True)
        archive = harness.bundle / "artifacts" / "phantom-engine" / harness.pins["pe_archive_name"]
        archive.write_bytes(archive.read_bytes() + b"x")
        del harness.config["interrupt_after_step"]
        code, body = harness.run("apply", yes=True)
        self.assertEqual(code, 4, body)
        self.assertEqual(body["state"], "FAILED_SAFE")
        self.assertEqual(harness.snapshot().get("containers") or [], [])

    def test_dead_pid_status_becomes_interrupted(self) -> None:
        harness = self.make()
        harness.run("plan")
        tx_path = harness.tx_file("TRANSACTION.json")
        tx = json.loads(tx_path.read_text(encoding="utf-8"))
        tx["state"] = "APPLYING"
        tx["mutation_in_progress"] = True
        tx["owner_pid"] = 2_000_000_123
        tx_path.write_text(json.dumps(tx), encoding="utf-8")
        if os.path.exists(f"/proc/{tx['owner_pid']}"):
            self.skipTest("chosen pid is alive")
        code, body = harness.run("status")
        self.assertEqual(code, 5, body)
        self.assertEqual(body["state"], "INTERRUPTED")

    def test_missing_checkpoint_fails_closed(self) -> None:
        harness = self.make()
        harness.run("plan")
        harness.tx_file("PLAN.json").unlink()
        code, body = harness.run("apply", yes=True)
        self.assertEqual(code, 4, body)
        self.assertEqual(body["state"], "FAILED_SAFE")

    def test_no_optimistic_success_and_unknown_stays_unknown(self) -> None:
        harness = self.make()
        harness.run("plan")
        harness.config["simulate_missing"] = ["vantio-loader"]
        code, body = harness.run("apply", yes=True)
        self.assertEqual(code, 4, body)
        self.assertEqual(body["state"], "FAILED_SAFE")
        self.assertEqual(body["health_overall"], "FAIL")
        self.assertNotEqual(body["health_overall"], "PASS")

        harness = self.make()
        harness.run("plan")
        harness.config["simulate_probe_errors"] = ["process"]
        code, body = harness.run("apply", yes=True)
        self.assertEqual(code, 4, body)
        self.assertEqual(body["health_overall"], "UNKNOWN")
        self.assertEqual(body["state"], "FAILED_SAFE")
        self.assertEqual(body["proof_state"], "NOT_PROVED")

    def test_rollback_interruption_uninstall_residual_and_evidence(self) -> None:
        harness = self.make()
        harness.run("plan")
        harness.run("apply", yes=True)
        preflight_hash = hashlib.sha256(harness.tx_file("PREFLIGHT.json").read_bytes()).hexdigest()
        harness.config["rollback_interrupt_after_step"] = "start_pe_observe"
        code, body = harness.run("rollback", yes=True)
        self.assertEqual(code, 5, body)
        self.assertEqual(body["state"], "INTERRUPTED")
        self.assertTrue(harness.snapshot().get("images"))
        code, body = harness.run("rollback", yes=True)
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "ROLLED_BACK")
        self.assertNotEqual(body.get("health_overall"), "PASS")
        code, body = harness.run("verify-removal", scope="all")
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "VERIFIED_REMOVED")
        self.assertEqual(body["residual_result"], "EMPTY")
        self.assertEqual(preflight_hash, hashlib.sha256((harness.evidence / "PREFLIGHT.json").read_bytes()).hexdigest())

        harness = self.make()
        harness.run("plan")
        harness.run("apply", yes=True)
        evidence_hash = hashlib.sha256((harness.evidence / "PLAN.json").read_bytes()).hexdigest()
        harness.config["uninstall_leave"] = ["bpf_pins"]
        code, body = harness.run("uninstall", yes=True, scope="pe")
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "UNINSTALLED")
        code, body = harness.run("verify-removal", scope="pe")
        self.assertEqual(code, 2, body)
        self.assertEqual(body["state"], "RESIDUAL_PRESENT")
        self.assertTrue(any(item["kind"] == "bpf_pin" for item in body["residual_items"]))
        self.assertEqual(evidence_hash, hashlib.sha256((harness.evidence / "PLAN.json").read_bytes()).hexdigest())

        harness = self.make()
        harness.run("plan")
        harness.run("apply", yes=True)
        harness.run("uninstall", yes=True, scope="pe")
        code, body = harness.run("verify-removal", scope="pe")
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "VERIFIED_REMOVED")
        code, body = harness.run("verify-removal", scope="all")
        self.assertEqual(code, 2, body)
        self.assertEqual(body["state"], "RESIDUAL_PRESENT")

    def test_uncheckpointed_optics_prefix_is_not_verified_removed(self) -> None:
        harness = self.make()
        harness.run("plan")
        harness.run("apply", yes=True)
        harness.run("uninstall", yes=True, scope="all")
        code, body = harness.run("verify-removal", scope="all")
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "VERIFIED_REMOVED")
        self.assertFalse(harness.snapshot().get("optics_cli_version"))
        self.assertFalse((harness.prefix / "optics-cli-receipt.json").exists())
        binary = harness.prefix / "bin" / "vantio"
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_text("#!/bin/sh\nprintf '%s\\n' \"0.3.24\"\n", encoding="utf-8")
        binary.chmod(0o755)
        false_clean = verify(harness.evidence, harness.bundle)
        self.assertEqual(false_clean["result"], "FAIL")
        residual = next(row for row in false_clean["checks"] if row["id"] == "recompute-residual")
        self.assertEqual(residual["result"], "FAIL")
        self.assertEqual(residual["stated"], "EMPTY")
        self.assertEqual(residual["recomputed"], "RESIDUAL_PRESENT")
        code, body = harness.run("verify-removal", scope="all")
        self.assertNotEqual(code, 0, body)
        self.assertNotEqual(body["state"], "VERIFIED_REMOVED")
        self.assertEqual(body["state"], "RESIDUAL_PRESENT")
        self.assertNotEqual(body["residual_result"], "EMPTY")
        self.assertTrue(any(item.get("path") == "bin/vantio" for item in body["residual_items"]))

    def test_uncheckpointed_optics_prefix_is_removed_on_rollback(self) -> None:
        harness = self.make()
        harness.run("plan")
        path = harness.tx_file("TRANSACTION.json")
        tx = json.loads(path.read_text(encoding="utf-8"))
        tx["state"] = "FAILED_SAFE"
        tx["completed_steps"] = ["verify_artifacts", "ensure_node"]
        path.write_text(json.dumps(tx), encoding="utf-8")
        self.assertFalse((harness.tx_file("PARTIAL-MUTATIONS.json")).exists())
        binary = harness.prefix / "bin" / "vantio"
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_text("#!/bin/sh\nprintf '%s\\n' \"0.3.24\"\n", encoding="utf-8")
        binary.chmod(0o755)
        outside = harness.root / "outside-tree"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep\n", encoding="utf-8")
        escaped = harness.prefix / "lib" / "node_modules" / "@vantio" / "cli"
        escaped.parent.mkdir(parents=True, exist_ok=True)
        escaped.symlink_to(outside)
        code, body = harness.run("rollback", yes=True)
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "ROLLED_BACK")
        self.assertFalse(binary.exists())
        self.assertFalse(escaped.is_symlink())
        self.assertTrue((outside / "keep.txt").is_file())
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("install_optics_cli", saved["rollback_completed_steps"])
        self.assertNotIn("install_optics_cli", saved["completed_steps"])
        code, body = harness.run("verify-removal", scope="all")
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "VERIFIED_REMOVED")

    def test_uncheckpointed_sdk_prefix_is_not_verified_removed(self) -> None:
        harness = self.make()
        harness.run("plan")
        harness.run("apply", yes=True)
        harness.run("uninstall", yes=True, scope="all")
        code, body = harness.run("verify-removal", scope="all")
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "VERIFIED_REMOVED")
        self.assertFalse(harness.snapshot().get("agent_sdk_npm_version"))
        self.assertFalse(harness.snapshot().get("agent_sdk_py_version"))
        receipt = harness.prefix / "agent-sdk-receipt.json"
        receipt.write_text('{"marker":"vantio-install-receipt"}\n', encoding="utf-8")
        npm = harness.prefix / "lib" / "node_modules" / "@vantio" / "agent-sdk"
        npm.mkdir(parents=True)
        (npm / "package.json").write_text('{"name":"@vantio/agent-sdk","version":"0.2.4"}\n', encoding="utf-8")
        site = harness.prefix / "local" / "lib" / "python3.12" / "dist-packages"
        module = site / "vantio"
        module.mkdir(parents=True)
        (module / "__init__.py").write_text('__version__ = "3.1.0"\n', encoding="utf-8")
        dist = site / "vantio_agent_sdk-3.1.0.dist-info"
        dist.mkdir()
        (dist / "METADATA").write_text("Name: vantio-agent-sdk\nVersion: 3.1.0\n", encoding="utf-8")
        false_clean = verify(harness.evidence, harness.bundle)
        self.assertEqual(false_clean["result"], "FAIL")
        residual = next(row for row in false_clean["checks"] if row["id"] == "recompute-residual")
        self.assertEqual(residual["result"], "FAIL")
        self.assertEqual(residual["stated"], "EMPTY")
        self.assertEqual(residual["recomputed"], "RESIDUAL_PRESENT")
        code, body = harness.run("verify-removal", scope="all")
        self.assertNotEqual(code, 0, body)
        self.assertNotEqual(body["state"], "VERIFIED_REMOVED")
        self.assertEqual(body["state"], "RESIDUAL_PRESENT")
        self.assertNotEqual(body["residual_result"], "EMPTY")
        paths = {item.get("path") for item in body["residual_items"]}
        self.assertIn("lib/node_modules/@vantio/agent-sdk", paths)
        self.assertIn("local/lib/python3.12/dist-packages/vantio", paths)
        self.assertIn("local/lib/python3.12/dist-packages/vantio_agent_sdk-3.1.0.dist-info", paths)
        self.assertTrue(any(item.get("name") == "agent-sdk-receipt.json" for item in body["residual_items"]))

    def test_uncheckpointed_sdk_prefix_is_removed_on_rollback(self) -> None:
        harness = self.make()
        harness.run("plan")
        path = harness.tx_file("TRANSACTION.json")
        tx = json.loads(path.read_text(encoding="utf-8"))
        tx["state"] = "FAILED_SAFE"
        tx["completed_steps"] = ["verify_artifacts", "ensure_node"]
        tx["rollback_completed_steps"] = ["install_agent_sdks"]
        path.write_text(json.dumps(tx), encoding="utf-8")
        self.assertFalse((harness.tx_file("PARTIAL-MUTATIONS.json")).exists())
        outside = harness.root / "outside-tree"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep\n", encoding="utf-8")
        escaped = harness.prefix / "lib" / "node_modules" / "@vantio" / "agent-sdk"
        escaped.parent.mkdir(parents=True, exist_ok=True)
        escaped.symlink_to(outside)
        site = harness.prefix / "lib" / "python3.12" / "site-packages"
        module = site / "vantio"
        module.mkdir(parents=True)
        (module / "__init__.py").write_text('__version__ = "3.1.0"\n', encoding="utf-8")
        dist = site / "vantio_agent_sdk-3.1.0.dist-info"
        dist.mkdir()
        (dist / "METADATA").write_text("Name: vantio-agent-sdk\nVersion: 3.1.0\n", encoding="utf-8")
        receipt = harness.prefix / "agent-sdk-receipt.json"
        receipt.write_text('{"marker":"vantio-install-receipt"}\n', encoding="utf-8")
        code, body = harness.run("rollback", yes=True)
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "ROLLED_BACK")
        self.assertFalse(escaped.exists())
        self.assertFalse(module.exists())
        self.assertFalse(dist.exists())
        self.assertFalse(receipt.exists())
        self.assertTrue((outside / "keep.txt").is_file())
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("install_agent_sdks", saved["rollback_completed_steps"])
        self.assertNotIn("install_agent_sdks", saved["completed_steps"])
        code, body = harness.run("verify-removal", scope="all")
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "VERIFIED_REMOVED")

    def test_sdk_removal_does_not_follow_symlink_outside_prefix(self) -> None:
        harness = self.make()
        outside = harness.root / "outside-tree"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep\n", encoding="utf-8")
        link = harness.prefix / "local" / "lib" / "python3.12" / "dist-packages" / "vantio"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(outside)
        remove_agent_sdks(harness.prefix)
        self.assertFalse(link.exists())
        self.assertTrue((outside / "keep.txt").is_file())

    def test_optics_removal_does_not_follow_symlink_outside_prefix(self) -> None:
        harness = self.make()
        outside = harness.root / "outside-tree"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep\n", encoding="utf-8")
        link = harness.prefix / "lib" / "node_modules" / "@vantio" / "cli"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(outside)
        remove_optics_prefix(harness.prefix)
        self.assertFalse(link.exists())
        self.assertTrue((outside / "keep.txt").is_file())

    def test_unknown_residual_is_not_removed(self) -> None:
        harness = self.make()
        harness.run("plan")
        harness.run("apply", yes=True)
        harness.run("uninstall", yes=True, scope="all")
        harness.config["residual_probe_errors"] = ["bpf"]
        code, body = harness.run("verify-removal", scope="all")
        self.assertEqual(code, 4, body)
        self.assertEqual(body["state"], "FAILED_SAFE")
        self.assertEqual(body["residual_result"], "UNKNOWN")
        self.assertNotEqual(body["state"], "VERIFIED_REMOVED")

    def test_support_bundle_sanitizes(self) -> None:
        harness = self.make()
        harness.run("plan")
        harness.run("apply", yes=True)
        poison_key = "AKIA" + "IOSFODNN7EXAMPLE"
        pem = "-----BEGIN " + "RSA PRIVATE KEY-----\nabc\n-----END " + "RSA PRIVATE KEY-----"
        line = json.dumps(
            {
                "detail": f"leaked {poison_key} {pem} /home/vantioai/scratch Phantom-Box token ghp_abcdefghijklmnop CRM",
            }
        )
        with (harness.evidence / "APPLY-EVENT-LOG.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        build_support_bundle(harness.evidence, TX, harness.snapshot())
        archive = harness.evidence / f"vantio-support-{TX}.tar.gz"
        sidecar = Path(str(archive) + ".sha256")
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), sidecar.read_text(encoding="utf-8").split()[0])
        with tarfile.open(archive, "r:gz") as tar:
            blob = b""
            for member in tar.getmembers():
                self.assertFalse(member.name.startswith("/"))
                self.assertNotIn("..", Path(member.name).parts)
                extracted = tar.extractfile(member)
                if extracted is not None:
                    blob += extracted.read()
        self.assertNotIn(poison_key.encode("utf-8"), blob)
        self.assertNotIn(b"BEGIN RSA PRIVATE KEY", blob)
        self.assertNotIn(b"/home/vantioai", blob)
        self.assertNotIn(b"Phantom-Box", blob)
        self.assertNotIn(b"ghp_abcdefghijklmnop", blob)
        self.assertIn(b"[REDACTED_AWS_ACCESS_KEY]", blob)

    def test_verifier_ignores_exit_zero(self) -> None:
        harness = self.make()
        harness.run("plan")
        code, body = harness.run("apply", yes=True)
        self.assertEqual(code, 0, body)
        report = verify(harness.evidence, harness.bundle)
        self.assertEqual(report["result"], "PASS")
        self.assertFalse(report["trusted_installer_exit"])
        self.assertEqual(report["proof_state"], "NOT_PROVED")
        (harness.evidence / "INSTALLER-EXIT.json").write_text('{"exit_code": 0}\n', encoding="utf-8")
        archive = harness.bundle / "artifacts" / "phantom-engine" / harness.pins["pe_archive_name"]
        archive.write_bytes(b"not-the-sealed-archive\n")
        failed = verify(harness.evidence, harness.bundle)
        self.assertEqual(failed["result"], "FAIL")
        self.assertFalse(failed["trusted_installer_exit"])
        health = json.loads((harness.evidence / "HEALTH.json").read_text(encoding="utf-8"))
        health["overall"] = "PASS"
        (harness.evidence / "HEALTH.json").write_text(json.dumps(health), encoding="utf-8")
        snap = json.loads((harness.evidence / "HOST-SNAPSHOT.json").read_text(encoding="utf-8"))
        snap["processes"] = []
        (harness.evidence / "HOST-SNAPSHOT.json").write_text(json.dumps(snap), encoding="utf-8")
        archive.write_bytes(harness.files["archive"])
        tampered = verify(harness.evidence, harness.bundle)
        self.assertEqual(tampered["result"], "FAIL")

    def test_verifier_module_does_not_import_installer_success_path(self) -> None:
        source = (PACKAGE / "vantio_install" / "verifier.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        banned = {
            "vantio_install.engine",
            "vantio_install.health",
            "vantio_install.cli",
            "vantio_install.mutator",
            "vantio_install.preflight",
            "vantio_install.live_executor",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in banned:
                self.fail(node.module)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name, banned)

    def test_health_rules_match_between_copies(self) -> None:
        snapshot = host()
        snapshot["optics_cli_version"] = "0.3.24"
        snapshot["containers"] = [
            {"role": "phantom_engine", "status": "running", "cmd": ["--iface", "ens5"], "enforce": False}
        ]
        snapshot["processes"] = ["vantio-loader"]
        snapshot["bpf_pins"] = list(constants.BPF_PINS)
        snapshot["clsact_ifaces"] = ["ens5"]
        config = {"enforcement": "NOT_ENABLED", "path_deny": "disabled", "otlp": "DISABLED", "iface": "ens5"}
        self.assertEqual(derive(snapshot, config)["overall"], _recompute_health(snapshot, config, []))

    def test_observe_argv_shape(self) -> None:
        argv = observe_container_argv(
            tag=constants.FROZEN_PINS["pe_local_tag"],
            iface="ens5",
            name="vantio-pe-test",
        )
        self.assertNotIn("--enforce", argv)
        self.assertNotIn("VANTIO_PHANTOM_DENY", argv)
        self.assertNotIn("--privileged", argv)
        self.assertIn("--iface", argv)
        self.assertIn("ens5", argv)

    def test_illegal_transition_fails(self) -> None:
        with self.assertRaises(InstallError):
            transition("UNSUPPORTED", "PLANNED")
        with self.assertRaises(InstallError):
            transition("CREATED", "HEALTHY")

    def test_customer_surface_has_no_internal_paths_or_secrets(self) -> None:
        roots = [PACKAGE / "README.md", PACKAGE / "docs", PACKAGE / "config"]
        blobs = []
        for root in roots:
            if root.is_file():
                blobs.append(root.read_text(encoding="utf-8"))
            else:
                for path in root.rglob("*"):
                    if path.is_file():
                        blobs.append(path.read_text(encoding="utf-8"))
        text = "\n".join(blobs)
        for needle in NEEDLES:
            self.assertNotIn(needle, text)
        self.assertNotIn("CUSTOMER_VALIDATED", text)
        self.assertNotIn("PROVED_EXTERNAL", text)
        for path in PACKAGE.rglob("*"):
            if not path.is_file() or "tests" in path.parts or path.suffix in {".pyc"}:
                continue
            raw = path.read_text(encoding="utf-8", errors="ignore")
            self.assertIsNone(re.search(r"\bAKIA[0-9A-Z]{16}\b", raw), path)
            self.assertNotIn("BEGIN RSA PRIVATE KEY", raw)
            self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", raw)

    def test_defaults_are_observe_only(self) -> None:
        defaults = json.loads((PACKAGE / "config" / "defaults.observe-only.json").read_text(encoding="utf-8"))
        policy = json.loads((PACKAGE / "config" / "policy.observe-only.json").read_text(encoding="utf-8"))
        self.assertEqual(defaults["install_mode"], "observe-only")
        self.assertEqual(defaults["enforcement"], "NOT_ENABLED")
        self.assertEqual(policy["enforcement"], "NOT_ENABLED")
        self.assertEqual(defaults["artifact_source"], "sealed_archive")

    def test_packaging_and_compile(self) -> None:
        text = (PACKAGE / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('name = "vantio-install"', text)
        self.assertIn("0.1.0-stage-a", text)
        self.assertIn("vantio-install =", text)
        self.assertIn("vantio-verify =", text)
        self.assertTrue(compileall.compile_dir(str(PACKAGE / "vantio_install"), quiet=1))

    def test_cli_subprocess_mismatch_does_not_trust_success(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="vantio-install-cli-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        bundle = root / "bundle"
        files = default_files()
        real = copy.deepcopy(constants.FROZEN_PINS)
        write_bundle(bundle, real, files)
        host_path = root / "host.json"
        host_path.write_text(json.dumps(host()), encoding="utf-8")
        workload = root / "workload" / "roots" / "app"
        workload.mkdir(parents=True)
        config = {
            "install_mode": "observe-only",
            "enforcement": "NOT_ENABLED",
            "iface": "ens5",
            "workload_roots": [str(workload)],
            "evidence_root": str(root / "evidence" / "vantio" / "tx"),
            "otlp": "DISABLED",
            "path_deny": "disabled",
            "traffic_control": "audit-only",
            "transfer_required": False,
            "transfer_source_cidrs": [],
            "artifact_source": "sealed_archive",
            "install_motion": "customer-local",
            "enterprise_inclusion": "OPTIONAL_SOURCE_ONLY_NOT_PACKAGED_AUTHORITY",
            "stage_dir": str(root / "stage" / "vantio" / "pe"),
            "prefix": str(root / "prefix" / "vantio" / "opt"),
        }
        config_path = root / "config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PACKAGE)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "vantio_install",
                "plan",
                "--bundle",
                str(bundle),
                "--config",
                str(config_path),
                "--state-dir",
                str(root / "state" / "vantio" / "install"),
                "--evidence-dir",
                str(root / "evidence" / "vantio" / "tx"),
                "--fixture-host",
                str(host_path),
                "--transaction-id",
                TX,
                "--as-of",
                AS_OF,
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(PACKAGE),
            env=env,
        )
        self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
        body = json.loads(completed.stdout)
        self.assertEqual(body["state"], "PREFLIGHT_BLOCKED")
        self.assertEqual(body["proof_state"], "NOT_PROVED")
        self.assertNotEqual(body["state"], "PLANNED")


if __name__ == "__main__":
    unittest.main()
