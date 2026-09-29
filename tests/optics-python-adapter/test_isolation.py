"""Unit C stays off the frozen writer trees."""

import ast
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def setUpModule():
    if not (ROOT / "docs" / "internal").exists():
        raise unittest.SkipTest("PRIVATE_TREE_REMOVED_FROM_PUBLIC_TIP")


sys.path.insert(0, str(ROOT / "packages" / "optics-python-adapter" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "vantio-agent-sdk-py"))

import vantio.sdk as sdk  # noqa: E402
from optics_python_adapter import CLASSIFICATION, POSTURE, adapt_copy  # noqa: E402

PACKAGE = ROOT / "packages" / "optics-python-adapter"
DOCS = ROOT / "docs" / "internal" / "optics-pkg02-unit-c"
BASE = "587f3b94d47ea958f91d3a99125cd55931d995f1"
BANNER = "PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA"
ALLOWED = (
    "packages/optics-python-adapter/",
    "tests/optics-python-adapter/",
    "docs/internal/optics-pkg02-unit-c/",
)
DOC_NAMES = (
    "INVENTORY.md",
    "BOUNDARY.md",
    "DESIGN.md",
    "ADAPTER.md",
    "FIXTURE-SCORE.md",
    "NO-WRITER.md",
    "KNOWN-LIMITATIONS.md",
    "IMPLEMENTATION-REPORT.md",
)
BANNED_SOURCE = (
    "vantio.sdk",
    "vantio-agent-sdk-py",
    "install_http_observe",
    "write_text",
    "write_bytes",
    "sqlite",
    ".vantio",
    "twine",
)


def _normalize(path):
    return str(path).replace("\\", "/").lstrip("./")


def _scope_violation(path):
    normalized = _normalize(path)
    if normalized == "":
        return None
    if any(normalized.startswith(prefix) for prefix in ALLOWED):
        return None
    return normalized


def _parse_status(text):
    parts = text.split("\0")
    if parts and parts[-1] == "":
        parts.pop()
    paths = []
    index = 0
    while index < len(parts):
        entry = parts[index]
        if len(entry) < 4:
            index += 1
            continue
        paths.append(entry[3:])
        index += 1
        if "R" in entry[:2] or "C" in entry[:2]:
            if index < len(parts):
                paths.append(parts[index])
                index += 1
    return paths


class IsolationTests(unittest.TestCase):
    def test_source_has_no_writer_hooks(self):
        files = list((PACKAGE / "src").rglob("*.py"))
        self.assertGreater(len(files), 0)
        for path in files:
            text = path.read_text(encoding="utf-8")
            ast.parse(text)
            for banned in BANNED_SOURCE:
                self.assertNotIn(banned, text, path.name + " " + banned)

    def test_frozen_versions_stay_put(self):
        cli = json_version(ROOT / "packages" / "vantio-cli" / "package.json")
        node = json_version(ROOT / "packages" / "vantio-agent-sdk" / "package.json")
        contract = json_version(ROOT / "packages" / "optics-evidence-contract" / "package.json")
        vocabulary = json_version(ROOT / "packages" / "optics-record-vocabulary" / "package.json")
        python_text = (ROOT / "packages" / "vantio-agent-sdk-py" / "pyproject.toml").read_text(encoding="utf-8")
        adapter_text = (PACKAGE / "pyproject.toml").read_text(encoding="utf-8")
        workspace = (ROOT / "pnpm-workspace.yaml").read_text(encoding="utf-8")
        self.assertEqual(cli, "0.3.24")
        self.assertEqual(node, "0.2.4")
        self.assertEqual(contract, "0.0.0-unstable-pre-1.0")
        self.assertEqual(vocabulary, "0.0.0-unstable-pre-1.0")
        self.assertIn('version = "3.1.0"', python_text)
        self.assertIn('name = "vantio-agent-sdk"', python_text)
        self.assertIn('name = "vantio-optics-python-adapter"', adapter_text)
        self.assertIn('version = "0.0.0-unstable-pre-1.0"', adapter_text)
        self.assertNotIn("optics-python-adapter", workspace)
        self.assertNotIn("optics-record-vocabulary", workspace)

    def test_paths_stay_inside_unit_c(self):
        self.assertIsNone(_scope_violation("docs/internal/optics-pkg02-unit-c/BOUNDARY.md"))
        self.assertEqual(_scope_violation("packages/vantio-cli/package.json"), "packages/vantio-cli/package.json")
        committed = subprocess.check_output(
            ["git", "diff", "-z", "--name-only", BASE, "HEAD"],
            cwd=ROOT,
            text=True,
        )
        status = subprocess.check_output(["git", "status", "--porcelain=v1", "-z"], cwd=ROOT, text=True)
        committed_paths = [part for part in committed.split("\0") if part]
        uncommitted = _parse_status(status)
        outside = [path for path in committed_paths + uncommitted if _scope_violation(path)]
        self.assertEqual(outside, [])

    def test_docs_carry_the_inert_banner(self):
        for name in DOC_NAMES:
            text = (DOCS / name).read_text(encoding="utf-8")
            self.assertIn(BANNER, text, name)
            self.assertIn("INTERNAL_RESTRICTED", text, name)
            self.assertNotIn("COUNCIL_PASSED", text, name)
        report = (DOCS / "IMPLEMENTATION-REPORT.md").read_text(encoding="utf-8")
        self.assertIn(CLASSIFICATION, report)
        self.assertEqual(POSTURE[0], "PRIVATE")

    def test_live_entrypoint_identity_is_stable(self):
        before = sdk.shield
        sample = adapt_copy({"hostname": "api.example.com", "status": 204})
        after = sdk.shield
        self.assertIs(before, after)
        self.assertFalse(sample["live_writer_modified"])
        self.assertEqual(sample["canonical"]["http_status"], 204)
        self.assertEqual(sample["canonical"]["optics_status"], "UNAVAILABLE")


def json_version(path):
    return json.loads(path.read_text(encoding="utf-8"))["version"]


if __name__ == "__main__":
    unittest.main()
