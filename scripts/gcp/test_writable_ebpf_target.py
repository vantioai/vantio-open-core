#!/usr/bin/env python3
"""The proof build must not write cargo or eBPF output on the read-only checkout."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "scripts" / "gcp" / "build_pe_loader.sh"
ALLOWLIST = ROOT / "scripts" / "gcp" / "pe-git-sha-allowlist.txt"


def _mounts_are_writable(text: str) -> bool:
    return (
        '-v "$src:$src:ro"' in text
        and '-v "$ebpf_host:$src/target"' in text
        and '-v "$ebpf_host:$src/target:ro"' not in text
        and '-v "$cargo_host:/cargo-target"' in text
        and "CARGO_TARGET_DIR=/cargo-target" in text
        and "CARGO_TARGET_DIR=/tmp/target" not in text
        and 'mkdir -p "$cargo_host" "$ebpf_host" "$src/target"' in text
    )


class WritableTargetTests(unittest.TestCase):
    def test_the_script_mounts_writable_output_dirs(self) -> None:
        text = BUILD.read_text(encoding="utf-8")
        self.assertTrue(_mounts_are_writable(text))
        removed = text.replace('  -v "$ebpf_host:$src/target" \\\n', "", 1)
        self.assertNotEqual(removed, text)
        self.assertFalse(_mounts_are_writable(removed))

    def test_a_read_only_checkout_can_still_write_its_target_dir(self) -> None:
        script = r"""
set -euo pipefail
src=$(mktemp -d)
rw=$(mktemp -d)
mkdir -p "$src/target"
echo src > "$src/Cargo.toml"
mkdir -p /mnt
mount --bind "$src" /mnt
mount -o remount,bind,ro /mnt
if mkdir /mnt/target/ebpf 2>/tmp/ro-target.err; then
  echo ro-mkdir-unexpected >&2
  exit 1
fi
grep -q "Read-only file system" /tmp/ro-target.err
mount --bind "$rw" /mnt/target
mkdir -p /mnt/target/ebpf
echo ok > /mnt/target/ebpf/made
test "$(cat /mnt/target/ebpf/made)" = ok
echo repro-ok
"""
        if os.geteuid() == 0:
            command = ["bash", "-c", script]
        else:
            command = ["sudo", "-n", "bash", "-c", script]
        done = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("repro-ok", done.stdout)

    def test_the_script_passes_those_mounts_to_docker(self) -> None:
        pin = ""
        for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
            if len(line) == 40 and all(ch in "0123456789abcdef" for ch in line):
                pin = line
                break
        self.assertEqual(len(pin), 40)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "phantom-engine"
            (checkout / "vantio-loader" / "src").mkdir(parents=True)
            (checkout / "scripts").mkdir()
            (checkout / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")
            (checkout / "rust-toolchain.toml").write_text("[toolchain]\n", encoding="utf-8")
            (checkout / "vantio-loader" / "src" / "main.rs").write_text("fn main() {}\n", encoding="utf-8")
            (checkout / "scripts" / "enforcement_proof_lab.sh").write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
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
                "  merge-base) exit 0 ;;\n"
                "  *) echo git_unexpected >&2; exit 1 ;;\n"
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
            env = {
                "PATH": f"{bindir}:{os.environ.get('PATH', '')}",
                "DOCKER_LOG": str(root / "docker.log"),
                "PE_HEAD": pin,
                "HOME": str(root),
            }
            done = subprocess.run(
                ["bash", str(BUILD), "phantom-engine", "out", pin],
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
            self.assertTrue(
                any(item.endswith(f":{workdir}/target") and not item.endswith(":ro") for item in volumes)
            )
            self.assertTrue(any(item.endswith(":/cargo-target") for item in volumes))


if __name__ == "__main__":
    unittest.main()
