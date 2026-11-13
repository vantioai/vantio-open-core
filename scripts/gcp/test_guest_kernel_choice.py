#!/usr/bin/env python3
"""Guest kernel choice for the enforcement proof. No cloud calls."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import enforcement_proof as ep
import offline_deliver as od


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "gcp-lab-enforcement-proof.yml"
GATE = ROOT / ".github" / "workflows" / "gcp-lab-cost-gate.yml"
ALLOWLIST = ROOT / "scripts" / "gcp" / "pe-git-sha-allowlist.txt"
GO = "zach-run-go-placeholder"
HOST = "proof81"
PIN = ep.PE_GIT_SHA
GATE_JSON = json.dumps({"expected_oop_usd": "0", "abort": False})


def _env(**extra: str) -> dict[str, str]:
    env = {
        "PE_GIT_SHA": PIN,
        "PROOF_SLICE": "full",
        "PROOF_RUN_GO": GO,
        "PROOF_HOST_NAME": HOST,
        "PROOF_UNINSTALL_APPROVAL": "",
        "STOP_AFTER_MINUTES": "120",
        "INSTANCE_NAME": "",
        "GCP_LAB_PROJECT": "vantio-lab-oct08",
        "GITHUB_RUN_ID": "12",
        "GCP_LAB_NOW_EPOCH": "1800000000",
    }
    env.update(extra)
    return env


def _loader(directory: Path) -> None:
    directory.mkdir()
    binary = directory / "vantio-loader"
    binary.write_bytes(b"\x7fELFnot-a-real-loader")
    script = directory / "enforcement_proof_lab.sh"
    script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    (directory / "loader.sha256").write_text(hashlib.sha256(binary.read_bytes()).hexdigest() + "\n", encoding="utf-8")
    (directory / "script.sha256").write_text(hashlib.sha256(script.read_bytes()).hexdigest() + "\n", encoding="utf-8")
    (directory / "ldd.txt").write_text("\tlibc.so.6 => /lib/libc.so.6\n", encoding="utf-8")
    (directory / "build-sha").write_text(PIN + "\n", encoding="utf-8")


class GuestKernelChoiceTests(unittest.TestCase):
    def test_known_kernels_map_and_other_values_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = str(Path(tmp) / "startup.sh")
            Path(script).write_text("#!/bin/bash\n", encoding="utf-8")
            default = " ".join(ep.instance_create_argv(_env(), script))
            six_eight = " ".join(ep.instance_create_argv(_env(PROOF_GUEST_KERNEL="6.8"), script))
            seven = " ".join(ep.instance_create_argv(_env(PROOF_GUEST_KERNEL="7.0"), script))
            twelve = " ".join(ep.instance_create_argv(_env(PROOF_GUEST_KERNEL="6.12"), script))
        self.assertIn("--image-family=ubuntu-2404-lts-amd64", default)
        self.assertIn("--image-project=ubuntu-os-cloud", default)
        self.assertNotIn("debian-cloud", default)
        self.assertEqual(default, six_eight)
        self.assertIn("--image-family=ubuntu-2604-lts-amd64", seven)
        self.assertIn("--image-project=ubuntu-os-cloud", seven)
        self.assertNotIn("ubuntu-2404-lts-amd64", seven)
        self.assertIn("--image-family=debian-13", twelve)
        self.assertIn("--image-project=debian-cloud", twelve)
        self.assertEqual(ep.precheck(_env()), 0)
        for kernel in ("6.8", "7.0", "6.12"):
            self.assertEqual(ep.precheck(_env(PROOF_GUEST_KERNEL=kernel)), 0)
        for kernel in ("5.8", "6.1", "6.80", "ubuntu-2604", "7", "debian-13"):
            self.assertEqual(ep.precheck(_env(PROOF_GUEST_KERNEL=kernel)), 1)
            with self.assertRaises(SystemExit) as caught:
                ep.instance_create_argv(_env(PROOF_GUEST_KERNEL=kernel), script)
            self.assertEqual(caught.exception.code, "guest_kernel")
        plan = {
            "project_id": "vantio-lab-oct08",
            "name": "vantio-gcp-lab-12",
            "public_ip": False,
            "service_account": None,
            "network": od.NETWORK,
            "subnet": od.SUBNET,
            "labels": od.offline_labels(1_800_000_000, 120),
            "image_family": "ubuntu-2204-lts",
            "image_project": "ubuntu-os-cloud",
        }
        with self.assertRaises(SystemExit) as caught:
            od.offline_create_argv(plan, script)
        self.assertEqual(caught.exception.code, "image")

    def test_release_must_start_with_the_chosen_version(self) -> None:
        self.assertTrue(ep.kernel_release_matches("6.8.0-100-generic", "6.8"))
        self.assertTrue(ep.kernel_release_matches("7.0.0-1008-gcp", "7.0"))
        self.assertTrue(ep.kernel_release_matches("6.12.11-amd64", "6.12"))
        self.assertFalse(ep.kernel_release_matches("6.80.0", "6.8"))
        self.assertFalse(ep.kernel_release_matches("6.1.0-amd64", "6.12"))
        self.assertFalse(ep.kernel_release_matches("7.00.0", "7.0"))
        self.assertFalse(ep.kernel_release_matches("6.8.0\n6.12.0", "6.8"))

    def test_a_failed_image_resolve_does_not_create(self) -> None:
        class Fake:
            def __init__(self) -> None:
                self.created = 0

            def image(self, _project: str, _family: str) -> str:
                raise SystemExit("image")

            def create(self, _env: dict[str, str]) -> str:
                self.created += 1
                raise AssertionError("created")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _loader(root / "loader")
            fake = Fake()
            env = _env(
                GCP_LAB_EXECUTE="1",
                GCP_LAB_GATE_JSON=GATE_JSON,
                PROOF_GUEST_KERNEL="7.0",
                LOADER_DIR=str(root / "loader"),
                EVIDENCE_DIR=str(root / "evidence"),
                RUNNER_TEMP=str(root),
            )
            self.assertEqual(ep.run_proof(env, fake), 2)  # type: ignore[arg-type]
            body = json.loads((root / "evidence" / "enforcement-proof.json").read_text(encoding="utf-8"))
        self.assertEqual(fake.created, 0)
        self.assertEqual(body["stopped"], "image")
        self.assertEqual(body["guest_kernel"], "7.0")
        self.assertEqual(body["image_family"], "ubuntu-2604-lts-amd64")
        self.assertEqual(body["live_enforcement"], "NOT_PROVEN")
        self.assertEqual(body["instance_name"], "")

    def test_a_wrong_uname_stops_before_a_phase(self) -> None:
        class Fake:
            def __init__(self) -> None:
                self.commands: list[str] = []
                self.created = 0

            def image(self, project: str, family: str) -> str:
                return f"https://www.googleapis.com/compute/v1/projects/{project}/global/images/{family}"

            def instances(self, _project: str) -> list[dict[str, str]]:
                return []

            def create(self, _env: dict[str, str]) -> str:
                self.created += 1
                return "vantio-gcp-lab-12"

            def wait_ssh(self, _project: str, _name: str) -> str:
                return "boot"

            def scp(self, _project: str, _name: str, _paths: list[Path]) -> None:
                raise AssertionError("copied")

            def ssh(self, _project: str, _name: str, command: str) -> subprocess.CompletedProcess[str]:
                self.commands.append(command)
                if command == "uname -r":
                    return subprocess.CompletedProcess([], 0, "6.12.11-amd64\n", "")
                raise AssertionError(command)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _loader(root / "loader")
            debs = root / "debs"
            debs.mkdir()
            (debs / "python3-cryptography_1_amd64.deb").write_bytes(b"deb")
            fake = Fake()
            env = _env(
                GCP_LAB_EXECUTE="1",
                GCP_LAB_GATE_JSON=GATE_JSON,
                PROOF_GUEST_KERNEL="6.8",
                LOADER_DIR=str(root / "loader"),
                DEB_DIR=str(debs),
                EVIDENCE_DIR=str(root / "evidence"),
                RUNNER_TEMP=str(root),
            )
            self.assertEqual(ep.run_proof(env, fake), 2)  # type: ignore[arg-type]
            body = json.loads((root / "evidence" / "enforcement-proof.json").read_text(encoding="utf-8"))
        self.assertEqual(fake.created, 1)
        self.assertEqual(fake.commands, ["uname -r"])
        self.assertEqual(body["stopped"], "guest_kernel")
        self.assertEqual(body["live_enforcement"], "NOT_PROVEN")

    def test_describe_from_family_rejects_a_foreign_link(self) -> None:
        transport = ep.GcloudTransport()
        bad = subprocess.CompletedProcess([], 0, "https://example.invalid/projects/other/global/images/x\n", "")
        with mock.patch("enforcement_proof.subprocess.run", return_value=bad) as run:
            with self.assertRaises(SystemExit) as caught:
                transport.image("ubuntu-os-cloud", "ubuntu-2604-lts-amd64")
        self.assertEqual(caught.exception.code, "image")
        argv = run.call_args.args[0]
        self.assertEqual(argv[3], "describe-from-family")
        self.assertIn("ubuntu-2604-lts-amd64", argv)
        self.assertIn("--project=ubuntu-os-cloud", argv)

    def test_a_workload_identity_file_is_not_a_static_key(self) -> None:
        self.assertEqual(ep.precheck(_env(GOOGLE_APPLICATION_CREDENTIALS="/tmp/key.json")), 1)
        self.assertEqual(
            ep.precheck(
                _env(
                    GCP_SA_KEY="present",
                    GOOGLE_APPLICATION_CREDENTIALS="/tmp/gha.json",
                    GOOGLE_GHA_CREDS_PATH="/tmp/gha.json",
                )
            ),
            1,
        )
        self.assertEqual(
            ep.precheck(
                _env(
                    GOOGLE_APPLICATION_CREDENTIALS="/tmp/gha.json",
                    GOOGLE_GHA_CREDS_PATH="/tmp/gha.json",
                )
            ),
            0,
        )

    def test_workflow_keeps_the_ancestor_guard_and_forwards_the_kernel(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        gate = GATE.read_text(encoding="utf-8")
        self.assertIn("merge-base --is-ancestor", text)
        self.assertNotIn("google-github-actions/auth@", text)
        self.assertIn('default: "6.8"', text)
        self.assertIn("- \"7.0\"", text)
        self.assertIn("- \"6.12\"", text)
        self.assertIn("guest_kernel: ${{ inputs.guest_kernel }}", text)
        self.assertIn("PROOF_GUEST_KERNEL: ${{ inputs.guest_kernel }}", text)
        self.assertIn("PROOF_GUEST_KERNEL: ${{ inputs.guest_kernel }}", gate)
        self.assertIn("google-github-actions/auth@", gate)
        self.assertIn("inputs.proof_slice == '' || inputs.proof_slice == null", gate)
        self.assertIn("pe-git-sha-allowlist.txt", text)
        allow = ALLOWLIST.read_text(encoding="utf-8")
        self.assertIn("864289cb2c9c4135d74233c74c6655087de3f20d", allow)
        self.assertIn("b3567a2aa3d705e8214e1cc671d30c31b9ac1c98", allow)
        self.assertIn("4bfb4fdcd52b85137d54dd5e45a46d71a2361b59", allow)
        self.assertNotIn("ubuntu-2604", allow)
        self.assertNotIn("debian-13", allow)


if __name__ == "__main__":
    unittest.main()
