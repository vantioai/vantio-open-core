"""Customer host prep matches the lab drop-in and stays observe-only."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
STOCK = "lockdown,capability,landlock,yama,apparmor,ima,evm"
STOCK_WITH_BPF = STOCK + ",bpf"
LOADER_SENTENCE = (
    "The installer writes that line only after explicit operator consent."
)


def _baseline():
    path = REPO / "scripts" / "aws" / "lab-guests" / "baseline_diag.py"
    spec = importlib.util.spec_from_file_location("baseline_diag", path)
    if spec is None or spec.loader is None:
        raise AssertionError("baseline_diag missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _operator_dropin(lab_text: str) -> str:
    lines = lab_text.splitlines()
    lines[0] = "# Operator host prep. Sourced after the cloud image grub files."
    return "\n".join(lines) + "\n"


class HostPrepGuideTest(unittest.TestCase):
    def test_guide_matches_the_lab_dropin(self) -> None:
        from vantio_install.boot_hold.readiness import lsm_cmdline_with_bpf

        self.assertIsNone(lsm_cmdline_with_bpf(STOCK, consent=False))
        self.assertEqual(lsm_cmdline_with_bpf(STOCK, consent=True), STOCK_WITH_BPF)
        guide = (PACKAGE / "docs" / "HOST-PREP.md").read_text(encoding="utf-8")
        lab = _baseline().lsm_dropin_text(STOCK_WITH_BPF)
        operator = _operator_dropin(lab)
        start = guide.index("<<'EOF'\n") + len("<<'EOF'\n")
        end = guide.index("\nEOF", start)
        self.assertEqual(guide[start:end] + "\n", operator)
        self.assertIn("/etc/default/grub.d/99-vantio-lsm.cfg", guide)
        self.assertIn("sudo chmod 0755 /etc/default/grub.d/99-vantio-lsm.cfg", guide)
        self.assertIn("/etc/default/grub.vantio-backup", guide)
        self.assertIn("sudo update-grub", guide)
        self.assertIn("panic=-1", guide)
        self.assertIn(LOADER_SENTENCE, guide)
        self.assertIn("does not describe `vantio-install`", guide)
        self.assertIn("observe-only", guide)
        self.assertIn("NOT_ENABLED", guide)
        self.assertIn("leaves the bootloader alone", guide)
        self.assertIn("40-force-partuuid.cfg", guide)
        self.assertIn("50-cloudimg-settings.cfg", guide)

    def test_customer_pages_point_at_the_guide(self) -> None:
        docs = PACKAGE / "docs"
        pages = {
            "INSTALL.md": docs / "INSTALL.md",
            "PREFLIGHT.md": docs / "PREFLIGHT.md",
            "LIMITATIONS.md": docs / "LIMITATIONS.md",
            "QUICKSTART.md": docs / "QUICKSTART.md",
            "ROLLBACK.md": docs / "ROLLBACK.md",
            "README.md": PACKAGE / "README.md",
        }
        for name, path in pages.items():
            text = path.read_text(encoding="utf-8")
            self.assertIn("HOST-PREP.md", text, name)
        preflight = (docs / "PREFLIGHT.md").read_text(encoding="utf-8")
        self.assertIn(
            "Reboot so /sys/kernel/security/lsm lists bpf, then rerun preflight. "
            "A host without that token is not healthy and is not protected.",
            preflight,
        )
        limits = (docs / "LIMITATIONS.md").read_text(encoding="utf-8")
        self.assertIn("does not describe this package", limits)
        rollback = (docs / "ROLLBACK.md").read_text(encoding="utf-8")
        self.assertIn("99-vantio-lsm.cfg", rollback)

    def test_apply_stays_observe_only(self) -> None:
        live = (PACKAGE / "vantio_install" / "live_executor.py").read_text(encoding="utf-8")
        self.assertIn("Refusing an enforce or privileged flag.", live)
        self.assertIn("Live mutations run observe-only. Enforcement stays off.", live)
        health = (PACKAGE / "vantio_install" / "health.py").read_text(encoding="utf-8")
        self.assertIn(
            'components["enforcement"] = "NOT_ENABLED" if enforcement == "NOT_ENABLED" else "FAIL"',
            health,
        )
