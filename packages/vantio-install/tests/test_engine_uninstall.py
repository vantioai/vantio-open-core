"""The real bpffs uninstall is the engine command, not a local unlink."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from vantio_install import bpf_pins  # noqa: E402
from vantio_install.errors import InstallError  # noqa: E402


class _Completed:
    def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class EngineUninstallTests(unittest.TestCase):
    def test_argv_confirms_uninstall_and_passes_enterprise_token(self) -> None:
        self.assertEqual(
            bpf_pins.engine_uninstall_argv()[:4],
            ["vantio-loader", "uninstall", "--confirm", "uninstall"],
        )
        with patch.dict(os.environ, {"VANTIO_ENTERPRISE_UNINSTALL_APPROVAL": "  approval-token  "}):
            self.assertEqual(
                bpf_pins.engine_uninstall_argv(),
                [
                    "vantio-loader",
                    "uninstall",
                    "--confirm",
                    "uninstall",
                    "--enterprise-approval",
                    "approval-token",
                ],
            )
        with patch.dict(os.environ, {"VANTIO_ENTERPRISE_UNINSTALL_APPROVAL": "   "}):
            self.assertEqual(len(bpf_pins.engine_uninstall_argv()), 4)

    def test_output_is_verified_only_when_clean(self) -> None:
        self.assertTrue(bpf_pins.engine_output_is_verified(0, "UNINSTALL_VERIFIED\n"))
        self.assertFalse(bpf_pins.engine_output_is_verified(2, "uninstall refused: not root\n"))
        self.assertFalse(
            bpf_pins.engine_output_is_verified(1, "UNINSTALL_RESIDUAL\nresidual: bpffs vantio_persist\n")
        )
        self.assertFalse(bpf_pins.engine_output_is_verified(0, "UNINSTALL_VERIFIED\nUNINSTALL_RESIDUAL\n"))

    def test_fixture_directory_unlinks_without_the_engine(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "vantio_trace_map").write_text("pin\n", encoding="utf-8")
            (root / "other_map").write_text("keep\n", encoding="utf-8")
            with patch("vantio_install.bpf_pins.subprocess.run") as run:
                present, errors = bpf_pins.unlink_known_pins(root)
            run.assert_not_called()
            self.assertEqual(errors, [])
            self.assertEqual(present, [])
            self.assertTrue((root / "other_map").is_file())

    def test_real_bpffs_refuses_a_residual_and_accepts_a_clean_engine(self) -> None:
        with patch("vantio_install.bpf_pins.subprocess.run", return_value=_Completed(2, "uninstall refused: not root\n")):
            with self.assertRaises(InstallError) as refused:
                bpf_pins.unlink_known_pins(bpf_pins.DEFAULT_BPFFS)
        self.assertIn("not verified", str(refused.exception))
        self.assertEqual(refused.exception.failure_class, "FAILED_SAFE")

        with patch("vantio_install.bpf_pins.subprocess.run", side_effect=OSError("missing")):
            with self.assertRaises(InstallError) as missing:
                bpf_pins.remove_known_pins(bpf_pins.DEFAULT_BPFFS)
        self.assertIn("did not run", str(missing.exception))

        with (
            patch(
                "vantio_install.bpf_pins.subprocess.run",
                return_value=_Completed(0, "UNINSTALL_VERIFIED\n"),
            ) as run,
            patch.object(bpf_pins, "scan_known_pins", return_value=([], [])),
        ):
            present, errors = bpf_pins.remove_known_pins(bpf_pins.DEFAULT_BPFFS)
        self.assertEqual(run.call_args.args[0][:4], ["vantio-loader", "uninstall", "--confirm", "uninstall"])
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertEqual(present, [])
        self.assertEqual(errors, [])

    def test_standin_record_is_absent_until_the_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            missing = Path(raw) / "no-standin"
            self.assertFalse(bpf_pins.standin_record_present(missing))
            present = Path(raw) / "standin"
            present.write_text("/tmp/hidden\n", encoding="utf-8")
            self.assertTrue(bpf_pins.standin_record_present(present))


if __name__ == "__main__":
    unittest.main()
