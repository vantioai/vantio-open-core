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
import proof_grade as pg

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "gcp-lab-enforcement-proof.yml"
PROVISION = ROOT / ".github" / "workflows" / "gcp-lab-provision.yml"
BUILD = ROOT / "scripts" / "gcp" / "build_pe_loader.sh"
PIN = ep.PE_GIT_SHA
GO = "zach-run-go-placeholder"
HOST = "proof81"
GATE = json.dumps({"expected_oop_usd": "0", "abort": False})
BEFORE = "11111111-1111-1111-1111-111111111111"
AFTER = "22222222-2222-2222-2222-222222222222"


def _accepted_compare() -> str:
    lines = [
        "enforce_banner=ENFORCING",
        "audit_outside=connect where=outside result=connected errno=0 elapsed_ms=2.0",
        "audit_inside=connect where=inside result=connected errno=0 elapsed_ms=2.0",
        "enforce_inside=connect where=inside result=timeout errno=0 elapsed_ms=1500.0",
        "enforce_outside=connect where=outside result=connected errno=0 elapsed_ms=2.0",
        "drop_counter=source=tcpdump inside=0 outside=2",
        f"ledger_drop=type={pg.EXPECTED_DROP_EVENT} bytes={pg.SENT_PACKET_LENGTH} sent={pg.SENT_PACKET_LENGTH}",
        "compare=PASS",
        "live_enforcement=NOT_PROVEN",
    ]
    return "\n".join(lines) + "\n"


def _accepted_file_deny() -> str:
    return "\n".join(
        [
            "file_deny=PASS",
            "open_inside=result=error errno=13",
            "open_outside=result=ok errno=0",
            "file_deny_row=yes",
        ]
    ) + "\n"


def _accepted_reboot() -> str:
    return "\n".join(
        [
            "reboot_wiped=PASS",
            "reboot_restored=NOT_RUN",
            f"reboot_pre_boot_id={BEFORE}",
            f"reboot_post_boot_id={AFTER}",
        ]
    ) + "\n"


def _replace_prefix(lines: list[str], prefix: str, replacement: str) -> list[str]:
    return [replacement if line.startswith(prefix) else line for line in lines]


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
        self.assertFalse(ep.phase_accepted("compare", ["compare=PASS"], 0))
        self.assertFalse(ep.phase_accepted("compare", ["compare=REFUSED_LSM"], 0))
        self.assertTrue(
            ep.phase_accepted("uninstall", ["uninstall=REFUSED_NOT_ENROLLED"], 2)
        )
        self.assertFalse(ep.phase_accepted("expired-key", ["license_exp_claim=NOT_PROVEN"], 0))
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
                self.boot = "11111111-1111-1111-1111-111111111111"

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
                return "22222222-2222-2222-2222-222222222222" if before == self.boot or before == "11111111-1111-1111-1111-111111111111" else ""

            def ssh(self, _project: str, _name: str, command: str) -> subprocess.CompletedProcess[str]:
                self.commands.append(command)
                if command.startswith("sudo bash ") and "run-proof-phase.sh" in command:
                    phase = command.rsplit(" ", 1)[-1].strip("'")
                    lines = {
                        "compare": _accepted_compare(),
                        "file-deny": _accepted_file_deny(),
                        "reboot-pre": "reboot_pre=RECORDED\n",
                        "reboot-post": _accepted_reboot(),
                        "expired-key": "license_exp_claim=REFUSED\nlicense_exp_observation=REFUSED\n",
                        "uninstall": "uninstall=REFUSED_NOT_ENROLLED\n",
                    }
                    rc = 2 if phase == "uninstall" else 0
                    return subprocess.CompletedProcess([], rc, lines[phase], "")
                if "systemctl reboot --force" in command:
                    self.boot = "22222222-2222-2222-2222-222222222222"
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
            "  ls-files)\n"
            "    if [ -n \"${PE_LS_FILES:-}\" ]; then printf '%s\\n' \"$PE_LS_FILES\"; fi\n"
            "    ;;\n"
            "  read-tree) ;;\n"
            "  diff) exit \"${PE_DIFF_RC:-0}\" ;;\n"
            "  *) printf 'git_unexpected %s\\n' \"$1\" >&2; exit 1 ;;\n"
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


class FailClosedTests(unittest.TestCase):
    def test_timeout_and_loader_row_without_a_counter_is_not_pass(self) -> None:
        lines = [line for line in _accepted_compare().splitlines() if not line.startswith("drop_counter=")]
        self.assertEqual(pg.compare_verdict(lines), "FAIL_UNATTRIBUTED")
        self.assertFalse(ep.phase_accepted("compare", lines, 0))
        lied = _replace_prefix(lines, "drop_counter=", "drop_counter=source=ndjson delta=4")
        lied.append("drop_counter=source=ndjson delta=4")
        self.assertNotEqual(pg.compare_verdict(lied), "PASS")
        self.assertFalse(pg.counter_confirms_drop("drop_counter=source=loader delta=4"))

    def test_any_errno_is_not_a_block_and_the_pinned_errno_is(self) -> None:
        wrong = _replace_prefix(
            _accepted_compare().splitlines(),
            "enforce_inside=",
            "enforce_inside=connect where=inside result=error errno=111 elapsed_ms=3.0",
        )
        self.assertEqual(pg.compare_verdict(wrong), "FAIL_UNEXPECTED_ERRNO")
        self.assertFalse(ep.phase_accepted("compare", wrong, 0))
        pinned = _replace_prefix(
            _accepted_compare().splitlines(),
            "enforce_inside=",
            f"enforce_inside=connect where=inside result=error errno={pg.EXPECTED_BLOCK_ERRNO} elapsed_ms=3.0",
        )
        self.assertEqual(pg.compare_verdict(pinned), "PASS")
        opened = _replace_prefix(
            _accepted_compare().splitlines(),
            "enforce_inside=",
            "enforce_inside=connect where=inside result=connected errno=0 elapsed_ms=3.0",
        )
        self.assertEqual(pg.compare_verdict(opened), "FAIL_OPEN")
        unscoped = _replace_prefix(
            _accepted_compare().splitlines(),
            "enforce_outside=",
            "enforce_outside=connect where=outside result=timeout errno=0 elapsed_ms=3.0",
        )
        self.assertEqual(pg.compare_verdict(unscoped), "FAIL_UNSCOPED")
        delivered = _replace_prefix(
            _accepted_compare().splitlines(),
            "drop_counter=",
            "drop_counter=source=tcpdump inside=1 outside=2",
        )
        self.assertEqual(pg.compare_verdict(delivered), "FAIL_UNATTRIBUTED")
        counted = _replace_prefix(
            _accepted_compare().splitlines(),
            "drop_counter=",
            "drop_counter=source=nft delta=1",
        )
        self.assertEqual(pg.compare_verdict(counted), "PASS")
        quiet = _replace_prefix(
            _accepted_compare().splitlines(),
            "drop_counter=",
            "drop_counter=source=iptables delta=0",
        )
        self.assertNotEqual(pg.compare_verdict(quiet), "PASS")

    def test_mismatched_ledger_type_and_byte_length_fail(self) -> None:
        other = "NETWORK_BLOCK" if pg.EXPECTED_DROP_EVENT != "NETWORK_BLOCK" else "CGROUP_BLOCK"
        rows = [{"EventType": other, "ActionTaken": "BLOCKED", "BytesSevered": pg.SENT_PACKET_LENGTH}]
        self.assertFalse(pg.ledger_rows_ok(rows))
        self.assertIn("type=MISMATCH", pg.ledger_line(json.dumps(rows[0])))
        matched = {"EventType": pg.EXPECTED_DROP_EVENT, "ActionTaken": "BLOCKED", "BytesSevered": pg.SENT_PACKET_LENGTH}
        self.assertTrue(pg.ledger_rows_ok([matched, rows[0]]))
        mutated = dict(matched)
        mutated["BytesSevered"] = pg.SENT_PACKET_LENGTH + 1
        self.assertFalse(pg.ledger_rows_ok([mutated]))
        self.assertFalse(pg.ledger_rows_ok([matched], sent_len=pg.SENT_PACKET_LENGTH + 1))
        bad_line = _replace_prefix(
            _accepted_compare().splitlines(),
            "ledger_drop=",
            f"ledger_drop=type={other} bytes={pg.SENT_PACKET_LENGTH} sent={pg.SENT_PACKET_LENGTH}",
        )
        self.assertEqual(pg.compare_verdict(bad_line), "FAIL_UNATTRIBUTED")
        self.assertEqual(pg.compare_verdict(_accepted_compare().splitlines()), "PASS")

    def test_not_proven_expired_key_fails_and_a_refusal_passes(self) -> None:
        self.assertFalse(
            ep.phase_accepted("expired-key", ["license_exp_claim=NOT_PROVEN", "license_exp_observation=REFUSED"], 0)
        )
        self.assertFalse(
            ep.phase_accepted("expired-key", ["license_exp_claim=REFUSED", "license_exp_observation=NOT_CONSULTED"], 0)
        )
        self.assertTrue(
            ep.phase_accepted("expired-key", ["license_exp_claim=REFUSED", "license_exp_observation=REFUSED"], 0)
        )

    def test_file_deny_needs_eacces_inside_and_success_outside(self) -> None:
        opened = _accepted_file_deny().replace("result=error errno=13", "result=ok errno=0").splitlines()
        self.assertEqual(pg.file_deny_verdict(opened), "FAIL_OPEN")
        self.assertFalse(ep.phase_accepted("file-deny", ["file_deny=PASS", *opened], 0))
        other = _accepted_file_deny().replace("errno=13", "errno=1").splitlines()
        self.assertNotEqual(pg.file_deny_verdict(other), "PASS")
        self.assertEqual(pg.file_deny_verdict(_accepted_file_deny().splitlines()), "PASS")
        mutated = _accepted_file_deny().replace("errno=13", "errno=12").splitlines()
        self.assertNotEqual(pg.file_deny_verdict(mutated), "PASS")

    def test_root_detach_and_fork_inherit_fail_closed(self) -> None:
        wrapper = ep.wrapper_script()
        self.assertIn("root_detach=GAP", wrapper)
        self.assertIn("root_detach_decision=DECISION_NEEDED", wrapper)
        self.assertIn("fork_inherit=INCONCLUSIVE", wrapper)
        self.assertNotIn("root_detach=PASS", wrapper)
        self.assertFalse(ep.phase_accepted("root-detach", ["root_detach=PASS", "root_detach=GAP"], 0))
        self.assertEqual(pg.root_detach_verdict(["root_detach=PASS"]), "GAP")
        self.assertEqual(pg.fork_inherit_verdict([]), "INCONCLUSIVE")
        self.assertFalse(ep.phase_accepted("fork-inherit", [], 1))
        good = [
            "fork_parent=connect where=inside result=timeout errno=0 elapsed_ms=1.0",
            "fork_child=connect where=inside result=timeout errno=0 elapsed_ms=1.0",
            "fork_grandchild=connect where=inside result=timeout errno=0 elapsed_ms=1.0",
            "fork_stranger=connect where=outside result=connected errno=0 elapsed_ms=1.0",
            "fork_trace=parent=ab child=ab grandchild=ab",
            "fork_anchor=parent=7 child=7 grandchild=7",
        ]
        self.assertEqual(pg.fork_inherit_verdict(good), "PASS")
        self.assertTrue(ep.phase_accepted("fork-inherit", good, 0))
        zero = _replace_prefix(good, "fork_trace=", "fork_trace=parent=0 child=0 grandchild=0")
        self.assertEqual(pg.fork_inherit_verdict(zero), "FAIL_UNATTRIBUTED")
        changed = _replace_prefix(good, "fork_trace=", "fork_trace=parent=ab child=cd grandchild=ab")
        self.assertEqual(pg.fork_inherit_verdict(changed), "FAIL_UNATTRIBUTED")
        plan = ep.public_plan("full")
        self.assertEqual(plan["root_detach"], "DECISION_NEEDED")
        self.assertEqual(plan["stub_phases"], ["fork-inherit", "root-detach"])
        self.assertNotIn("fork-inherit", plan["phases"])
        self.assertNotIn("root-detach", plan["phases"])

    def test_reboot_requires_a_new_boot_id(self) -> None:
        same = _accepted_reboot().replace(AFTER, BEFORE).splitlines()
        self.assertFalse(ep.phase_accepted("reboot-post", same, 0))
        self.assertTrue(ep.phase_accepted("reboot-post", _accepted_reboot().splitlines(), 0))
        self.assertFalse(
            ep.phase_accepted(
                "reboot-post",
                _accepted_reboot().splitlines(),
                0,
                {"before": BEFORE, "after": BEFORE},
            )
        )
        missing = [line for line in _accepted_reboot().splitlines() if not line.startswith("reboot_pre_boot_id=")]
        self.assertFalse(ep.phase_accepted("reboot-post", missing, 0))

    def test_not_proven_stops_before_uninstall(self) -> None:
        class Fake:
            def __init__(self) -> None:
                self.commands: list[str] = []
                self.boot = BEFORE

            def instances(self, _project: str) -> list[dict[str, str]]:
                return []

            def create(self, _env: dict[str, str]) -> str:
                return "vantio-gcp-lab-12"

            def scp(self, _project: str, _name: str, _paths: list[Path]) -> None:
                return None

            def wait_ssh(self, _project: str, _name: str) -> str:
                return self.boot

            def boot_id(self, _project: str, _name: str) -> str:
                return self.boot

            def wait_boot(self, _project: str, _name: str, before: str) -> str:
                return AFTER if before == BEFORE else ""

            def ssh(self, _project: str, _name: str, command: str) -> subprocess.CompletedProcess[str]:
                self.commands.append(command)
                if "systemctl reboot --force" in command:
                    self.boot = AFTER
                    return subprocess.CompletedProcess([], 0, "", "")
                phase = command.rsplit(" ", 1)[-1].strip("'")
                if phase == "expired-key":
                    return subprocess.CompletedProcess(
                        [],
                        0,
                        "license_exp_claim=NOT_PROVEN\nlicense_exp_observation=NOT_CONSULTED\n",
                        "",
                    )
                text = {
                    "compare": _accepted_compare(),
                    "file-deny": _accepted_file_deny(),
                    "reboot-pre": "reboot_pre=RECORDED\n",
                    "reboot-post": _accepted_reboot(),
                }.get(phase, "")
                return subprocess.CompletedProcess([], 0, text, "")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            RunTests._loader(self, root / "loader")  # type: ignore[arg-type]
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
        self.assertFalse(any(command.endswith(" uninstall") for command in fake.commands))

    def test_harden_rejects_any_errno_and_not_proven(self) -> None:
        script = (
            "#!/bin/bash\nset -euo pipefail\n"
            "phase_compare() {\n" + ep._OLD_COMPARE + "}\n"
            "phase_expired_key() {\n" + ep._OLD_EXPIRED +
            "phase_reboot_post() {\n" + ep._OLD_REBOOT + "}\n"
        )
        self.assertIn('result=timeout" in item or "result=error" in item', script)
        patched = ep.harden_lab_script(script)
        self.assertNotIn('result=timeout" in item or "result=error" in item', patched)
        self.assertIn("proof_grade.py", patched)
        self.assertIn("compare-verdict", patched)
        self.assertIn("license_exp_claim=NOT_PROVEN", patched)
        self.assertIn("exit 1", patched.split("license_exp_claim=NOT_PROVEN", 1)[1])
        self.assertIn("reboot_pre_boot_id=", patched)
        checked = subprocess.run(["bash", "-n"], input=patched, text=True, capture_output=True, check=False)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(ep.harden_lab_script("#!/bin/bash\nexit 0\n"), "#!/bin/bash\nexit 0\n")
        with self.assertRaises(SystemExit):
            ep.harden_lab_script("#!/bin/bash\nphase_compare() {\n:\n}\n")

    def _git(self, repo: Path) -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "GIT_AUTHOR_NAME": "Proof Test",
                "GIT_AUTHOR_EMAIL": "proof@example.com",
                "GIT_COMMITTER_NAME": "Proof Test",
                "GIT_COMMITTER_EMAIL": "proof@example.com",
            }
        )
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, env=env, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=repo, check=True, env=env, capture_output=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, env=env, capture_output=True)
        return env

    def _pinned_script(self, root: Path, head: str) -> Path:
        script = root / "build.sh"
        script.write_text(BUILD.read_text(encoding="utf-8").replace(PIN, head, 1), encoding="utf-8")
        return script

    def test_assume_unchanged_and_skip_worktree_are_dirty(self) -> None:
        text = BUILD.read_text(encoding="utf-8")
        self.assertNotIn("git status --porcelain", text)
        self.assertLess(text.index("trap cleanup_writable EXIT"), text.index('echo "pe_git_sha"'))
        self.assertLess(text.index("trap cleanup_target EXIT"), text.index("apt-get update"))
        self.assertIn("RUST_TOOLCHAIN=nightly-2026-10-13", text)
        self.assertIn("BPF_LINKER_VERSION=0.12.0", text)
        self.assertIn("bpf-linker@${BPF_LINKER_VERSION}", text)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "phantom-engine"
            CreateAndBuildTests._checkout(self, checkout)  # type: ignore[arg-type]
            env = self._git(checkout)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True, env=env).strip()
            (checkout / "Cargo.toml").write_text("[workspace]\n# dirty\n", encoding="utf-8")
            subprocess.run(["git", "update-index", "--assume-unchanged", "Cargo.toml"], cwd=checkout, check=True, env=env)
            status = subprocess.check_output(["git", "status", "--porcelain"], cwd=checkout, text=True, env=env)
            self.assertEqual(status, "")
            bindir = root / "bin"
            bindir.mkdir()
            docker = bindir / "docker"
            docker.write_text("#!/bin/sh\necho called > \"$DOCKER_LOG\"\nexit 99\n", encoding="utf-8")
            docker.chmod(0o755)
            run_env = {**env, "PATH": f"{bindir}:{env.get('PATH', '')}", "DOCKER_LOG": str(root / "docker.log")}
            done = subprocess.run(
                ["bash", str(self._pinned_script(root, head)), str(checkout), str(root / "out"), head],
                capture_output=True,
                text=True,
                env=run_env,
                check=False,
            )
            self.assertEqual(done.returncode, 1, done.stderr)
            self.assertIn("pe_dirty", done.stderr)
            self.assertFalse((root / "docker.log").exists())
            hidden = text.replace(
                'if worktree_dirty "$src"; then\n  echo "pe_dirty" >&2\n  exit 1\nfi\n',
                'if [[ -n "$(git -C "$src" status --porcelain)" ]]; then\n  echo "pe_dirty" >&2\n  exit 1\nfi\n',
                1,
            )
            self.assertNotEqual(hidden, text)
            (root / "status.sh").write_text(hidden.replace(PIN, head, 1), encoding="utf-8")
            leaked = subprocess.run(
                ["bash", str(root / "status.sh"), str(checkout), str(root / "out2"), head],
                capture_output=True,
                text=True,
                env=run_env,
                check=False,
            )
            self.assertNotIn("pe_dirty", leaked.stderr)
            self.assertTrue((root / "docker.log").exists())
            no_flags = text.replace(
                """  if printf '%s\\n' "$flags" | awk '
    BEGIN { found = 0 }
    {
      tag = substr($0, 1, 1)
      if (tag ~ /[a-z]/ || tag == "S") found = 1
    }
    END { exit found ? 0 : 1 }
  '; then
    return 0
  fi
""",
                "",
                1,
            )
            self.assertNotEqual(no_flags, text)
            (root / "docker.log").unlink()
            (root / "nofield.sh").write_text(no_flags.replace(PIN, head, 1), encoding="utf-8")
            still = subprocess.run(
                ["bash", str(root / "nofield.sh"), str(checkout), str(root / "out3"), head],
                capture_output=True,
                text=True,
                env=run_env,
                check=False,
            )
            self.assertIn("pe_dirty", still.stderr)
            self.assertFalse((root / "docker.log").exists())

    def test_skip_worktree_is_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "phantom-engine"
            CreateAndBuildTests._checkout(self, checkout)  # type: ignore[arg-type]
            env = self._git(checkout)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True, env=env).strip()
            (checkout / "Cargo.toml").write_text("[workspace]\n# skipped\n", encoding="utf-8")
            subprocess.run(["git", "update-index", "--skip-worktree", "Cargo.toml"], cwd=checkout, check=True, env=env)
            status = subprocess.check_output(["git", "status", "--porcelain"], cwd=checkout, text=True, env=env)
            self.assertEqual(status, "")
            flags = subprocess.check_output(["git", "ls-files", "-v", "Cargo.toml"], cwd=checkout, text=True, env=env)
            self.assertTrue(flags.startswith("S"))
            bindir = root / "bin"
            bindir.mkdir()
            docker = bindir / "docker"
            docker.write_text("#!/bin/sh\necho called > \"$DOCKER_LOG\"\nexit 99\n", encoding="utf-8")
            docker.chmod(0o755)
            done = subprocess.run(
                ["bash", str(self._pinned_script(root, head)), str(checkout), str(root / "out"), head],
                capture_output=True,
                text=True,
                env={**env, "PATH": f"{bindir}:{env.get('PATH', '')}", "DOCKER_LOG": str(root / "docker.log")},
                check=False,
            )
            self.assertEqual(done.returncode, 1, done.stderr)
            self.assertIn("pe_dirty", done.stderr)

    def test_failed_compile_chowns_and_removes_the_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "phantom-engine"
            CreateAndBuildTests._checkout(self, checkout)  # type: ignore[arg-type]
            env = CreateAndBuildTests._fake_tools(self, root, PIN)  # type: ignore[arg-type]
            bindir = Path(env["PATH"].split(":", 1)[0])
            (bindir / "docker").write_text(
                "#!/bin/sh\n"
                "for arg in \"$@\"; do\n"
                "  case \"$arg\" in\n"
                "    *:/target|*:*/target) host=${arg%%:*}; mkdir -p \"$host\"; echo kept > \"$host/kept\"; ;;\n"
                "  esac\n"
                "done\n"
                "echo failed > \"$DOCKER_LOG\"\n"
                "exit 1\n",
                encoding="utf-8",
            )
            chown_log = root / "chown.log"
            (bindir / "chown").write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$CHOWN_LOG\"\nexit 0\n",
                encoding="utf-8",
            )
            (bindir / "chown").chmod(0o755)
            done = subprocess.run(
                ["bash", str(BUILD), "phantom-engine", "out", PIN],
                capture_output=True,
                text=True,
                cwd=root,
                env={**env, "CHOWN_LOG": str(chown_log)},
                check=False,
            )
            self.assertNotEqual(done.returncode, 0)
            self.assertNotIn("loader_built=1", done.stdout)
            self.assertTrue(chown_log.is_file(), done.stderr)
            recorded = chown_log.read_text(encoding="utf-8").strip().split()
            self.assertTrue(recorded, done.stderr)
            self.assertFalse(Path(recorded[-1]).exists(), recorded[-1])


if __name__ == "__main__":
    unittest.main()

