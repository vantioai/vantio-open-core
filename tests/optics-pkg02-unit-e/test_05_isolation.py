"""Unit E does not reopen sealed trees or Unit D."""

import json
import subprocess
import unittest
from pathlib import Path

from support import ROOT, START


FROZEN = [
    "packages/vantio-agent-sdk-py",
    "packages/vantio-cli",
    "packages/vantio-agent-sdk",
    "docs/planning/optics-pkg02",
    "packages/optics-reader-compat-gates",
    "packages/optics-record-reader",
    "packages/optics-node-adapter",
    "packages/optics-evidence-contract",
    "packages/optics-record-vocabulary",
]


class IsolationTests(unittest.TestCase):
    def test_frozen_trees_match_the_starting_commit(self):
        completed = subprocess.run(
            ["git", "diff", "--exit-code", START, "--", *FROZEN],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout or completed.stderr)

    def test_cli_and_reader_gates_stay_closed(self):
        cli = json.loads((ROOT / "packages" / "vantio-cli" / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(cli["version"], "0.3.24")
        gates = (ROOT / "packages" / "optics-reader-compat-gates" / "src" / "gates.cjs").read_text(encoding="utf-8")
        self.assertIn("activates_unit_e: false", gates)
        self.assertIn("activates_unit_d: false", gates)
        marker = json.loads(
            (ROOT / "docs" / "internal" / "optics-pkg02-unit-e" / "MATRIX-MARKERS.json").read_text(encoding="utf-8")
        )
        self.assertTrue(marker["activates_unit_e"])
        self.assertFalse(marker["activates_unit_d"])
        self.assertFalse(marker["registry_publish"])
        self.assertFalse(marker["merged"])
        self.assertFalse(marker["sealed"])
        self.assertEqual(marker["future_version"], "PKG02-FUTURE-PYTHON-UNASSIGNED")
        writers = {cell["reader"] for cell in marker["cells"]}
        self.assertIn("future_python", writers)
        self.assertTrue(all(cell["writer"] == "future_python" for cell in marker["cells"]))
        self.assertTrue(all(cell["achievement"] == "READY_FOR_COUNCIL" for cell in marker["cells"]))
        plan = json.loads(
            (ROOT / "docs" / "planning" / "optics-pkg02" / "RECORD-COMPATIBILITY-MATRIX.json").read_text(
                encoding="utf-8"
            )
        )
        planned = [cell for cell in plan["cells"] if cell["writer"] == "future_python"]
        self.assertEqual(len(planned), len(marker["cells"]))
        self.assertTrue(all(cell["achievement"] == "NOT_SHIPPED" for cell in planned))

    def test_unit_e_paths_do_not_include_unit_d_sources(self):
        root = ROOT / "docs" / "internal" / "optics-pkg02-unit-e"
        self.assertTrue(root.is_dir())
        for path in root.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("activates_unit_d\": true", text)
                self.assertNotIn("PKG02-FUTURE-CLI-UNASSIGNED", text)


if __name__ == "__main__":
    unittest.main()
