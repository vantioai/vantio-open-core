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


def _cargo_workdir_is_checkout(workdir: str, volume: str, checkout: Path) -> bool:
    """True when cargo's workdir is the absolute checkout, not a bare /src mount."""
    root = str(checkout.resolve())
    if not workdir.startswith("/") or workdir in {"/src", "/src/"}:
        return False
    if workdir != root:
        return False
    return volume == f"{root}:{root}:ro"


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
        rows = ep.green_full_rows()
        for phase, lines, returncode in rows:
            self.assertTrue(ep.phase_accepted(phase, lines, returncode))
        self.assertEqual(ep.overall_grade(rows, ds_wired=False), "INCOMPLETE")
        self.assertNotEqual(ep.overall_grade(rows, ds_wired=False), "PASS")
        self.assertEqual(ep.overall_grade(rows, ds_wired=True), "NOT_PROVEN")
        self.assertNotEqual(ep.overall_grade(rows, ds_wired=True), "PASS")
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
            self.assertIn(
                "ubuntu:24.04@sha256:77eb101c607d6e3d4f5ad0c8a02c2136c689b98aba1f359e6502ba517e5c57ec",
                args,
            )
            self.assertNotIn("debian:13", args)
            self.assertNotIn("/src", workdir)
            self.assertTrue((Path(workdir) / "Cargo.toml").is_file())
            flipped = workdir[:-1] + ("x" if workdir[-1] != "x" else "y")
            self.assertNotEqual(flipped, workdir)
            self.assertFalse(_cargo_workdir_is_checkout(flipped, f"{flipped}:{flipped}:ro", checkout))
            self.assertFalse(_cargo_workdir_is_checkout("/src", "phantom-engine:/src:ro", checkout))
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('build_pe_loader.sh "${GITHUB_WORKSPACE}/phantom-engine"', workflow)
        self.assertNotIn("build_pe_loader.sh phantom-engine ", workflow)

    def test_stage4_images_replace_the_ubuntu_2404_container(self) -> None:
        text = BUILD.read_text(encoding="utf-8")
        self.assertNotIn("The guest is an e2-micro", text)
        self.assertIn("e2-standard-2", text)
        self.assertIn("binstall_tag=v1.27.0", text)
        self.assertIn("bpf_linker_version=0.13.0", text)
        self.assertIn("b2e4b70fcddc5bd6fd90c5cf8dc17b4cf0ea54a3db16c65ee0307f42c9bd3187", text)
        self.assertIn("0e9b2b30f68898177f1cb6f0ecbfa909a82479473a49a0ef66529fd088e3e410", text)
        self.assertNotIn("cargo binstall --no-confirm", text)
        first_check = text.index("sha256sum -c -")
        second_check = text.index("sha256sum -c -", first_check + 1)
        self.assertLess(first_check, text.index('tar -C "$HOME/.cargo/bin" -xzf'))
        self.assertLess(second_check, text.index('tar --zstd -C "$HOME/.cargo/bin" -xf'))
        self.assertNotIn("install-from-binstall-release.sh", text)
        self.assertNotIn("cargo-binstall/main", text)
        self.assertNotIn("sh.rustup.rs", text)
        self.assertNotIn("--default-toolchain nightly --", text)
        self.assertIn("rustup_version=1.29.3", text)
        self.assertIn("b1c8cb14e30889e7e2999e6b69e62d9e9b9ffc0f4df8180564d306d9680e6c55", text)
        self.assertIn("rustup_toolchain=nightly-2026-11-12", text)
        self.assertIn("20261111T000000Z", text)
        self.assertIn("20261112T025704Z", text)
        self.assertIn(
            "ubuntu:24.04@sha256:77eb101c607d6e3d4f5ad0c8a02c2136c689b98aba1f359e6502ba517e5c57ec",
            text,
        )
        self.assertIn(
            "debian:13@sha256:bfc36aecdece0387418759dba474aa856c026ca8087da3606b41b90ab0509c99",
            text,
        )
        self.assertIn(
            "ubuntu:26.04@sha256:0d5255be560e2d2ddcfbfda88549e9e815ef29e7cd7fc62183d5709e6e2963c6",
            text,
        )
        rustup_check = text.index('"$RUSTUP_SHA256" /tmp/rustup-init | sha256sum -c -')
        self.assertLess(rustup_check, text.index("/tmp/rustup-init -y"))
        self.assertLess(text.index("printf \"%s\\n\" \"$APT_SOURCES\""), text.index("apt-get update"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "phantom-engine"
            self._checkout(checkout)
            env = self._fake_tools(root, PIN)
            for guest, image, other in (
                (
                    "debian13",
                    "debian:13@sha256:bfc36aecdece0387418759dba474aa856c026ca8087da3606b41b90ab0509c99",
                    "ubuntu:24.04",
                ),
                (
                    "ubuntu2604",
                    "ubuntu:26.04@sha256:0d5255be560e2d2ddcfbfda88549e9e815ef29e7cd7fc62183d5709e6e2963c6",
                    "ubuntu:24.04",
                ),
            ):
                done = subprocess.run(
                    ["bash", str(BUILD), "phantom-engine", "out", PIN, guest],
                    capture_output=True,
                    text=True,
                    cwd=root,
                    env=env,
                    check=False,
                )
                self.assertEqual(done.returncode, 0, done.stderr)
                args = (root / "docker.log").read_text(encoding="utf-8").splitlines()
                self.assertIn(image, args)
                self.assertNotIn(other, args)
            (root / "docker.log").unlink()
            refused = subprocess.run(
                ["bash", str(BUILD), "phantom-engine", "out", PIN, "ubuntu2404"],
                capture_output=True,
                text=True,
                cwd=root,
                env=env,
                check=False,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("build_image", refused.stderr)
            self.assertFalse((root / "docker.log").exists())

    def test_flipped_digest_fails_before_extract(self) -> None:
        digest = hashlib.sha256(b"pin").hexdigest()
        flipped = digest[:-1] + ("0" if digest[-1] != "0" else "1")
        self.assertNotEqual(flipped, digest)
        with tempfile.TemporaryDirectory() as tmp:
            blob = Path(tmp) / "blob"
            blob.write_bytes(b"pin")
            check = "printf '%s  %s\\n' \"$DIGEST\" \"$BLOB\" | sha256sum -c -"
            good = subprocess.run(
                ["bash", "-c", check],
                capture_output=True,
                text=True,
                env={"DIGEST": digest, "BLOB": str(blob)},
                check=False,
            )
            bad = subprocess.run(
                ["bash", "-c", check],
                capture_output=True,
                text=True,
                env={"DIGEST": flipped, "BLOB": str(blob)},
                check=False,
            )
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertNotEqual(bad.returncode, 0)
        self.assertNotIn("tar ", check)

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
        sheet = (ROOT / "docs/lab/enforcement-proof-OPERATOR.md").read_text(encoding="utf-8")
        self.assertIn(
            "compare, file-deny, reboot-pre, reboot, reboot-post, compare, expired-key, uninstall",
            sheet,
        )


if __name__ == "__main__":
    unittest.main()
