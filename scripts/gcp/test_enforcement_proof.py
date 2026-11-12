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
from unittest import mock

import yaml

import enforcement_proof as ep
import lab_auto

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "gcp-lab-enforcement-proof.yml"
PROVISION = ROOT / ".github" / "workflows" / "gcp-lab-provision.yml"
BUILD = ROOT / "scripts" / "gcp" / "build_pe_loader.sh"
PIN = ep.PE_GIT_SHA
MAIN_TIP = "b3567a2aa3d705e8214e1cc671d30c31b9ac1c98"
DRAFT_TIP = "2d7b92949348478705545a9af660e2dbec3b94af"
TIPS = (PIN, MAIN_TIP)
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


def _cli(command: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(ROOT / "scripts/gcp/enforcement_proof.py"), command],
        capture_output=True,
        text=True,
        env={**os.environ, **env, "PATH": os.environ.get("PATH", "")},
        check=False,
    )


def _cargo_workdir_is_checkout(workdir: str, volume: str, checkout: Path) -> bool:
    """True when cargo's workdir is the absolute checkout, not a bare /src mount."""
    root = str(checkout.resolve())
    if not workdir.startswith("/") or workdir in {"/src", "/src/"}:
        return False
    if workdir != root:
        return False
    return volume == f"{root}:{root}:ro"


def _writable_target_outside_checkout(volumes: list[str], checkout: Path) -> bool:
    """True when eBPF's target dir is a writable bind outside the read-only checkout."""
    root = str(checkout.resolve())
    wanted = f"{root}/target"
    found = False
    for volume in volumes:
        host, sep, dest = volume.partition(":")
        if sep != ":" or dest != wanted:
            continue
        if not host.startswith("/"):
            return False
        if host == root or host.startswith(root + os.sep) or root.startswith(host + os.sep):
            return False
        found = True
    return found


class PinAndOrderTests(unittest.TestCase):
    def test_allowlisted_tips_pass_and_other_hex_fails(self) -> None:
        tips = ep.read_allowlist()
        self.assertEqual(tips, {PIN: False, MAIN_TIP: False})
        self.assertEqual(ep.ALLOWLIST_FILE.name, "pe-git-sha-allowlist.txt")
        for tip in TIPS:
            self.assertEqual(len(tip), 40)
            self.assertTrue(ep.sha_ok(tip))
            self.assertEqual(ep.precheck(_base_env(PE_GIT_SHA=tip)), 0)
            recorded = _cli("sha", {"PE_GIT_SHA": tip})
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            self.assertIn(f"sha={tip}", recorded.stdout)
            self.assertNotIn(GO, recorded.stdout + recorded.stderr)
        other = "ab" * 20
        self.assertEqual(len(other), 40)
        self.assertFalse(ep.sha_ok(other))
        self.assertFalse(ep.sha_ok("ab" * 32))
        self.assertFalse(ep.sha_ok(PIN.upper()))
        self.assertFalse(ep.sha_ok(PIN[:-1]))
        self.assertFalse(ep.sha_ok(PIN + "\n"))
        self.assertFalse(ep.sha_ok(""))
        self.assertEqual(ep.precheck(_base_env(PE_GIT_SHA=other)), 1)
        hidden = _cli("precheck", _base_env(PE_GIT_SHA=other))
        self.assertEqual(hidden.returncode, 1)
        self.assertNotIn(other, hidden.stdout + hidden.stderr)
        self.assertIn("pe_git_sha", hidden.stderr)

    def test_one_flipped_nibble_is_rejected(self) -> None:
        flipped = _flip(PIN)
        self.assertNotEqual(flipped, PIN)
        self.assertEqual(len(flipped), 40)
        self.assertFalse(ep.sha_ok(flipped))
        env = _base_env(PE_GIT_SHA=flipped)
        self.assertEqual(ep.precheck(env), 1)

    def test_one_flipped_allowlist_byte_rejects_the_tip(self) -> None:
        text = ep.ALLOWLIST_FILE.read_text(encoding="utf-8")
        flipped = _flip(PIN)
        mutated = text.replace(PIN, flipped, 1)
        self.assertNotEqual(mutated, text)
        allowed = ep.parse_allowlist(mutated)
        self.assertNotIn(PIN, allowed)
        self.assertFalse(ep.sha_ok(PIN, allowlist=allowed))
        self.assertFalse(ep.sha_ok(flipped))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pe-git-sha-allowlist.txt"
            path.write_text(PIN + "\n" + ("g" * 40) + "\n", encoding="utf-8")
            with self.assertRaises(SystemExit) as caught:
                ep.read_allowlist(path)
            self.assertEqual(caught.exception.code, "pe_git_sha_allowlist")
            self.assertFalse(ep.sha_ok(PIN, path=path))
            with mock.patch.object(ep, "ALLOWLIST_FILE", path):
                self.assertEqual(ep.precheck(_base_env()), 1)
                self.assertEqual(ep.check_sha({"PE_GIT_SHA": PIN}), 1)
        duplicate = PIN + "\n" + PIN + "\n"
        with self.assertRaises(SystemExit) as caught:
            ep.parse_allowlist(duplicate)
        self.assertEqual(caught.exception.code, "pe_git_sha_allowlist")

    def test_comment_blank_padding_and_injection_are_refused(self) -> None:
        commented = "# " + PIN + "\n\n" + MAIN_TIP + "\n"
        entries = ep.parse_allowlist(commented)
        self.assertEqual(entries, {MAIN_TIP: False})
        self.assertNotIn(PIN, entries)
        self.assertFalse(ep.sha_ok(PIN, allowlist=entries))
        padded_lines = (f" {PIN}", f"{PIN} ", f"\t{PIN}", f"{PIN}\t", f"{PIN}  cleared", f" {PIN} cleared")
        for bad in padded_lines:
            with self.assertRaises(SystemExit) as caught:
                ep.parse_allowlist(bad + "\n" + MAIN_TIP + "\n")
            self.assertEqual(caught.exception.code, "pe_git_sha_allowlist")
            self.assertFalse(ep.sha_ok(bad))
        payloads = ("$(touch /tmp/pe-inject)", PIN + ";touch /tmp/pe-inject", "`id`", PIN + "\n" + MAIN_TIP)
        for payload in payloads:
            self.assertFalse(ep.sha_ok(payload))
            hidden = _cli("precheck", _base_env(PE_GIT_SHA=payload))
            self.assertEqual(hidden.returncode, 1)
            self.assertNotIn(payload, hidden.stdout + hidden.stderr)
            self.assertIn("pe_git_sha", hidden.stderr)
        self.assertTrue(ep.tip_may_build(MAIN_TIP, "yes", {MAIN_TIP: False}))
        self.assertFalse(ep.tip_may_build(MAIN_TIP, "no", {MAIN_TIP: False}))
        self.assertFalse(ep.tip_may_build(PIN, "no", {PIN: True}))
        with self.assertRaises(SystemExit) as caught:
            ep.parse_allowlist(PIN + " cleared\n")
        self.assertEqual(caught.exception.code, "pe_git_sha_allowlist")
        self.assertFalse(ep.tip_may_build(DRAFT_TIP, "yes", {PIN: False, MAIN_TIP: False}))

    def test_plan_records_the_dispatched_tip(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            ep.public_plan("full", DRAFT_TIP)
        self.assertEqual(caught.exception.code, "pe_git_sha")
        with self.assertRaises(SystemExit) as caught:
            ep.public_plan("full", _flip(DRAFT_TIP))
        self.assertEqual(caught.exception.code, "pe_git_sha")
        done = _cli("plan", _base_env(PE_GIT_SHA=MAIN_TIP))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["pe_git_sha"], MAIN_TIP)
        self.assertNotIn(GO, done.stdout)
        refused = _cli("plan", _base_env(PE_GIT_SHA="ab" * 20))
        self.assertEqual(refused.returncode, 2)
        self.assertNotIn("ab" * 20, refused.stdout + refused.stderr)
        self.assertIn("pe_git_sha", refused.stderr)

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
        for tip in TIPS:
            kept = ep.allow_evidence(
                {"live_enforcement": "NOT_PROVEN", "pe_git_sha": tip, "reboot_restored": "NOT_RUN"}
            )
            self.assertEqual(kept["pe_git_sha"], tip)
        with self.assertRaises(SystemExit) as caught:
            ep.allow_evidence(
                {"live_enforcement": "NOT_PROVEN", "pe_git_sha": _flip(PIN), "reboot_restored": "NOT_RUN"}
            )
        self.assertEqual(caught.exception.code, "pe_git_sha")

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
        (directory / "build-sha").write_text(PIN + "\n", encoding="utf-8")

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
        self.assertIn(ep.BUILD_SHA_PATH, joined)
        self.assertIn(PIN, joined)
        self.assertEqual(body["live_enforcement"], "NOT_PROVEN")
        self.assertEqual(body["pe_git_sha"], PIN)
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
            body = json.loads((root / "evidence" / "enforcement-proof.json").read_text(encoding="utf-8"))
        self.assertEqual(body["pe_git_sha"], PIN)
        self.assertFalse(any("reboot --force" in command for command in fake.commands))

    def test_proof_json_records_the_build_head_not_a_different_input(self) -> None:
        class Boom:
            def create(self, _env: dict[str, str]) -> str:
                raise AssertionError("created")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._loader(root / "loader")
            (root / "loader" / "build-sha").write_text(MAIN_TIP + "\n", encoding="utf-8")
            env = _base_env(
                GCP_LAB_EXECUTE="1",
                LOADER_DIR=str(root / "loader"),
                EVIDENCE_DIR=str(root / "evidence"),
                RUNNER_TEMP=str(root),
            )
            self.assertEqual(ep.run_proof(env, Boom()), 2)  # type: ignore[arg-type]
            body = json.loads((root / "evidence" / "enforcement-proof.json").read_text(encoding="utf-8"))
        self.assertEqual(body["pe_git_sha"], MAIN_TIP)
        self.assertEqual(body["stopped"], "pe_build_sha")
        self.assertNotEqual(body["pe_git_sha"], PIN)

    def test_reboot_post_fails_when_the_instance_sha_differs(self) -> None:
        class Fake:
            def __init__(self) -> None:
                self.commands: list[str] = []
                self.copied = False

            def instances(self, _project: str) -> list[dict[str, object]]:
                return [
                    {
                        "name": "vantio-gcp-lab-12",
                        "status": "RUNNING",
                        "labels": {
                            "vantio-lab": "gcp",
                            "vantio-owner": "gha",
                            "vantio-expires-epoch": "1999999999",
                        },
                    }
                ]

            def wait_ssh(self, _project: str, _name: str) -> str:
                return "boot"

            def scp(self, _project: str, _name: str, _paths: list[Path]) -> None:
                self.copied = True

            def ssh(self, _project: str, _name: str, command: str) -> subprocess.CompletedProcess[str]:
                self.commands.append(command)
                if command.startswith("sudo cat ") and "build-sha" in command:
                    return subprocess.CompletedProcess([], 0, MAIN_TIP + "\n", "")
                return subprocess.CompletedProcess([], 0, "", "")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = Fake()
            env = _base_env(
                GCP_LAB_EXECUTE="1",
                GCP_LAB_GATE_JSON=GATE,
                PROOF_SLICE="reboot-post",
                INSTANCE_NAME="vantio-gcp-lab-12",
                EVIDENCE_DIR=str(root / "evidence"),
                RUNNER_TEMP=str(root),
            )
            self.assertEqual(ep.run_proof(env, fake), 2)  # type: ignore[arg-type]
            body = json.loads((root / "evidence" / "enforcement-proof.json").read_text(encoding="utf-8"))
        self.assertEqual(body["pe_git_sha"], MAIN_TIP)
        self.assertEqual(body["stopped"], "pe_build_sha")
        self.assertFalse(fake.copied)
        self.assertFalse(any(command.endswith(" compare") for command in fake.commands))


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
            self.assertNotIn("0" * 40, done.stdout + done.stderr)
            self.assertFalse(log.exists())
            text = BUILD.read_text(encoding="utf-8")
            self.assertIn("pe-git-sha-allowlist.txt", text)
            self.assertNotIn(PIN, text)
            start = text.index('if [[ ! "$pin" =~ ^[0-9a-f]{40}$ ]]')
            end = text.index("src=$(cd", start)
            mutated = text[:start] + text[end:]
            self.assertNotEqual(mutated, text)
            self.assertNotIn("pe_git_sha", mutated)
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

    def test_allowlist_byte_mutation_does_not_start_docker(self) -> None:
        text = ep.ALLOWLIST_FILE.read_text(encoding="utf-8")
        flipped = _flip(PIN)
        mutated_allow = text.replace(PIN, flipped, 1)
        self.assertNotEqual(mutated_allow, text)
        self.assertFalse(ep.sha_ok(PIN, allowlist=ep.parse_allowlist(mutated_allow)))
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
            script = root / "build_pe_loader.sh"
            script.write_text(BUILD.read_text(encoding="utf-8"), encoding="utf-8")
            (root / "pe-git-sha-allowlist.txt").write_text(mutated_allow, encoding="utf-8")
            env = {
                "PATH": f"{bindir}:{os.environ.get('PATH', '')}",
                "DOCKER_LOG": str(log),
                "HOME": str(root),
            }
            done = subprocess.run(
                ["bash", str(script), str(root / "src"), str(root / "out"), PIN],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(done.returncode, 1)
            self.assertIn("pe_git_sha", done.stderr)
            self.assertNotIn(PIN, done.stdout + done.stderr)
            self.assertNotIn(flipped, done.stdout + done.stderr)
            self.assertFalse(log.exists())
            (root / "pe-git-sha-allowlist.txt").write_text(PIN + "\n" + ("g" * 40) + "\n", encoding="utf-8")
            invalid = subprocess.run(
                ["bash", str(script), str(root / "src"), str(root / "out"), PIN],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(invalid.returncode, 1)
            self.assertIn("pe_git_sha", invalid.stderr)
            self.assertFalse(log.exists())

    def _fake_tools(self, root: Path, pin: str) -> dict[str, str]:
        bindir = root / "bin"
        bindir.mkdir()
        git = bindir / "git"
        git.write_text(
            "#!/bin/sh\n"
            "while [ $# -gt 0 ]; do\n"
            "  case \"$1\" in\n"
            "    -C) shift 2; continue ;;\n"
            "  esac\n"
            "  break\n"
            "done\n"
            "case \"$1\" in\n"
            "  rev-parse) printf '%s\\n' \"$PE_HEAD\" ;;\n"
            "  status) ;;\n"
            "  merge-base)\n"
            "    if [ \"${PE_ANCESTOR:-1}\" = \"0\" ]; then exit 1; fi\n"
            "    exit 0\n"
            "    ;;\n"
            "  *) printf 'git_unexpected\\n' >&2; exit 1 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        git.chmod(0o755)
        docker = bindir / "docker"
        docker.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$@\" > \"$DOCKER_LOG\"\n"
            "out_host=\n"
            "for arg in \"$@\"; do\n"
            "  case \"$arg\" in\n"
            "    *:/out) out_host=${arg%:/out} ;;\n"
            "  esac\n"
            "done\n"
            "if [ -n \"$out_host\" ]; then\n"
            "  mkdir -p \"$out_host\"\n"
            "  printf '\\177ELF' > \"$out_host/vantio-loader\"\n"
            "  printf 'libc.so.6\\n' > \"$out_host/ldd.txt\"\n"
            "fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        docker.chmod(0o755)
        return {
            "PATH": f"{bindir}:{os.environ.get('PATH', '')}",
            "DOCKER_LOG": str(root / "docker.log"),
            "PE_HEAD": pin,
            "HOME": str(root),
        }

    def _checkout(self, path: Path, *, manifest: bool = True) -> None:
        (path / "vantio-loader" / "src").mkdir(parents=True)
        (path / "scripts").mkdir()
        if manifest:
            (path / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")
        (path / "rust-toolchain.toml").write_text("[toolchain]\n", encoding="utf-8")
        (path / "vantio-loader" / "src" / "main.rs").write_text("fn main() {}\n", encoding="utf-8")
        (path / "scripts" / "enforcement_proof_lab.sh").write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")

    def test_relative_checkout_is_the_cargo_workdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "phantom-engine"
            self._checkout(checkout)
            env = self._fake_tools(root, PIN)
            done = subprocess.run(
                ["bash", str(BUILD), "phantom-engine", "out", PIN],
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
                check=False,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("loader_built=1", done.stdout)
            args = (root / "docker.log").read_text(encoding="utf-8").splitlines()
            workdir = args[args.index("-w") + 1]
            volumes = [args[i + 1] for i, arg in enumerate(args) if arg == "-v"]
            self.assertTrue(_cargo_workdir_is_checkout(workdir, f"{workdir}:{workdir}:ro", checkout))
            self.assertIn(f"{workdir}:{workdir}:ro", volumes)
            self.assertNotIn("/src", workdir)
            self.assertTrue((Path(workdir) / "Cargo.toml").is_file())
            flipped = workdir[:-1] + ("x" if workdir[-1] != "x" else "y")
            self.assertNotEqual(flipped, workdir)
            self.assertFalse(_cargo_workdir_is_checkout(flipped, f"{flipped}:{flipped}:ro", checkout))
            self.assertFalse(_cargo_workdir_is_checkout("/src", "phantom-engine:/src:ro", checkout))
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('build_pe_loader.sh "${GITHUB_WORKSPACE}/phantom-engine"', workflow)
        self.assertNotIn("build_pe_loader.sh phantom-engine ", workflow)
        self.assertIn('"$PE_GIT_SHA"', workflow)
        self.assertNotIn(f"pe-loader\" {PIN}", workflow)

    def test_checked_out_head_must_be_the_dispatched_tip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "phantom-engine").mkdir()
            env = self._fake_tools(root, DRAFT_TIP)
            done = subprocess.run(
                ["bash", str(BUILD), "phantom-engine", "out", PIN],
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
                check=False,
            )
            self.assertEqual(done.returncode, 1)
            self.assertIn("pe_head", done.stderr)
            self.assertFalse((root / "docker.log").exists())

    def test_draft_tip_is_not_rejected_before_docker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._checkout(root / "phantom-engine")
            side = root / "pwned"
            env = self._fake_tools(root, DRAFT_TIP)
            done = subprocess.run(
                ["bash", str(BUILD), "phantom-engine", "out", DRAFT_TIP],
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
                check=False,
            )
            self.assertEqual(done.returncode, 1)
            self.assertIn("pe_git_sha", done.stderr)
            self.assertNotIn(DRAFT_TIP, done.stdout + done.stderr)
            self.assertFalse((root / "docker.log").exists())
            self.assertFalse(side.exists())

    def test_non_ancestor_and_a_cleared_suffix_are_refused_before_docker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._checkout(root / "phantom-engine")
            env = self._fake_tools(root, PIN)
            env["PE_ANCESTOR"] = "0"
            refused = subprocess.run(
                ["bash", str(BUILD), "phantom-engine", "out", PIN],
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
                check=False,
            )
            self.assertEqual(refused.returncode, 1)
            self.assertIn("pe_ancestor", refused.stderr)
            self.assertFalse((root / "docker.log").exists())
            script = root / "build_pe_loader.sh"
            script.write_text(BUILD.read_text(encoding="utf-8"), encoding="utf-8")
            (root / "pe-git-sha-allowlist.txt").write_text(
                "# comment " + PIN + "\n\n" + PIN + " cleared\n",
                encoding="utf-8",
            )
            cleared = subprocess.run(
                ["bash", str(script), "phantom-engine", "out", PIN],
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
                check=False,
            )
            self.assertEqual(cleared.returncode, 1)
            self.assertIn("pe_git_sha", cleared.stderr)
            self.assertFalse((root / "docker.log").exists())

    def test_allowlist_and_input_injection_does_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            side = root / "pwned"
            payload = f"$(touch {side})"
            script = root / "build_pe_loader.sh"
            script.write_text(BUILD.read_text(encoding="utf-8"), encoding="utf-8")
            (root / "pe-git-sha-allowlist.txt").write_text(PIN + "\n" + payload + "\n", encoding="utf-8")
            env = self._fake_tools(root, PIN)
            injected = subprocess.run(
                ["bash", str(script), "phantom-engine", "out", PIN],
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
                check=False,
            )
            self.assertEqual(injected.returncode, 1)
            self.assertIn("pe_git_sha", injected.stderr)
            self.assertFalse(side.exists())
            self.assertFalse((root / "docker.log").exists())
            (root / "pe-git-sha-allowlist.txt").write_text("# \n\n" + PIN + "\n", encoding="utf-8")
            padded = subprocess.run(
                ["bash", str(script), "phantom-engine", "out", " " + PIN],
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
                check=False,
            )
            self.assertEqual(padded.returncode, 1)
            self.assertIn("pe_git_sha", padded.stderr)
            self.assertFalse(side.exists())
            self.assertFalse((root / "docker.log").exists())

    def test_missing_manifest_does_not_start_docker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._checkout(root / "phantom-engine", manifest=False)
            env = self._fake_tools(root, PIN)
            done = subprocess.run(
                ["bash", str(BUILD), "phantom-engine", "out", PIN],
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
                check=False,
            )
            self.assertNotEqual(done.returncode, 0)
            self.assertFalse((root / "docker.log").exists())

    def test_named_volume_mount_mutation_is_not_the_checkout(self) -> None:
        text = BUILD.read_text(encoding="utf-8")
        self.assertIn('-v "$src:$src:ro"', text)
        self.assertIn('-w "$src"', text)
        self.assertNotIn("cd /src", text)
        self.assertNotIn('"$root:/src', text)
        mutated = text.replace('"$src:$src:ro"', '"$root:/src:ro"', 1).replace('-w "$src"', "-w /src", 1)
        self.assertNotEqual(mutated, text)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "phantom-engine"
            self._checkout(checkout)
            script = root / "mutated.sh"
            script.write_text(mutated, encoding="utf-8")
            (root / "pe-git-sha-allowlist.txt").write_text(
                ep.ALLOWLIST_FILE.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            env = self._fake_tools(root, PIN)
            done = subprocess.run(
                ["bash", str(script), "phantom-engine", "out", PIN],
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
                check=False,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            args = (root / "docker.log").read_text(encoding="utf-8").splitlines()
            workdir = args[args.index("-w") + 1]
            volumes = [args[i + 1] for i, arg in enumerate(args) if arg == "-v"]
            self.assertEqual(workdir, "/src")
            self.assertIn("phantom-engine:/src:ro", volumes)
            self.assertFalse(_cargo_workdir_is_checkout(workdir, "phantom-engine:/src:ro", checkout))

    def test_ebpf_target_is_a_writable_bind_outside_the_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "phantom-engine"
            self._checkout(checkout)
            env = self._fake_tools(root, PIN)
            done = subprocess.run(
                ["bash", str(BUILD), "phantom-engine", "out", PIN],
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
                check=False,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            args = (root / "docker.log").read_text(encoding="utf-8").splitlines()
            workdir = args[args.index("-w") + 1]
            volumes = [args[i + 1] for i, arg in enumerate(args) if arg == "-v"]
            self.assertIn(f"{workdir}:{workdir}:ro", volumes)
            self.assertTrue(_writable_target_outside_checkout(volumes, checkout))
            self.assertTrue((checkout.resolve() / "target").is_dir())
            text = BUILD.read_text(encoding="utf-8")
            self.assertIn('-v "$writable:$src/target"', text)
            self.assertIn('rm -rf "$writable" >/dev/null 2>&1 || true', text)
            self.assertIn('chown -R "${HOST_UID}:${HOST_GID}" "$(pwd)/target" /out', text)
            mutated = text.replace('-v "$writable:$src/target"', '-v "$writable:$src/target:ro"', 1)
            self.assertNotEqual(mutated, text)
            script = root / "mutated.sh"
            script.write_text(mutated, encoding="utf-8")
            mutated_run = subprocess.run(
                ["bash", str(script), "phantom-engine", "out", PIN],
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
                check=False,
            )
            self.assertEqual(mutated_run.returncode, 0, mutated_run.stderr)
            mutated_args = (root / "docker.log").read_text(encoding="utf-8").splitlines()
            mutated_volumes = [mutated_args[i + 1] for i, arg in enumerate(mutated_args) if arg == "-v"]
            self.assertFalse(_writable_target_outside_checkout(mutated_volumes, checkout))

    def test_writable_target_inside_the_checkout_does_not_start_docker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "phantom-engine"
            self._checkout(checkout)
            env = self._fake_tools(root, PIN)
            mktemp = Path(env["PATH"].split(":", 1)[0]) / "mktemp"
            inside = checkout / "nested-target"
            mktemp.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$FAKE_MKTEMP\"\n",
                encoding="utf-8",
            )
            mktemp.chmod(0o755)
            done = subprocess.run(
                ["bash", str(BUILD), "phantom-engine", "out", PIN],
                capture_output=True,
                text=True,
                cwd=root,
                env={**env, "FAKE_MKTEMP": str(inside)},
                check=False,
            )
            self.assertEqual(done.returncode, 1)
            self.assertIn("pe_target", done.stderr)
            self.assertFalse((root / "docker.log").exists())
            text = BUILD.read_text(encoding="utf-8")
            needle = '  "$src"|"$src"/*) echo "pe_target" >&2; exit 1 ;;\n'
            self.assertIn(needle, text)
            mutated = text.replace(needle, "", 1)
            self.assertNotEqual(mutated, text)
            script = root / "mutated.sh"
            script.write_text(mutated, encoding="utf-8")
            (root / "docker.log").unlink(missing_ok=True)
            broken = subprocess.run(
                ["bash", str(script), "phantom-engine", "out", PIN],
                capture_output=True,
                text=True,
                cwd=root,
                env={**env, "FAKE_MKTEMP": str(inside)},
                check=False,
            )
            self.assertNotIn("pe_target", broken.stderr)
            self.assertTrue((root / "docker.log").exists())

    def test_failed_target_cleanup_does_not_fail_the_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "phantom-engine"
            self._checkout(checkout)
            env = self._fake_tools(root, PIN)
            rm = Path(env["PATH"].split(":", 1)[0]) / "rm"
            rm.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            rm.chmod(0o755)
            done = subprocess.run(
                ["bash", str(BUILD), "phantom-engine", "out", PIN],
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
                check=False,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("loader_built=1", done.stdout)
            text = BUILD.read_text(encoding="utf-8")
            needle = 'rm -rf "$writable" >/dev/null 2>&1 || true'
            self.assertIn(needle, text)
            mutated = text.replace(needle, 'rm -rf "$writable"', 1)
            self.assertNotEqual(mutated, text)
            script = root / "mutated.sh"
            script.write_text(mutated, encoding="utf-8")
            broken = subprocess.run(
                ["bash", str(script), "phantom-engine", "out", PIN],
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
                check=False,
            )
            self.assertNotEqual(broken.returncode, 0)
            self.assertIn("loader_built=1", broken.stdout)

    def test_relative_src_does_not_start_docker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "phantom-engine"
            self._checkout(checkout)
            env = self._fake_tools(root, PIN)
            done = subprocess.run(
                [
                    "bash",
                    "-c",
                    "pwd() { printf 'relative-src\\n'; }; export -f pwd; exec bash \"$1\" \"$2\" \"$3\" \"$4\"",
                    "bash",
                    str(BUILD),
                    str(checkout),
                    str(root / "out"),
                    PIN,
                ],
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
                check=False,
            )
            self.assertEqual(done.returncode, 1)
            self.assertIn("pe_src", done.stderr)
            self.assertFalse((root / "docker.log").exists())
            text = BUILD.read_text(encoding="utf-8")
            needle = '  *) echo "pe_src" >&2; exit 1 ;;\n'
            self.assertIn(needle, text)
            mutated = text.replace(needle, "", 1)
            self.assertNotEqual(mutated, text)
            script = root / "mutated.sh"
            script.write_text(mutated, encoding="utf-8")
            broken = subprocess.run(
                [
                    "bash",
                    "-c",
                    "pwd() { printf 'relative-src\\n'; }; export -f pwd; exec bash \"$1\" \"$2\" \"$3\" \"$4\"",
                    "bash",
                    str(script),
                    str(checkout),
                    str(root / "out"),
                    PIN,
                ],
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
                check=False,
            )
            self.assertNotIn("pe_src", broken.stderr)
            self.assertNotEqual(broken.returncode, 0)
            self.assertFalse((root / "docker.log").exists())


class TeardownTests(unittest.TestCase):
    def _env(self, root: Path) -> dict[str, str]:
        return _base_env(
            GCP_LAB_EXECUTE="1",
            EVIDENCE_DIR=str(root),
            RUNNER_TEMP=str(root),
        )

    def test_verified_removed_requires_a_zero_delete_result(self) -> None:
        def verify(env: dict[str, str]) -> int:
            print(json.dumps({"status": "VERIFIED_REMOVED", "name": env["INSTANCE_NAME"]}))
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(ep.lab, "execute_teardown", return_value=0) as deleted, mock.patch.object(
                ep.lab, "execute_verify", side_effect=verify
            ):
                code = ep.teardown_named(self._env(root))
            body = json.loads((root / "enforcement-proof-teardown.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(deleted.return_value, 0)
        self.assertEqual(body["verify_status"], "VERIFIED_REMOVED")
        self.assertEqual(body["deleted"], 0)
        self.assertEqual(body["live_enforcement"], "NOT_PROVEN")

    def test_verified_removed_with_a_changed_delete_result_fails(self) -> None:
        def verify(_env: dict[str, str]) -> int:
            print(json.dumps({"status": "VERIFIED_REMOVED"}))
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(ep.lab, "execute_teardown", return_value=2), mock.patch.object(
                ep.lab, "execute_verify", side_effect=verify
            ):
                code = ep.teardown_named(self._env(Path(tmp)))
        self.assertEqual(code, 2)


def _workflow_texts() -> dict[str, str]:
    directory = ROOT / ".github" / "workflows"
    return {path.name: path.read_text(encoding="utf-8") for path in directory.glob("*.yml")}


class WifPathTests(unittest.TestCase):
    def test_auth_steps_use_an_allowed_workflow_file(self) -> None:
        files = _workflow_texts()
        self.assertEqual(ep.wif_auth_violations(files), [])
        self.assertNotIn(ep.WIF_AUTH_USE, files[ep.WORKFLOW_FILE])
        self.assertIn(ep.WIF_AUTH_USE, files[ep.CALLED_WIF_FILE])
        called = yaml.safe_load(files[ep.CALLED_WIF_FILE])
        prove_if = called["jobs"]["prove"]["if"]
        for slice_name in ep.SLICES:
            self.assertIn(f"inputs.proof_slice == '{slice_name}'", prove_if)
        self.assertIn("inputs.proof_slice == '' || inputs.proof_slice == null", called["jobs"]["gate"]["if"])
        self.assertNotIn("needs", called["jobs"]["prove"])
        caller = yaml.safe_load(files[ep.WORKFLOW_FILE])
        self.assertEqual(
            caller["jobs"]["prove"]["uses"],
            "vantioai/vantio-open-core/.github/workflows/gcp-lab-cost-gate.yml@main",
        )
        self.assertIn("gcp-lab-cost-gate.yml@refs/heads/main", files[ep.CALLED_WIF_FILE])
        self.assertIn('build_pe_loader.sh "${GITHUB_WORKSPACE}/phantom-engine"', files[ep.WORKFLOW_FILE])

    def test_auth_in_the_proof_file_is_rejected(self) -> None:
        files = {
            ep.WORKFLOW_FILE: "uses: google-github-actions/auth@ba79af03959ebeac9769e648f473a284504d9193\n",
        }
        self.assertEqual(ep.wif_auth_violations(files), [ep.WORKFLOW_FILE])

    def test_one_flipped_allowlist_byte_rejects_the_cost_gate(self) -> None:
        files = _workflow_texts()
        allow = list(ep.LIVE_WIF_FILES)
        index = allow.index(ep.CALLED_WIF_FILE)
        allow[index] = _flip(allow[index])
        self.assertNotEqual(allow[index], ep.CALLED_WIF_FILE)
        self.assertIn(ep.CALLED_WIF_FILE, ep.wif_auth_violations(files, allow))


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
        self.assertEqual(text.count(PIN), 1)
        self.assertNotIn(MAIN_TIP, text)
        self.assertNotIn(DRAFT_TIP, text)
        self.assertIn("pe-git-sha-allowlist.txt", text)
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
        self.assertEqual(doc["permissions"]["contents"], "read")
        self.assertEqual(doc["permissions"]["id-token"], "write")
        self.assertEqual(doc["jobs"]["build"]["environment"], "w3-lab-auto")
        self.assertEqual(doc["jobs"]["precheck"]["environment"], "w3-lab-auto")
        precheck_steps = doc["jobs"]["precheck"]["steps"]
        precheck_names = [step["name"] for step in precheck_steps]
        read_at = precheck_names.index("Read the requested Phantom Engine commit")
        self.assertLess(precheck_names.index("Check the proof inputs"), read_at)
        read_step = precheck_steps[read_at]
        self.assertNotIn("continue-on-error", read_step)
        self.assertEqual(read_step["env"]["PE_READ_MODE"], "proof")
        self.assertEqual(read_step["env"]["PE_READ_SHA"], "${{ inputs.pe_git_sha }}")
        self.assertEqual(read_step["env"]["PE_READ_TOKEN"], "${{ secrets.W3_LAB_PRIVATE_BUNDLE_TOKEN }}")
        self.assertIn("bash scripts/gcp/pe_tip_read.sh", read_step["run"])
        self.assertEqual(doc["jobs"]["gate"]["needs"], "precheck")
        self.assertEqual(doc["concurrency"]["group"], "vantio-gce-slot")
        self.assertIs(doc["concurrency"]["cancel-in-progress"], False)
        self.assertNotIn("google-github-actions/auth@", text)
        steps = doc["jobs"]["build"]["steps"]
        names = [step["name"] for step in steps]
        refuse_at = names.index("Refuse a Phantom Engine tip that is not allowlisted")
        checkout_at = names.index("Checkout the Phantom Engine commit")
        record_at = names.index("Record the Phantom Engine commit")
        self.assertLess(refuse_at, checkout_at)
        self.assertLess(checkout_at, record_at)
        self.assertIn("enforcement_proof.py sha", steps[refuse_at]["run"])
        self.assertEqual(steps[refuse_at]["env"]["PE_GIT_SHA"], "${{ inputs.pe_git_sha }}")
        self.assertEqual(steps[checkout_at]["with"]["ref"], "${{ inputs.pe_git_sha }}")
        self.assertEqual(steps[checkout_at]["with"]["repository"], "vantioai/vantio-phantom-engine")
        self.assertIs(steps[checkout_at]["with"]["persist-credentials"], False)
        self.assertEqual(steps[checkout_at]["with"]["token"], "${{ secrets.W3_LAB_PRIVATE_BUNDLE_TOKEN }}")
        self.assertEqual(steps[record_at]["id"], "record")
        self.assertIn("rev-parse HEAD", steps[record_at]["run"])
        self.assertIn("pe_git_sha=", steps[record_at]["run"])
        self.assertIn("head_sha=", steps[record_at]["run"])
        self.assertEqual(
            doc["jobs"]["build"]["outputs"]["head_sha"],
            "${{ steps.record.outputs.head_sha }}",
        )
        ancestor_at = names.index("Require an ancestor of Phantom Engine main")
        build_at = names.index("Build the release loader")
        self.assertLess(record_at, ancestor_at)
        self.assertLess(ancestor_at, build_at)
        self.assertIn("merge-base --is-ancestor", steps[ancestor_at]["run"])
        self.assertNotIn("enforcement_proof.py cleared", steps[ancestor_at]["run"])
        self.assertNotIn("pe_ancestor=cleared", text)
        self.assertNotIn("gcloud", steps[ancestor_at]["run"])
        build = steps[names.index("Build the release loader")]
        self.assertIn('"$PE_GIT_SHA"', build["run"])
        self.assertEqual(build["env"]["PE_GIT_SHA"], "${{ inputs.pe_git_sha }}")
        self.assertEqual(
            doc["jobs"]["prove"]["with"]["pe_git_sha"],
            "${{ needs.build.outputs.head_sha != '' && needs.build.outputs.head_sha || inputs.pe_git_sha }}",
        )
        gate = (ROOT / ".github/workflows/gcp-lab-cost-gate.yml").read_text(encoding="utf-8")
        self.assertIn("PE_GIT_SHA: ${{ inputs.pe_git_sha }}", gate)
        self.assertIn("google-github-actions/auth@", gate)
        mutated = text.replace("expected_oop_usd == '0'", "expected_oop_usd == '1'")
        mutated_doc = yaml.safe_load(mutated)
        self.assertNotIn("expected_oop_usd == '0'", mutated_doc["jobs"]["prove"]["if"])
        self.assertIn(ep.WORKFLOW_FILE, ep.WORKFLOW_REF)
        self.assertIn(ep.WORKFLOW_FILE, lab_auto.WORKFLOWS)
        sheet = (ROOT / "docs/lab/enforcement-proof-OPERATOR.md").read_text(encoding="utf-8")
        self.assertIn(
            "compare, file-deny, reboot-pre, reboot, reboot-post, compare, expired-key, uninstall",
            sheet,
        )
        self.assertIn("pe-git-sha-allowlist.txt", sheet)
        self.assertIn("fails before a VM", sheet)
        self.assertIn("ancestor", sheet)
        self.assertNotIn("cleared", sheet)
        self.assertNotIn(DRAFT_TIP, sheet)
        read_workflow = yaml.safe_load((ROOT / ".github/workflows/pe-tip-read.yml").read_text(encoding="utf-8"))
        self.assertEqual(list(read_workflow[True]), ["workflow_dispatch"])
        self.assertEqual(read_workflow["permissions"], {"contents": "read"})
        self.assertNotIn("id-token", read_workflow["permissions"])
        read_job = read_workflow["jobs"]["read"]
        self.assertEqual(read_job["environment"], "w3-lab-auto")
        read_text = (ROOT / ".github/workflows/pe-tip-read.yml").read_text(encoding="utf-8")
        self.assertIn("bash scripts/gcp/pe_tip_read.sh", read_text)
        self.assertIn("PE_READ_MODE: proof", read_text)
        self.assertIn("PE_READ_SHA: ${{ inputs.pe_git_sha }}", read_text)
        self.assertNotIn("google-github-actions/auth", read_text)
        self.assertNotIn("gcp-lab-cost-gate.yml", read_text)
        self.assertNotIn("gcloud", read_text)
        self.assertNotIn("id-token:", read_text)
        for tip in TIPS:
            self.assertIn(tip, sheet)
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("bash scripts/gcp/pe_tip_read.sh", ci)
        self.assertIn("PE_READ_MODE: pr_ci", ci)
        self.assertIn("secrets.W3_LAB_PRIVATE_BUNDLE_TOKEN", ci)
        reader = (ROOT / "scripts/gcp/pe_tip_read.sh").read_text(encoding="utf-8")
        self.assertIn("pe_read=NOT_PROVEN_token_unavailable_in_pr_ci", reader)
        self.assertNotIn("gcloud", reader)
        self.assertNotIn("compute instances", reader)


class PhantomReadTests(unittest.TestCase):
    def _fake_git(self, root: Path) -> dict[str, str]:
        bindir = root / "bin"
        bindir.mkdir()
        fetch_file = root / "fetch-sha"
        git = bindir / "git"
        git.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >> \"$GIT_LOG\"\n"
            "while [ $# -gt 0 ]; do\n"
            "  case \"$1\" in\n"
            "    -C|-c) shift 2; continue ;;\n"
            "  esac\n"
            "  break\n"
            "done\n"
            "cmd=$1\n"
            "shift\n"
            "case \"$cmd\" in\n"
            "  ls-remote)\n"
            "    if [ \"${PE_LS_FAIL:-0}\" = \"1\" ]; then\n"
            "      echo \"fatal: repository not found\" >&2\n"
            "      exit 1\n"
            "    fi\n"
            "    printf '0123456789abcdef0123456789abcdef01234567\\trefs/heads/main\\n'\n"
            "    ;;\n"
            "  init) ;;\n"
            "  fetch)\n"
            "    if [ \"${PE_FETCH_FAIL:-0}\" = \"1\" ]; then\n"
            "      echo \"fatal: repository not found\" >&2\n"
            "      exit 1\n"
            "    fi\n"
            "    sha=\n"
            "    for arg in \"$@\"; do sha=$arg; done\n"
            "    printf '%s\\n' \"$sha\" > \"$PE_FETCH_FILE\"\n"
            "    ;;\n"
            "  rev-parse) cat \"$PE_FETCH_FILE\" ;;\n"
            "  *) echo git_unexpected >&2; exit 1 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        git.chmod(0o755)
        return {
            "PATH": f"{bindir}:{os.environ.get('PATH', '')}",
            "GIT_LOG": str(root / "git.log"),
            "PE_FETCH_FILE": str(fetch_file),
            "HOME": str(root),
            "PE_READ_TOKEN": "not-a-real-token",
        }

    def test_shallow_fetch_reads_each_allowlisted_tip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self._fake_git(root)
            done = subprocess.run(
                ["bash", str(ROOT / "scripts/gcp/pe_tip_read.sh")],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("pe_read=ls-remote", done.stdout)
            self.assertIn("refs/heads/main", done.stdout)
            for tip in (PIN, MAIN_TIP):
                self.assertIn(f"pe_read=ok sha={tip}", done.stdout)
            log = (root / "git.log").read_text(encoding="utf-8")
            self.assertIn("ls-remote", log)
            self.assertEqual(log.count("fetch --depth=1"), 2)
            self.assertNotIn("gcloud", log)
            self.assertNotIn("not-a-real-token", done.stdout + done.stderr + log)

    def test_repository_not_found_stops_before_a_second_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self._fake_git(root)
            env["PE_LS_FAIL"] = "1"
            done = subprocess.run(
                ["bash", str(ROOT / "scripts/gcp/pe_tip_read.sh")],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(done.returncode, 1)
            self.assertIn("pe_read=404", done.stdout)
            log = (root / "git.log").read_text(encoding="utf-8")
            self.assertIn("ls-remote", log)
            self.assertNotIn("fetch", log)
            self.assertNotIn("not-a-real-token", done.stdout + done.stderr)

    def test_pr_ci_missing_token_is_not_a_pass_and_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self._fake_git(root)
            env.pop("PE_READ_TOKEN")
            env["PE_READ_MODE"] = "pr_ci"
            done = subprocess.run(
                ["bash", str(ROOT / "scripts/gcp/pe_tip_read.sh")],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(done.returncode, 0)
            self.assertEqual(done.stdout.strip(), "pe_read=NOT_PROVEN_token_unavailable_in_pr_ci")
            self.assertNotIn("pe_read=ok", done.stdout)
            self.assertFalse((root / "git.log").exists())

    def test_proof_read_fails_closed_without_a_token_or_a_fetch(self) -> None:
        script = str(ROOT / "scripts/gcp/pe_tip_read.sh")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self._fake_git(root)
            env.pop("PE_READ_TOKEN")
            env["PE_READ_MODE"] = "proof"
            env["PE_READ_SHA"] = PIN
            missing = subprocess.run(
                ["bash", script],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(missing.returncode, 1)
            self.assertIn("pe_read=token_missing", missing.stdout)
            self.assertNotIn("NOT_PROVEN_token_unavailable_in_pr_ci", missing.stdout)
            self.assertFalse((root / "git.log").exists())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            side = root / "pwned"
            env = self._fake_git(root)
            env["PE_READ_MODE"] = "proof"
            env["PE_READ_SHA"] = f"$(touch {side})"
            refused = subprocess.run(
                ["bash", script],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(refused.returncode, 1)
            self.assertIn("pe_read=sha", refused.stderr)
            self.assertFalse(side.exists())
            self.assertFalse((root / "git.log").exists())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self._fake_git(root)
            env["PE_READ_MODE"] = "proof"
            env["PE_READ_SHA"] = PIN
            env["PE_FETCH_FAIL"] = "1"
            failed = subprocess.run(
                ["bash", script],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(failed.returncode, 1)
            self.assertIn("pe_read=404", failed.stdout)
            self.assertNotIn("pe_read=ok", failed.stdout)
            log = (root / "git.log").read_text(encoding="utf-8")
            self.assertIn("ls-remote", log)
            self.assertIn("fetch --depth=1", log)
            self.assertIn(PIN, log)

    def test_proof_read_fetches_only_the_requested_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self._fake_git(root)
            env["PE_READ_MODE"] = "proof"
            env["PE_READ_SHA"] = PIN
            done = subprocess.run(
                ["bash", str(ROOT / "scripts/gcp/pe_tip_read.sh")],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("pe_read=ls-remote", done.stdout)
            self.assertIn(f"pe_read=ok sha={PIN}", done.stdout)
            self.assertNotIn(f"pe_read=ok sha={MAIN_TIP}", done.stdout)
            log = (root / "git.log").read_text(encoding="utf-8")
            self.assertEqual(log.count("fetch --depth=1"), 1)
            self.assertIn(PIN, log)
            self.assertNotIn("not-a-real-token", done.stdout + done.stderr + log)

    def test_missing_token_does_not_call_git(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self._fake_git(root)
            env.pop("PE_READ_TOKEN")
            done = subprocess.run(
                ["bash", str(ROOT / "scripts/gcp/pe_tip_read.sh")],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(done.returncode, 1)
            self.assertIn("pe_read=token_missing", done.stdout)
            self.assertFalse((root / "git.log").exists())


if __name__ == "__main__":
    unittest.main()
