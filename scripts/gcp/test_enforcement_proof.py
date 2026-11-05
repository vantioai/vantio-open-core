#!/usr/bin/env python3
"""Offline guards for the enforcement-proof workflow. No network and no cloud."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

import enforcement_proof as ep
import lab_auto

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "gcp-lab-enforcement-proof.yml"
PROVISION = ROOT / ".github" / "workflows" / "gcp-lab-provision.yml"
BUILD = ROOT / "scripts" / "gcp" / "build_pe_loader.sh"
PIN = ep.PE_GIT_SHA
GO = "zach-run-go-placeholder"
HOST = "proof81"
GATE = json.dumps({"expected_oop_usd": "0", "abort": False})


def _base_env(**extra: str) -> dict[str, str]:
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


def _flip(text: str) -> str:
    last = "0" if text[-1] != "0" else "1"
    return text[:-1] + last


class PinAndOrderTests(unittest.TestCase):
    def test_only_the_pinned_tip_passes(self) -> None:
        self.assertTrue(ep.sha_ok(PIN))
        self.assertEqual(len(PIN), 40)
        self.assertFalse(ep.sha_ok("ab" * 32))
        self.assertFalse(ep.sha_ok(PIN.upper()))
        self.assertFalse(ep.sha_ok(""))

    def test_one_flipped_nibble_is_rejected(self) -> None:
        flipped = _flip(PIN)
        self.assertNotEqual(flipped, PIN)
        self.assertEqual(len(flipped), 40)
        self.assertFalse(ep.sha_ok(flipped))
        env = _base_env(PE_GIT_SHA=flipped)
        self.assertEqual(ep.precheck(env), 1)

    def test_bad_sha_is_not_printed(self) -> None:
        flipped = _flip(PIN)
        env = _base_env(PE_GIT_SHA=flipped)
        done = subprocess.run(
            ["python3", str(ROOT / "scripts/gcp/enforcement_proof.py"), "precheck"],
            capture_output=True,
            text=True,
            env={**os.environ, **env, "PATH": os.environ.get("PATH", "")},
            check=False,
        )
        self.assertEqual(done.returncode, 1)
        self.assertNotIn(flipped, done.stdout + done.stderr)
        self.assertNotIn(GO, done.stdout + done.stderr)
        self.assertIn("pe_git_sha", done.stderr)

    def test_packet_order_without_a_second_compare_is_refused(self) -> None:
        packet = ("compare", "file-deny", "reboot-pre", "reboot", "reboot-post", "expired-key", "uninstall")
        self.assertFalse(ep.phase_order_allowed(packet))
        moved = list(ep.phases_for("full"))
        self.assertEqual(moved.count("compare"), 2)
        expired = moved.index("expired-key")
        reboot = moved.index("reboot")
        self.assertLess(reboot, expired)
        self.assertLess(moved.index("reboot-post"), expired)
        self.assertLess(moved.index("compare", reboot), expired)
        self.assertTrue(ep.phase_order_allowed(moved))
        swapped = list(moved)
        swapped[expired], swapped[reboot] = swapped[reboot], swapped[expired]
        self.assertFalse(ep.phase_order_allowed(swapped))

    def test_public_plan_and_ssh_omit_the_run_go(self) -> None:
        plan = json.dumps(ep.public_plan("full"))
        self.assertNotIn(GO, plan)
        self.assertNotIn(HOST, plan)
        self.assertIn(ep.LAB_DIR, plan)
        self.assertEqual(json.loads(plan)["phases"].count("compare"), 2)
        self.assertIn("expired-key", plan)
        command = ep.ssh_phase_command("compare")
        self.assertNotIn(GO, command)
        self.assertNotIn("GOOGLE_APPLICATION_CREDENTIALS=", command)
        self.assertIn("--i-understand-this-attaches-ebpf", ep.wrapper_script())
        text = ep.env_file_text(_base_env(PROOF_UNINSTALL_APPROVAL="approval-value-not-printed"))
        self.assertIn(GO, text)
        self.assertIn("VANTIO_LAB_DIR=/var/lib/vantio-enforcement-proof", text)
        self.assertNotIn(GO, ep.redact(text, _base_env()))
        self.assertNotIn("approval-value-not-printed", ep.redact(text, _base_env(PROOF_UNINSTALL_APPROVAL="approval-value-not-printed")))


class ObservationTests(unittest.TestCase):
    def test_pass_token_is_kept_and_a_changed_token_is_dropped(self) -> None:
        self.assertEqual(ep.keep_line("compare=PASS"), "compare=PASS")
        self.assertIsNone(ep.keep_line("compare=pass"))
        self.assertIsNone(ep.keep_line("compare=PROVEN"))
        self.assertIsNone(ep.keep_line(f"note={GO}"))
        self.assertTrue(ep.phase_accepted("compare", ["compare=PASS"], 0))
        self.assertFalse(ep.phase_accepted("compare", ["compare=REFUSED_LSM"], 0))
        self.assertTrue(
            ep.phase_accepted("uninstall", ["uninstall=REFUSED_NOT_ENROLLED"], 2)
        )
        self.assertTrue(ep.phase_accepted("expired-key", ["license_exp_claim=NOT_PROVEN"], 0))
        self.assertFalse(
            ep.phase_accepted(
                "expired-key",
                ["license_exp_claim=NOT_PROVEN", "expired_key=FAIL_private_key_remains"],
                0,
            )
        )
        with self.assertRaises(SystemExit):
            ep.allow_evidence({"live_enforcement": "PROVEN", "reboot_restored": "NOT_RUN"})

    def test_loader_lib_line_mutation_fails(self) -> None:
        good = "\tlibc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x1)\n"
        self.assertTrue(ep.loader_libs_ok(good))
        self.assertFalse(ep.loader_libs_ok(good + "\tlibssl.so.3 => /usr/lib/libssl.so.3\n"))


class RunTests(unittest.TestCase):
    def _loader(self, directory: Path) -> None:
        directory.mkdir()
        binary = directory / "vantio-loader"
        binary.write_bytes(b"\x7fELFnot-a-real-loader")
        script = directory / "enforcement_proof_lab.sh"
        script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
        (directory / "loader.sha256").write_text(hashlib.sha256(binary.read_bytes()).hexdigest() + "\n", encoding="utf-8")
        (directory / "script.sha256").write_text(hashlib.sha256(script.read_bytes()).hexdigest() + "\n", encoding="utf-8")
        (directory / "ldd.txt").write_text("\tlibc.so.6 => /lib/libc.so.6\n", encoding="utf-8")

    def test_refuses_without_execute_and_does_not_create(self) -> None:
        class Boom:
            def create(self, _env: dict[str, str]) -> str:
                raise AssertionError("created")

        self.assertEqual(ep.run_proof({"GCP_LAB_EXECUTE": ""}, Boom()), 2)  # type: ignore[arg-type]

    def test_full_slice_reboots_between_the_script_phases(self) -> None:
        class Fake:
            def __init__(self) -> None:
                self.commands: list[str] = []
                self.files: list[str] = []
                self.created = 0
                self.boot = "boot-before"

            def instances(self, _project: str) -> list[dict[str, str]]:
                return []

            def create(self, _env: dict[str, str]) -> str:
                self.created += 1
                return "vantio-gcp-lab-12"

            def scp(self, _project: str, _name: str, paths: list[Path]) -> None:
                self.files.extend(path.name for path in paths)

            def wait_ssh(self, _project: str, _name: str) -> str:
                return self.boot

            def boot_id(self, _project: str, _name: str) -> str:
                return self.boot

            def wait_boot(self, _project: str, _name: str, before: str) -> str:
                return "boot-after" if before == "boot-before" else ""

            def ssh(self, _project: str, _name: str, command: str) -> subprocess.CompletedProcess[str]:
                self.commands.append(command)
                if command.startswith("sudo bash ") and "run-proof-phase.sh" in command:
                    phase = command.rsplit(" ", 1)[-1].strip("'")
                    lines = {
                        "compare": "compare=PASS\nlive_enforcement=NOT_PROVEN\n",
                        "file-deny": "file_deny=PASS\n",
                        "reboot-pre": "reboot_pre=RECORDED\n",
                        "reboot-post": "reboot_wiped=PASS\nreboot_restored=NOT_RUN\n",
                        "expired-key": "license_exp_claim=NOT_PROVEN\nlicense_exp_observation=NOT_CONSULTED\n",
                        "uninstall": "uninstall=REFUSED_NOT_ENROLLED\n",
                    }
                    rc = 2 if phase == "uninstall" else 0
                    return subprocess.CompletedProcess([], rc, lines[phase], "")
                if "systemctl reboot --force" in command:
                    self.boot = "boot-after"
                    return subprocess.CompletedProcess([], 0, "", "")
                return subprocess.CompletedProcess([], 1 if command.startswith("sudo cat") else 0, "", "")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._loader(root / "loader")
            debs = root / "debs"
            debs.mkdir()
            (debs / "python3-cryptography_1_amd64.deb").write_bytes(b"deb")
            fake = Fake()
            env = _base_env(
                GCP_LAB_EXECUTE="1",
                GCP_LAB_GATE_JSON=GATE,
                LOADER_DIR=str(root / "loader"),
                DEB_DIR=str(debs),
                EVIDENCE_DIR=str(root / "evidence"),
                RUNNER_TEMP=str(root),
            )
            self.assertEqual(ep.run_proof(env, fake), 0)  # type: ignore[arg-type]
            body = json.loads((root / "evidence" / "enforcement-proof.json").read_text(encoding="utf-8"))
        self.assertEqual(fake.created, 1)
        joined = "\n".join(fake.commands)
        self.assertNotIn(GO, joined)
        self.assertIn("systemctl reboot --force", joined)
        self.assertIn("google-shutdown-scripts", joined)
        self.assertNotIn("sudo reboot", joined)
        reboot_at = next(i for i, command in enumerate(fake.commands) if "systemctl reboot --force" in command)
        pre = next(i for i, command in enumerate(fake.commands) if command.endswith(" reboot-pre"))
        post = next(i for i, command in enumerate(fake.commands) if command.endswith(" reboot-post"))
        expired = next(i for i, command in enumerate(fake.commands) if command.endswith(" expired-key"))
        self.assertLess(pre, reboot_at)
        self.assertLess(reboot_at, post)
        self.assertLess(post, expired)
        self.assertIn("proof.env", fake.files)
        self.assertEqual(body["live_enforcement"], "NOT_PROVEN")
        self.assertEqual(body["result"], "OBSERVED")
        self.assertNotIn(GO, json.dumps(body))
        self.assertIn("compare=PASS", body["observations"])

    def test_refused_lsm_stops_before_reboot(self) -> None:
        class Fake:
            def __init__(self) -> None:
                self.commands: list[str] = []

            def instances(self, _project: str) -> list[dict[str, str]]:
                return []

            def create(self, _env: dict[str, str]) -> str:
                return "vantio-gcp-lab-12"

            def scp(self, _project: str, _name: str, _paths: list[Path]) -> None:
                return None

            def wait_ssh(self, _project: str, _name: str) -> str:
                return "boot"

            def ssh(self, _project: str, _name: str, command: str) -> subprocess.CompletedProcess[str]:
                self.commands.append(command)
                if command.endswith("compare"):
                    return subprocess.CompletedProcess([], 0, "compare=REFUSED_LSM\n", "")
                return subprocess.CompletedProcess([], 0, "", "")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._loader(root / "loader")
            debs = root / "debs"
            debs.mkdir()
            (debs / "python3-cryptography_1_amd64.deb").write_bytes(b"deb")
            fake = Fake()
            env = _base_env(
                GCP_LAB_EXECUTE="1",
                GCP_LAB_GATE_JSON=GATE,
                LOADER_DIR=str(root / "loader"),
                DEB_DIR=str(debs),
                EVIDENCE_DIR=str(root / "evidence"),
                RUNNER_TEMP=str(root),
            )
            self.assertEqual(ep.run_proof(env, fake), 2)  # type: ignore[arg-type]
        self.assertFalse(any("reboot --force" in command for command in fake.commands))


class CreateAndBuildTests(unittest.TestCase):
    def test_create_argv_is_the_ubuntu_micro_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "startup.sh"
            script.write_text("#!/bin/bash\n", encoding="utf-8")
            argv = ep.instance_create_argv(_base_env(), str(script))
        joined = " ".join(argv)
        self.assertIn("--machine-type=e2-micro", joined)
        self.assertIn("--image-family=ubuntu-2404-lts-amd64", joined)
        self.assertIn("--no-address", joined)
        self.assertIn("--no-service-account", joined)
        self.assertIn("--hostname=proof81.vantio-lab-oct08.internal", joined)
        self.assertNotIn("e2-standard", joined)
        self.assertNotIn(GO, joined)
        with self.assertRaises(SystemExit):
            ep.instance_create_argv(_base_env(GCP_LAB_PROJECT="other-project"), str(script))

    def test_wrong_pin_does_not_start_docker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bindir = root / "bin"
            bindir.mkdir()
            log = root / "docker.log"
            docker = bindir / "docker"
            docker.write_text(
                "#!/bin/sh\necho called >> \"$DOCKER_LOG\"\nexit 99\n",
                encoding="utf-8",
            )
            docker.chmod(0o755)
            env = {
                "PATH": f"{bindir}:{os.environ.get('PATH', '')}",
                "DOCKER_LOG": str(log),
                "HOME": str(root),
            }
            done = subprocess.run(
                ["bash", str(BUILD), str(root / "src"), str(root / "out"), "0" * 40],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(done.returncode, 1)
            self.assertIn("pe_git_sha", done.stderr)
            self.assertFalse(log.exists())
            text = BUILD.read_text(encoding="utf-8")
            self.assertIn(f"expected={PIN}", text)
            mutated = text.replace(
                'if [[ "$pin" != "$expected" ]]; then\n  echo "pe_git_sha" >&2\n  exit 1\nfi\n',
                "",
                1,
            )
            self.assertNotEqual(mutated, text)
            mutated_path = root / "mutated.sh"
            mutated_path.write_text(mutated, encoding="utf-8")
            broken = subprocess.run(
                ["bash", str(mutated_path), str(root / "src"), str(root / "out"), "0" * 40],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertNotIn("pe_git_sha", broken.stderr)
            self.assertNotEqual(broken.returncode, 0)
            self.assertFalse(log.exists())

    def test_script_pin_byte_must_match_the_constant(self) -> None:
        text = BUILD.read_text(encoding="utf-8")
        self.assertIn(f"expected={PIN}", text)
        mutated = text.replace(PIN, _flip(PIN), 1)
        self.assertNotIn(f"expected={PIN}", mutated)


class WorkflowTests(unittest.TestCase):
    def test_provision_is_not_the_proof_path(self) -> None:
        provision = PROVISION.read_text(encoding="utf-8")
        self.assertNotIn("enforcement_proof_lab.sh", provision)
        self.assertNotIn("enforcement_proof.py", provision)
        self.assertNotIn("PROOF_RUN_GO", provision)

    def test_dispatch_shape_reuses_the_gate_and_hides_the_go(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        doc = yaml.safe_load(text)
        trigger = doc[True]
        self.assertEqual(list(trigger), ["workflow_dispatch"])
        inputs = trigger["workflow_dispatch"]["inputs"]
        self.assertEqual(inputs["pe_git_sha"]["default"], PIN)
        self.assertNotIn("seal", inputs)
        self.assertNotIn("t2112u", inputs)
        self.assertEqual(inputs["proof_slice"]["default"], "full")
        self.assertIn(ep.LAB_DIR, text)
        self.assertIn("gcp-lab-cost-gate.yml@main # oidc-trust", text)
        self.assertIn("needs.gate.outputs.expected_oop_usd == '0'", doc["jobs"]["prove"]["if"])
        self.assertIn("needs.gate.outputs.expected_oop_usd == '0'", doc["jobs"]["build"]["if"])
        self.assertIn("gcp-lab-teardown.yml", text)
        self.assertIn("gcp-lab-verify-removed.yml", text)
        self.assertNotIn("gh workflow", text)
        self.assertNotIn("production-signing-key", text)
        self.assertNotIn(GO, text)
        mutated = text.replace("expected_oop_usd == '0'", "expected_oop_usd == '1'")
        mutated_doc = yaml.safe_load(mutated)
        self.assertNotIn("expected_oop_usd == '0'", mutated_doc["jobs"]["prove"]["if"])
        self.assertIn(ep.WORKFLOW_FILE, ep.WORKFLOW_REF)
        self.assertIn(ep.WORKFLOW_FILE, lab_auto.WORKFLOWS)


if __name__ == "__main__":
    unittest.main()
