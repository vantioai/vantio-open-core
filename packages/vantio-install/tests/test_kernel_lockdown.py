"""Secure Boot and kernel lockdown matrix for installer preflight."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from tests.test_stage_a import Harness  # noqa: E402
from vantio_install.kernel_lockdown import (  # noqa: E402
    REFUSAL,
    SECURE_BOOT_NAME,
    grade,
    parse_lockdown,
    read_facts,
    read_secure_boot,
)

PAIRS = (
    ("off", "none", "PASS", "continue"),
    ("off", "integrity", "PASS", "continue"),
    ("off", "confidentiality", "BLOCKED", "lockdown_confidentiality"),
    ("on", "none", "BLOCKED", "secure_boot_lockdown_mismatch"),
    ("on", "integrity", "PASS", "continue"),
    ("on", "confidentiality", "BLOCKED", "lockdown_confidentiality"),
    ("absent", "none", "PASS", "continue"),
    ("absent", "integrity", "PASS", "continue"),
    ("absent", "confidentiality", "BLOCKED", "lockdown_confidentiality"),
)


def _secure_boot_file(root: Path, payload: bytes | None) -> None:
    directory = root / "sys/firmware/efi/efivars"
    directory.mkdir(parents=True, exist_ok=True)
    if payload is not None:
        (directory / SECURE_BOOT_NAME).write_bytes(payload)


class MatrixTests(unittest.TestCase):
    def test_every_secure_boot_and_lockdown_pair(self) -> None:
        seen = {(boot, mode) for boot, mode, _result, _reason in PAIRS}
        for boot in ("off", "on", "absent"):
            for mode in ("none", "integrity", "confidentiality"):
                self.assertIn((boot, mode), seen)
        for boot, mode, result, reason in PAIRS:
            self.assertEqual(grade(mode, boot), (result, reason), f"{boot} {mode}")

    def test_confidentiality_refusal_is_the_same_sentence_for_every_secure_boot_state(self) -> None:
        sentence = REFUSAL["lockdown_confidentiality"]
        self.assertIn("refuses this host", sentence)
        self.assertIn("confidentiality", sentence)
        self.assertIn("were not checked", sentence)
        for boot in ("off", "on", "absent", "unreadable"):
            result, reason = grade("confidentiality", boot)
            self.assertEqual(result, "BLOCKED")
            self.assertEqual(reason, "lockdown_confidentiality")
            self.assertEqual(REFUSAL[reason], sentence)

    def test_unreadable_facts_do_not_pass(self) -> None:
        self.assertEqual(grade("UNREADABLE", "off"), ("BLOCKED", "lockdown_unreadable"))
        self.assertEqual(grade(None, "integrity"), ("BLOCKED", "lockdown_unreadable"))
        self.assertEqual(grade("integrity", "unreadable"), ("BLOCKED", "secure_boot_unreadable"))
        self.assertEqual(grade("integrity", "maybe"), ("BLOCKED", "secure_boot_unreadable"))
        with self.assertRaises(ValueError):
            parse_lockdown("none integrity")
        with self.assertRaises(ValueError):
            parse_lockdown("[none] [integrity] confidentiality")
        self.assertEqual(parse_lockdown("none [integrity] confidentiality"), "integrity")
        self.assertEqual(parse_lockdown("[none] integrity confidentiality"), "none")
        self.assertEqual(parse_lockdown("none integrity [confidentiality]"), "confidentiality")

    def test_efi_variable_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(read_secure_boot(root), "absent")
            _secure_boot_file(root, b"\x07\x00\x00\x00\x01")
            self.assertEqual(read_secure_boot(root), "on")
            _secure_boot_file(root, b"\x07\x00\x00\x00\x00")
            self.assertEqual(read_secure_boot(root), "off")
            _secure_boot_file(root, b"\x07\x00\x00\x00")
            self.assertEqual(read_secure_boot(root), "unreadable")
            _secure_boot_file(root, b"\x07\x00\x00\x00\x02")
            self.assertEqual(read_secure_boot(root), "unreadable")
            path = root / "sys/firmware/efi/efivars" / SECURE_BOOT_NAME
            path.unlink()
            path.mkdir()
            self.assertEqual(read_secure_boot(root), "unreadable")

    def test_read_facts_records_roadmap_and_does_not_open_a_tpm(self) -> None:
        source = (PACKAGE / "vantio_install" / "kernel_lockdown.py").read_text(encoding="utf-8")
        self.assertNotIn("/dev/tpm", source)
        self.assertNotIn("tpm0", source)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lockdown = root / "sys/kernel/security"
            lockdown.mkdir(parents=True)
            (lockdown / "lockdown").write_text("none [integrity] confidentiality\n", encoding="utf-8")
            _secure_boot_file(root, b"\x07\x00\x00\x00\x01")
            facts = read_facts(root)
        self.assertEqual(facts["lockdown_mode"], "integrity")
        self.assertEqual(facts["secure_boot"], "on")
        self.assertEqual(facts["measured_boot"], "not_checked")
        self.assertEqual(facts["tpm_attestation"], "roadmap")


class PreflightMatrixTests(unittest.TestCase):
    def make(self) -> Harness:
        harness = Harness()
        self.addCleanup(harness.close)
        return harness

    def _check(self, harness: Harness) -> dict:
        code, body = harness.run("plan")
        preflight = json.loads(harness.tx_file("PREFLIGHT.json").read_text(encoding="utf-8"))
        check = next(row for row in preflight["checks"] if row["id"] == "PF-KERNEL-LOCKDOWN")
        return {"code": code, "body": body, "check": check}

    def test_default_fixture_is_integrity_with_secure_boot_absent(self) -> None:
        planned = self._check(self.make())
        self.assertEqual(planned["code"], 0, planned["body"])
        check = planned["check"]
        self.assertEqual(check["result"], "PASS")
        self.assertEqual(check["observed"]["lockdown_mode"], "integrity")
        self.assertEqual(check["observed"]["secure_boot"], "absent")
        self.assertEqual(check["observed"]["measured_boot"], "not_checked")
        self.assertEqual(check["observed"]["tpm_attestation"], "roadmap")
        self.assertNotIn("refusal", check["observed"])
        self.assertNotIn("PF-KERNEL-LOCKDOWN", planned["body"].get("failed_or_limiting_checks", []))

    def test_plan_refuses_confidentiality_with_the_clear_sentence(self) -> None:
        for boot in ("off", "on", "absent"):
            harness = self.make()
            harness.host["lockdown_mode"] = "confidentiality"
            harness.host["lockdown_raw"] = "none integrity [confidentiality]"
            harness.host["secure_boot"] = boot
            planned = self._check(harness)
            self.assertEqual(planned["code"], 2, planned["body"])
            self.assertEqual(planned["body"]["state"], "PREFLIGHT_BLOCKED")
            self.assertIn("PF-KERNEL-LOCKDOWN", planned["body"]["failed_or_limiting_checks"])
            check = planned["check"]
            self.assertEqual(check["result"], "BLOCKED")
            self.assertEqual(check["observed"]["reason"], "lockdown_confidentiality")
            self.assertEqual(check["observed"]["refusal"], REFUSAL["lockdown_confidentiality"])
            self.assertEqual(check["remediation"], REFUSAL["lockdown_confidentiality"])
            self.assertIn("refuses this host", check["remediation"])

    def test_plan_matrix_for_none_and_integrity(self) -> None:
        cases = (
            ("off", "none", 0, "PASS"),
            ("off", "integrity", 0, "PASS"),
            ("on", "integrity", 0, "PASS"),
            ("absent", "none", 0, "PASS"),
            ("on", "none", 2, "BLOCKED"),
        )
        for boot, mode, code, result in cases:
            harness = self.make()
            harness.host["secure_boot"] = boot
            harness.host["lockdown_mode"] = mode
            raw = {
                "none": "[none] integrity confidentiality",
                "integrity": "none [integrity] confidentiality",
            }
            harness.host["lockdown_raw"] = raw[mode]
            planned = self._check(harness)
            self.assertEqual(planned["code"], code, (boot, mode, planned["body"]))
            self.assertEqual(planned["check"]["result"], result, (boot, mode))
            if boot == "on" and mode == "none":
                self.assertEqual(planned["check"]["observed"]["reason"], "secure_boot_lockdown_mismatch")
                self.assertIn("refuses this pair", planned["check"]["remediation"])


if __name__ == "__main__":
    unittest.main()
