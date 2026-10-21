#!/usr/bin/env python3
"""Fixture grades for the webshell battery. No AWS and no sealed engine."""

from __future__ import annotations

import json
import os
import sys
import tarfile
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUESTS = ROOT / "scripts" / "aws" / "lab-guests"
sys.path.insert(0, str(GUESTS))

import webshell_grade  # noqa: E402
import webshell_guest  # noqa: E402

BEFORE = "11111111-1111-4111-8111-111111111111"
AFTER = "22222222-2222-4222-8222-222222222222"
TOOLS = ("/bin/sh", "/bin/bash", "/usr/bin/python3", "/usr/bin/curl")


def _exec(lineage: str, binary: str, *, errno: int = 13, mode: str = "enforce", enrolled: bool = True) -> dict[str, object]:
    return {"lineage": lineage, "binary": binary, "mode": mode, "errno": errno, "enrolled": enrolled}


def pass_row() -> dict[str, object]:
    checks = [_exec(lineage, binary) for lineage in ("php-fpm", "nginx") for binary in TOOLS]
    return {
        "battery": "webshell",
        "exec": checks,
        "file_write": {"denied": True, "errno": 13, "lineage": "php-fpm", "enrolled": True},
        "child_evasion": [_exec("nginx", "/bin/sh")],
        "loader_kill": {"signal": 9, "same_boot": True, "eacces_remains": True, "killed": True},
        "reboot": {
            "boot_id_before": BEFORE,
            "boot_id_after": AFTER,
            "loader_restarted": True,
            "denied_again": True,
        },
    }


class GradeTests(unittest.TestCase):
    def test_pass_fixture(self) -> None:
        self.assertEqual(webshell_grade.grade_webshell(pass_row()), {"result": "PASS", "reason": "pass"})

    def test_each_failure_mode(self) -> None:
        cases: list[tuple[str, dict[str, object]]] = []
        missing_shell = pass_row()
        missing_shell["exec"] = [row for row in missing_shell["exec"] if row["binary"] != "/bin/sh"]  # type: ignore[index]
        cases.append(("exec_missing", missing_shell))
        one_lineage = pass_row()
        one_lineage["exec"] = [row for row in one_lineage["exec"] if row["lineage"] == "nginx"]  # type: ignore[index]
        cases.append(("lineage_missing", one_lineage))
        allowed = pass_row()
        allowed["exec"] = [_exec("php-fpm", "/bin/sh", errno=0), *allowed["exec"][1:]]  # type: ignore[index]
        cases.append(("exec_not_eacces", allowed))
        audit = pass_row()
        audit["exec"] = [_exec("php-fpm", "/bin/sh", mode="audit"), *audit["exec"][1:]]  # type: ignore[index]
        cases.append(("exec_not_enforce", audit))
        write = pass_row()
        write["file_write"] = {"denied": False, "errno": 0, "lineage": "nginx", "enrolled": True}
        cases.append(("file_write_allowed", write))
        child = pass_row()
        child["child_evasion"] = [_exec("php-fpm", "/bin/bash", errno=0)]
        cases.append(("child_evasion_allowed", child))
        no_child = pass_row()
        no_child["child_evasion"] = []
        cases.append(("child_evasion_missing", no_child))
        kill = pass_row()
        kill["loader_kill"] = {"signal": 9, "same_boot": True, "eacces_remains": False, "killed": True}
        cases.append(("kill_not_persistent", kill))
        other_boot = pass_row()
        other_boot["loader_kill"] = {"signal": 9, "same_boot": False, "eacces_remains": True, "killed": True}
        cases.append(("kill_other_boot", other_boot))
        no_restart = pass_row()
        reboot = dict(no_restart["reboot"])  # type: ignore[arg-type]
        reboot["loader_restarted"] = False
        no_restart["reboot"] = reboot
        cases.append(("loader_not_restarted", no_restart))
        still_open = pass_row()
        reboot = dict(still_open["reboot"])  # type: ignore[arg-type]
        reboot["denied_again"] = False
        still_open["reboot"] = reboot
        cases.append(("reboot_not_denied", still_open))
        same_boot = pass_row()
        reboot = dict(same_boot["reboot"])  # type: ignore[arg-type]
        reboot["boot_id_after"] = BEFORE
        same_boot["reboot"] = reboot
        cases.append(("reboot_boot_unchanged", same_boot))
        lacks = pass_row()
        lacks["reason"] = "SEAL_LACKS_WEBSHELL"
        cases.append(("SEAL_LACKS_WEBSHELL", lacks))
        for reason, row in cases:
            graded = webshell_grade.grade_webshell(row)
            self.assertEqual(graded["result"], "FAIL", reason)
            self.assertEqual(graded["reason"], reason)

    def test_unreadable_row_fails(self) -> None:
        self.assertEqual(webshell_grade.grade_webshell(None)["reason"], "pe_rows_unreadable")
        self.assertEqual(webshell_grade.grade_webshell({"pe_rows_unreadable": True})["reason"], "pe_rows_unreadable")


class BundleTests(unittest.TestCase):
    def test_missing_script_is_seal_lacks_webshell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "seal.oci.tar"
            with tarfile.open(bundle, "w") as archive:
                payload = root / "readme.txt"
                payload.write_text("no script\n", encoding="utf-8")
                archive.add(payload, arcname="readme.txt")
            self.assertIsNone(webshell_guest.extract_webshell_script(bundle, root / "out"))
            row = webshell_guest.build_row(bundle, "pre", "ab" * 32, root / "work")
        self.assertEqual(row["reason"], "SEAL_LACKS_WEBSHELL")
        self.assertEqual(webshell_grade.grade_webshell(row)["reason"], "SEAL_LACKS_WEBSHELL")

    def test_script_in_a_nested_layer_is_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "lab_webshell_battery.py"
            script.write_text("print('ok')\n", encoding="utf-8")
            layer = root / "layer.tar"
            with tarfile.open(layer, "w") as archive:
                archive.add(script, arcname="scripts/lab_webshell_battery.py")
            bundle = root / "seal.oci.tar"
            with tarfile.open(bundle, "w") as archive:
                archive.add(layer, arcname="blobs/sha256/layer.tar")
            found = webshell_guest.extract_webshell_script(bundle, root / "out")
            self.assertIsNotNone(found)
            assert found is not None
            self.assertEqual(found.read_text(encoding="utf-8"), "print('ok')\n")

    def test_guest_refuses_to_run_without_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "lab_webshell_battery.py"
            script.write_text("import json; print(json.dumps({'exec': []}))\n", encoding="utf-8")
            previous = os.environ.pop("VANTIO_LAB_WEBSHELL", None)
            try:
                self.assertIsNone(webshell_guest.run_sealed_script(script, None))
            finally:
                if previous is not None:
                    os.environ["VANTIO_LAB_WEBSHELL"] = previous

    def test_guest_merges_a_fake_sealed_script(self) -> None:
        program = textwrap.dedent(
            """\
            import json, os, sys
            assert os.environ["VANTIO_LAB_WEBSHELL"] == "1"
            step = ""
            if "--reboot-step" in sys.argv:
                step = sys.argv[sys.argv.index("--reboot-step") + 1]
            print(json.dumps({"phases": {"shell-spawn": {"checks": [{"lineage": "nginx", "binary": "/bin/sh", "mode": "enforce", "errno": 13, "enrolled": True}]}}, "boot_id": step or "same"}))
            """
        )
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "lab_webshell_battery.py"
            script.write_text(program, encoding="utf-8")
            os.environ["VANTIO_LAB_WEBSHELL"] = "1"
            try:
                parsed = webshell_guest.run_sealed_script(script, "pre")
            finally:
                os.environ.pop("VANTIO_LAB_WEBSHELL", None)
        merged: dict[str, object] = {}
        webshell_guest.absorb_pe(merged, parsed, "pre")
        self.assertEqual(merged["exec"][0]["errno"], 13)  # type: ignore[index]
        reboot = merged["reboot"]
        assert isinstance(reboot, dict)
        self.assertEqual(reboot["boot_id_before"], "pre")


class DispatcherTests(unittest.TestCase):
    def test_shell_and_workflow_name_the_battery(self) -> None:
        shell = (GUESTS / "enterprise-rows.sh").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/w3-lab-auto-arm.yml").read_text(encoding="utf-8")
        self.assertIn('if [ "${2:-}" = "webshell" ]; then', shell)
        self.assertIn("VANTIO_LAB_WEBSHELL=1", shell)
        self.assertIn("webshell_guest.py", shell)
        self.assertIn("- webshell", workflow)
        self.assertIn("webshell does not run the enterprise rows", workflow)
        self.assertIn("webshell does not run the red-team brain", workflow)
        self.assertIn("jq -r '.lane_seal.sha256'", workflow)
        self.assertIn("jq -r '.public_pin.archive_sha256'", workflow)
        seal = json.loads((ROOT / "release" / "pe-canonical-seal.json").read_text(encoding="utf-8"))
        self.assertNotIn(seal["lane_seal"]["sha256"], workflow)
        self.assertNotIn(seal["public_pin"]["archive_sha256"], workflow)


if __name__ == "__main__":
    unittest.main()
